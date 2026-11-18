"""Suspended-first Windows AppContainer worker process launcher.

The launch sequence is strict:
  1. CreateProcessW with CREATE_SUSPENDED and explicit inherited handles.
  2. Assign the still-suspended process to the configured Job Object.
  3. Close the host copies of the child pipe endpoints.
  4. Resume the primary thread, requiring the previous suspend count to be 1.

No shell is used. Any failure after process creation terminates the process/job.
This module does not yet supervise pipe I/O, output caps, or execution timeouts.
"""
from __future__ import annotations

import ctypes
import ntpath
import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass

from .windows_appcontainer import (
    CREATE_SUSPENDED,
    CREATE_UNICODE_ENVIRONMENT,
    EXTENDED_STARTUPINFO_PRESENT,
    PROCESS_INFORMATION,
    STARTF_USESTDHANDLES,
    STARTUPINFOEX,
    HANDLE,
    require_win64,
    get_appcontainer_folder_path,
    JOB_OBJECT_CPU_RATE_CONTROL_ENABLE,
    JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP,
)
from .windows_environment import WorkerEnvironment
from .windows_job import (
    WorkerJobObject,
    REQUIRED_LIMIT_FLAGS,
    FORBIDDEN_BREAKAWAY_FLAGS,
)
from .windows_pipes import WorkerPipes
from .windows_startup import WorkerStartupAttributes


DWORD = ctypes.c_uint32
BOOL = ctypes.c_int32
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
WAIT_FAILED = 0xFFFFFFFF
STILL_ACTIVE = 259
INFINITE = 0xFFFFFFFF
PROCESS_TERMINATE_EXIT_CODE = 0xE0010001


@dataclass(frozen=True)
class WorkerLaunchSpec:
    application_path: str
    arguments: tuple[str, ...]
    current_directory: str


