"""Fail-closed Windows Job Object resource policy for isolated workers.

This module configures and verifies an unnamed Job Object. It does not create,
assign, resume, or supervise a worker process.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

from .windows_appcontainer import (
    HANDLE,
    JOBOBJECT_BASIC_LIMIT_INFORMATION,
    JOBOBJECT_CPU_RATE_CONTROL_INFORMATION,
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE,
    JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP,
    JOB_OBJECT_CPU_RATE_CONTROL_INFORMATION_CLASS,
    JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
    JOB_OBJECT_LIMIT_ACTIVE_PROCESS,
    JOB_OBJECT_LIMIT_JOB_MEMORY,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOB_OBJECT_LIMIT_PROCESS_MEMORY,
    require_win64,
)


DWORD = ctypes.c_uint32
BOOL = ctypes.c_int32

# A single-process worker still receives finite per-process and per-job ceilings.
MIN_MEMORY_LIMIT_BYTES = 32 * 1024 * 1024
MAX_MEMORY_LIMIT_BYTES = 8 * 1024 * 1024 * 1024
MAX_CPU_RATE_10000 = 10000
REQUIRED_LIMIT_FLAGS = (
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    | JOB_OBJECT_LIMIT_ACTIVE_PROCESS
    | JOB_OBJECT_LIMIT_PROCESS_MEMORY
    | JOB_OBJECT_LIMIT_JOB_MEMORY
)
FORBIDDEN_BREAKAWAY_FLAGS = 0x00000800 | 0x00001000


@dataclass(frozen=True)
class JobConfiguration:
    memory_limit_bytes: int
    cpu_rate_10000: int
    active_process_limit: int = 1


class WorkerJobObject:
    """Own an unnamed Job Object configured to kill all members when closed."""

    def __init__(self, handle: HANDLE, configuration: JobConfiguration) -> None:
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._close_handle = self._kernel32.CloseHandle
        self._close_handle.argtypes = [HANDLE]
        self._close_handle.restype = BOOL
        self._terminate_job = self._kernel32.TerminateJobObject
        self._terminate_job.argtypes = [HANDLE, DWORD]
        self._terminate_job.restype = BOOL
        self.handle = handle
        self.configuration = configuration

    def query_configuration(self) -> dict[str, int]:
        if not self.handle:
            raise RuntimeError("Job Object is already closed")
        query = self._kernel32.QueryInformationJobObject
        query.argtypes = [HANDLE, DWORD, ctypes.c_void_p, DWORD, ctypes.POINTER(DWORD)]
        query.restype = BOOL

        extended = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        returned = DWORD()
        if not query(
            self.handle,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(extended),
            ctypes.sizeof(extended),
            ctypes.byref(returned),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        cpu = JOBOBJECT_CPU_RATE_CONTROL_INFORMATION()
        returned_cpu = DWORD()
        if not query(
            self.handle,
            JOB_OBJECT_CPU_RATE_CONTROL_INFORMATION_CLASS,
            ctypes.byref(cpu),
            ctypes.sizeof(cpu),
            ctypes.byref(returned_cpu),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        return {
            "limit_flags": int(extended.BasicLimitInformation.LimitFlags),
            "active_process_limit": int(extended.BasicLimitInformation.ActiveProcessLimit),
            "process_memory_limit": int(extended.ProcessMemoryLimit),
            "job_memory_limit": int(extended.JobMemoryLimit),
            "cpu_control_flags": int(cpu.ControlFlags),
            "cpu_rate_10000": int(cpu.RateControl.CpuRate),
        }

    def terminate(self, exit_code: int = 1) -> None:
        if not self.handle:
            raise RuntimeError("Job Object is already closed")
        if isinstance(exit_code, bool) or not isinstance(exit_code, int) or not 0 <= exit_code <= 0xFFFFFFFF:
            raise ValueError("exit_code must be an unsigned 32-bit integer")
        if not self._terminate_job(self.handle, exit_code):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self) -> None:
        if self.handle:
            handle, self.handle = self.handle, None
            if not self._close_handle(handle):
                raise ctypes.WinError(ctypes.get_last_error())

    def __enter__(self) -> "WorkerJobObject":
        if not self.handle:
            raise RuntimeError("Job Object is already closed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def _validate_configuration(memory_limit_bytes: int, cpu_rate_10000: int) -> JobConfiguration:
    if (
        isinstance(memory_limit_bytes, bool)
        or not isinstance(memory_limit_bytes, int)
        or not MIN_MEMORY_LIMIT_BYTES <= memory_limit_bytes <= MAX_MEMORY_LIMIT_BYTES
    ):
        raise ValueError(
            f"memory_limit_bytes must be between {MIN_MEMORY_LIMIT_BYTES} and {MAX_MEMORY_LIMIT_BYTES}"
        )
    if (
        isinstance(cpu_rate_10000, bool)
        or not isinstance(cpu_rate_10000, int)
        or not 1 <= cpu_rate_10000 <= MAX_CPU_RATE_10000
    ):
        raise ValueError("cpu_rate_10000 must be an integer from 1 through 10000")
    return JobConfiguration(
        memory_limit_bytes=memory_limit_bytes,
        cpu_rate_10000=cpu_rate_10000,
        active_process_limit=1,
    )


def create_worker_job(memory_limit_bytes: int, cpu_rate_10000: int) -> WorkerJobObject:
    """Create, configure, and read-back verify a restrictive unnamed Job Object.

    cpu_rate_10000 uses Windows' 1/100-percent units (2000 means a 20% hard cap).
    There is deliberately no breakaway option and no permissive fallback.
    """
    configuration = _validate_configuration(memory_limit_bytes, cpu_rate_10000)
    require_win64()

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_job = kernel32.CreateJobObjectW
    create_job.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
    create_job.restype = HANDLE
    set_info = kernel32.SetInformationJobObject
    set_info.argtypes = [HANDLE, DWORD, ctypes.c_void_p, DWORD]
    set_info.restype = BOOL
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [HANDLE]
    close_handle.restype = BOOL

    handle = create_job(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    job = None

    try:
        extended = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        extended.BasicLimitInformation = JOBOBJECT_BASIC_LIMIT_INFORMATION()
        extended.BasicLimitInformation.LimitFlags = REQUIRED_LIMIT_FLAGS
        extended.BasicLimitInformation.ActiveProcessLimit = 1
        extended.ProcessMemoryLimit = memory_limit_bytes
        extended.JobMemoryLimit = memory_limit_bytes

        if not set_info(
            handle,
            JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
            ctypes.byref(extended),
            ctypes.sizeof(extended),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        cpu = JOBOBJECT_CPU_RATE_CONTROL_INFORMATION()
        cpu.ControlFlags = JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP
        cpu.RateControl.CpuRate = cpu_rate_10000
        if not set_info(
            handle,
            JOB_OBJECT_CPU_RATE_CONTROL_INFORMATION_CLASS,
            ctypes.byref(cpu),
            ctypes.sizeof(cpu),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        job = WorkerJobObject(handle, configuration)
        handle = None  # Ownership transferred; cleanup is now through job.close().
        actual = job.query_configuration()
        expected_cpu_flags = JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP
        if (
            (actual["limit_flags"] & REQUIRED_LIMIT_FLAGS) != REQUIRED_LIMIT_FLAGS
            or (actual["limit_flags"] & FORBIDDEN_BREAKAWAY_FLAGS)
            or actual["active_process_limit"] != 1
            or actual["process_memory_limit"] != memory_limit_bytes
            or actual["job_memory_limit"] != memory_limit_bytes
            or actual["cpu_control_flags"] != expected_cpu_flags
            or actual["cpu_rate_10000"] != cpu_rate_10000
        ):
            raise OSError("Job Object resource policy failed read-back verification")
        return job
    except Exception:
        if job is not None:
            job.close()
        elif handle:
            close_handle(handle)
        raise
