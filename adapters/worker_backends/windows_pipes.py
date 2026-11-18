"""Bounded-handle Windows anonymous pipe set for an isolated worker.

The parent retains stdin-write/stdout-read/stderr-read. Only the opposite ends
are marked inheritable and may be passed to STARTUPINFOEX's handle allowlist.
This module does not launch a process or perform pipe I/O.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

from .windows_appcontainer import HANDLE, SECURITY_ATTRIBUTES, require_win64


DWORD = ctypes.c_uint32
BOOL = ctypes.c_int32
HANDLE_FLAG_INHERIT = 0x00000001
DEFAULT_PIPE_BUFFER_BYTES = 64 * 1024
MAX_PIPE_BUFFER_BYTES = 1024 * 1024


@dataclass(frozen=True)
class WorkerPipeHandles:
    child_stdin: HANDLE
    child_stdout: HANDLE
    child_stderr: HANDLE
    parent_stdin: HANDLE
    parent_stdout: HANDLE
    parent_stderr: HANDLE

    @property
    def child_handle_values(self) -> tuple[int, int, int]:
        return tuple(
            int(value.value if isinstance(value, ctypes.c_void_p) else value or 0) if value else 0
            for value in (self.child_stdin, self.child_stdout, self.child_stderr)
        )


class WorkerPipes:
    """Own three anonymous pipes with a strict parent/child inheritance split."""

    def __init__(self, handles: WorkerPipeHandles) -> None:
        self.handles = handles
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._close = self._kernel32.CloseHandle
        self._close.argtypes = [HANDLE]
        self._close.restype = BOOL
        self._closed = False
        self._child_closed = False

    @classmethod
    def create(cls, buffer_bytes: int = DEFAULT_PIPE_BUFFER_BYTES) -> "WorkerPipes":
        if (
            isinstance(buffer_bytes, bool)
            or not isinstance(buffer_bytes, int)
            or not 4096 <= buffer_bytes <= MAX_PIPE_BUFFER_BYTES
        ):
            raise ValueError("buffer_bytes must be between 4096 and 1048576")
        require_win64()

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_pipe = kernel32.CreatePipe
        create_pipe.argtypes = [
            ctypes.POINTER(HANDLE),
            ctypes.POINTER(HANDLE),
            ctypes.POINTER(SECURITY_ATTRIBUTES),
            DWORD,
        ]
        create_pipe.restype = BOOL
        set_info = kernel32.SetHandleInformation
        set_info.argtypes = [HANDLE, DWORD, DWORD]
        set_info.restype = BOOL
        get_info = kernel32.GetHandleInformation
        get_info.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
        get_info.restype = BOOL
        close = kernel32.CloseHandle
        close.argtypes = [HANDLE]
        close.restype = BOOL

        security = SECURITY_ATTRIBUTES()
        security.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
        security.lpSecurityDescriptor = None
        security.bInheritHandle = 1

        owned: list[HANDLE] = []

        def new_pipe() -> tuple[HANDLE, HANDLE]:
            read_handle, write_handle = HANDLE(), HANDLE()
            if not create_pipe(
                ctypes.byref(read_handle),
                ctypes.byref(write_handle),
                ctypes.byref(security),
                buffer_bytes,
            ):
                error = ctypes.get_last_error()
                if read_handle:
                    close(read_handle)
                if write_handle:
                    close(write_handle)
                raise ctypes.WinError(error)
            if not read_handle or not write_handle:
                if read_handle:
                    close(read_handle)
                if write_handle:
                    close(write_handle)
                raise OSError("CreatePipe returned an invalid handle")
            owned.extend([read_handle, write_handle])
            return read_handle, write_handle

        try:
            child_stdin, parent_stdin = new_pipe()
            parent_stdout, child_stdout = new_pipe()
            parent_stderr, child_stderr = new_pipe()

            # Parent endpoints must never leak into the worker.
            for handle in (parent_stdin, parent_stdout, parent_stderr):
                if not set_info(handle, HANDLE_FLAG_INHERIT, 0):
                    raise ctypes.WinError(ctypes.get_last_error())

            # Verify both sides of the inheritance split before exposing handles.
            for handle, expected in (
                (child_stdin, True),
                (child_stdout, True),
                (child_stderr, True),
                (parent_stdin, False),
                (parent_stdout, False),
                (parent_stderr, False),
            ):
                flags = DWORD()
                if not get_info(handle, ctypes.byref(flags)):
                    raise ctypes.WinError(ctypes.get_last_error())
                if bool(flags.value & HANDLE_FLAG_INHERIT) is not expected:
                    raise OSError("anonymous pipe handle inheritance split failed verification")

            instance = cls(
                WorkerPipeHandles(
                    child_stdin=child_stdin,
                    child_stdout=child_stdout,
                    child_stderr=child_stderr,
                    parent_stdin=parent_stdin,
                    parent_stdout=parent_stdout,
                    parent_stderr=parent_stderr,
                )
            )
            owned.clear()  # Ownership transferred to the WorkerPipes instance.
            return instance
        except Exception:
            for handle in reversed(owned):
                close(handle)
            raise

    def child_handles_for_startup(self) -> tuple[HANDLE, HANDLE, HANDLE]:
        if self._closed:
            raise RuntimeError("worker pipes are already closed")
        if self._child_closed:
            raise RuntimeError("worker child pipe handles are already closed")
        return (
            self.handles.child_stdin,
            self.handles.child_stdout,
            self.handles.child_stderr,
        )

    def close_child_handles_after_launch(self) -> None:
        """Close the host copies after CreateProcess has inherited the child ends."""
        if self._closed:
            raise RuntimeError("worker pipes are already closed")
        handles = (
            self.handles.child_stdin,
            self.handles.child_stdout,
            self.handles.child_stderr,
        )
        remaining = list(handles)
        for index, handle in enumerate(handles):
            if not self._close(handle):
                # Keep only handles not yet closed so a later cleanup does not
                # double-close already released native handles.
                for closed_index in range(index):
                    remaining[closed_index] = None
                self.handles = WorkerPipeHandles(
                    child_stdin=remaining[0], child_stdout=remaining[1], child_stderr=remaining[2],
                    parent_stdin=self.handles.parent_stdin,
                    parent_stdout=self.handles.parent_stdout,
                    parent_stderr=self.handles.parent_stderr,
                )
                self._child_closed = True
                raise ctypes.WinError(ctypes.get_last_error())
            remaining[index] = None
        self.handles = WorkerPipeHandles(
            child_stdin=None, child_stdout=None, child_stderr=None,
            parent_stdin=self.handles.parent_stdin,
            parent_stdout=self.handles.parent_stdout,
            parent_stderr=self.handles.parent_stderr,
        )
        self._child_closed = True

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        handles = (
            self.handles.child_stdin,
            self.handles.child_stdout,
            self.handles.child_stderr,
            self.handles.parent_stdin,
            self.handles.parent_stdout,
            self.handles.parent_stderr,
        )
        first_error = None
        for handle in handles:
            if handle:
                if not self._close(handle) and first_error is None:
                    first_error = ctypes.get_last_error()
        if first_error is not None:
            raise ctypes.WinError(first_error)

    def __enter__(self) -> "WorkerPipes":
        if self._closed:
            raise RuntimeError("worker pipes are already closed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