class WorkerProcess:
    """Own the process handle; the caller retains ownership of the Job Object."""

    def __init__(self, process_handle: HANDLE, process_id: int) -> None:
        self.handle = process_handle
        self.process_id = process_id
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._close = self._kernel32.CloseHandle
        self._close.argtypes = [HANDLE]
        self._close.restype = BOOL
        self._wait = self._kernel32.WaitForSingleObject
        self._wait.argtypes = [HANDLE, DWORD]
        self._wait.restype = DWORD
        self._get_exit_code = self._kernel32.GetExitCodeProcess
        self._get_exit_code.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
        self._get_exit_code.restype = BOOL

    def wait(self, timeout_ms: int) -> bool:
        if not self.handle:
            raise RuntimeError("worker process handle is already closed")
        if isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or not 0 <= timeout_ms < INFINITE:
            raise ValueError("timeout_ms must be an integer from 0 through 0xFFFFFFFE")
        result = int(self._wait(self.handle, timeout_ms))
        if result == WAIT_OBJECT_0:
            return True
        if result == WAIT_TIMEOUT:
            return False
        if result == WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        raise OSError(f"WaitForSingleObject returned unexpected status 0x{result:08X}")

    def exit_code(self) -> int:
        if not self.handle:
            raise RuntimeError("worker process handle is already closed")
        code = DWORD()
        if not self._get_exit_code(self.handle, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if code.value == STILL_ACTIVE:
            raise RuntimeError("worker process is still active")
        return int(code.value)

    def close(self) -> None:
        if self.handle:
            handle = self.handle
            if not self._close(handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.handle = None

    def __enter__(self) -> "WorkerProcess":
        if not self.handle:
            raise RuntimeError("worker process handle is already closed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def _validate_launch_spec(
    application_path: str,
    arguments: Sequence[str],
    current_directory: str,
) -> WorkerLaunchSpec:
    if not isinstance(application_path, str) or not ntpath.isabs(application_path) or "\x00" in application_path:
        raise ValueError("application_path must be an absolute NUL-free Windows path")
    if not os.path.isfile(application_path):
        raise ValueError("application_path must identify an existing regular file")
    if not isinstance(current_directory, str) or not ntpath.isabs(current_directory) or "\x00" in current_directory:
        raise ValueError("current_directory must be an absolute NUL-free Windows path")
    if not os.path.isdir(current_directory):
        raise ValueError("current_directory must identify an existing directory")
    if isinstance(arguments, (str, bytes)) or not isinstance(arguments, Sequence):
        raise TypeError("arguments must be a finite sequence of strings")
    if len(arguments) > 64:
        raise ValueError("worker command line may contain at most 64 arguments")
    normalized_args = []
    for value in arguments:
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError("worker arguments must be NUL-free strings")
        normalized_args.append(value)
    application_path = os.path.realpath(os.path.abspath(application_path))
    current_directory = os.path.realpath(os.path.abspath(current_directory))
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_attributes = kernel32.GetFileAttributesW
    get_attributes.argtypes = [ctypes.c_wchar_p]
    get_attributes.restype = DWORD
    invalid_attributes = 0xFFFFFFFF
    file_attributes = int(get_attributes(application_path))
    if file_attributes == invalid_attributes:
        raise ctypes.WinError(ctypes.get_last_error())
    if file_attributes & (0x00000010 | 0x00000400):
        raise ValueError("application_path must not be a directory or reparse point")
    directory_attributes = int(get_attributes(current_directory))
    if directory_attributes == invalid_attributes:
        raise ctypes.WinError(ctypes.get_last_error())
    if not (directory_attributes & 0x00000010) or (directory_attributes & 0x00000400):
        raise ValueError("current_directory must be a non-reparse directory")
    return WorkerLaunchSpec(
        application_path=application_path,
        arguments=tuple(normalized_args),
        current_directory=current_directory,
    )


def _close_owned_process_handles(info: PROCESS_INFORMATION, close_handle) -> tuple[tuple[str, int], ...]:
    """Attempt every owned PROCESS_INFORMATION handle and retain failed ones."""
    failures: list[tuple[str, int]] = []
    for handle_name in ("hThread", "hProcess"):
        handle = getattr(info, handle_name)
        if not handle:
            continue
        if close_handle(handle):
            setattr(info, handle_name, None)
        else:
            failures.append((handle_name, ctypes.get_last_error()))
    return tuple(failures)


def launch_appcontainer_worker(
    *,
    application_path: str,
    arguments: Sequence[str],
    current_directory: str,
    environment: WorkerEnvironment,
    pipes: WorkerPipes,
    startup: WorkerStartupAttributes,
    job: WorkerJobObject,
) -> WorkerProcess:
    """Launch one suspended AppContainer process and resume only after job assignment.

    Ownership:
      - `pipes`, `startup`, `environment`, and `job` remain caller-owned.
      - on success, the returned `WorkerProcess` owns the process handle.
      - the child pipe handles are closed in the host after successful inheritance.
      - on any post-CreateProcess failure, the worker/job is terminated fail-closed.
    """
    require_win64()
    spec = _validate_launch_spec(application_path, arguments, current_directory)

    if not isinstance(environment, WorkerEnvironment):
        raise TypeError("environment must be a WorkerEnvironment")
    if not isinstance(pipes, WorkerPipes):
        raise TypeError("pipes must be a WorkerPipes owner")
    if not isinstance(startup, WorkerStartupAttributes):
        raise TypeError("startup must be a WorkerStartupAttributes owner")
    if not isinstance(job, WorkerJobObject) or not job.handle:
        raise TypeError("job must be an open WorkerJobObject")

    startup.validate_live()
    pipes.validate_inheritance_split()
    environment.validate_for_launch()
    child_handles = pipes.child_handles_for_startup()
    child_values = tuple(
        int(value.value if isinstance(value, ctypes.c_void_p) else value)
        for value in child_handles
    )
    if startup.inherited_handle_values != child_values:
        raise ValueError("STARTUPINFOEX handle allowlist does not match the worker's child pipe ends")
    if not environment.block_text.endswith("\x00\x00"):
        raise ValueError("worker environment block is not double-NUL terminated")
    if len(environment.block_text) > 32767:
        raise ValueError("worker environment block exceeds Windows limit")

    # Re-check resource settings immediately before launch; no mutable job
    # configuration is accepted between policy construction and assignment.
    actual_job = job.query_configuration()
    expected = job.configuration
    if (
        (actual_job["limit_flags"] & REQUIRED_LIMIT_FLAGS) != REQUIRED_LIMIT_FLAGS
        or (actual_job["limit_flags"] & FORBIDDEN_BREAKAWAY_FLAGS) != 0
        or actual_job["active_process_limit"] != 1
        or actual_job["process_memory_limit"] != expected.memory_limit_bytes
        or actual_job["job_memory_limit"] != expected.memory_limit_bytes
        or actual_job["cpu_control_flags"] != (JOB_OBJECT_CPU_RATE_CONTROL_ENABLE | JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP)
        or actual_job["cpu_rate_10000"] != expected.cpu_rate_10000
    ):
        raise OSError("worker Job Object policy changed before process creation")

    startup.value.StartupInfo.dwFlags |= STARTF_USESTDHANDLES
    startup.value.StartupInfo.hStdInput = child_handles[0]
    startup.value.StartupInfo.hStdOutput = child_handles[1]
    startup.value.StartupInfo.hStdError = child_handles[2]

    command_line_text = subprocess.list2cmdline(
        [spec.application_path, *spec.arguments]
    )
    if not command_line_text or len(command_line_text) >= 32767:
        raise ValueError("worker command line is empty or exceeds Windows limit")
    command_line = ctypes.create_unicode_buffer(command_line_text)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_process = kernel32.CreateProcessW
    create_process.argtypes = [
        ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_wchar),
        ctypes.c_void_p,
        ctypes.c_void_p,
        BOOL,
        DWORD,
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_void_p,
        ctypes.POINTER(PROCESS_INFORMATION),
    ]
    create_process.restype = BOOL

    assign_job = kernel32.AssignProcessToJobObject
    assign_job.argtypes = [HANDLE, HANDLE]
    assign_job.restype = BOOL
    resume_thread = kernel32.ResumeThread
    resume_thread.argtypes = [HANDLE]
    resume_thread.restype = DWORD
    terminate_process = kernel32.TerminateProcess
    terminate_process.argtypes = [HANDLE, DWORD]
    terminate_process.restype = BOOL
    wait_process = kernel32.WaitForSingleObject
    wait_process.argtypes = [HANDLE, DWORD]
    wait_process.restype = DWORD
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [HANDLE]
    close_handle.restype = BOOL

    info = PROCESS_INFORMATION()
    created = create_process(
        spec.application_path,
        ctypes.cast(command_line, ctypes.POINTER(ctypes.c_wchar)),
        None,
        None,
        True,  # Required when PROC_THREAD_ATTRIBUTE_HANDLE_LIST is used.
        CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT,
        environment.pointer,
        spec.current_directory,
        ctypes.byref(startup.value),
        ctypes.byref(info),
    )
    if not created:
        raise ctypes.WinError(ctypes.get_last_error())

    assigned = False
    try:
        if not assign_job(job.handle, info.hProcess):
            raise ctypes.WinError(ctypes.get_last_error())
        assigned = True

        # Remove the host's duplicate child-end handles before the thread runs.
        pipes.close_child_handles_after_launch()

        previous_suspend_count = int(resume_thread(info.hThread))
        if previous_suspend_count == WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        if previous_suspend_count != 1:
            raise OSError(
                f"worker primary thread had unexpected suspend count {previous_suspend_count}"
            )

        if not close_handle(info.hThread):
            raise ctypes.WinError(ctypes.get_last_error())
        info.hThread = None
        return WorkerProcess(info.hProcess, int(info.dwProcessId))
    except Exception as launch_error:
        if assigned:
            try:
                job.terminate(PROCESS_TERMINATE_EXIT_CODE)
            except Exception:
                # Closing a kill-on-close Job Object is the next containment
                # boundary if TerminateJobObject itself fails.
                try:
                    job.close()
                except Exception:
                    terminate_process(info.hProcess, PROCESS_TERMINATE_EXIT_CODE)
        else:
            terminate_process(info.hProcess, PROCESS_TERMINATE_EXIT_CODE)

        wait_result = int(wait_process(info.hProcess, 5000))
        if wait_result != WAIT_OBJECT_0:
            # A failed/timeout wait is not proof of termination. Make one last
            # direct termination attempt and require a signaled process handle.
            terminate_process(info.hProcess, PROCESS_TERMINATE_EXIT_CODE)
            wait_result = int(wait_process(info.hProcess, 5000))
        if wait_result != WAIT_OBJECT_0:
            # Keep the native handles open rather than pretending cleanup worked.
            raise RuntimeError(
                f"could not confirm termination of failed worker process {int(info.dwProcessId)}"
            ) from launch_error

        close_failures = _close_owned_process_handles(info, close_handle)
        if close_failures:
            details = ", ".join(
                f"{name}=Win32 error {error}" for name, error in close_failures
            )
            raise RuntimeError(
                f"failed to close native handles after worker launch failure: {details}"
            ) from launch_error
        raise
