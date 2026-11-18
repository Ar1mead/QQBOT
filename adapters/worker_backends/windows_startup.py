"""STARTUPINFOEX attribute-list construction for AppContainer worker launches.

This module builds the two required process attributes (empty-capability
AppContainer security and an explicit inheritable-handle allowlist). It does
not call CreateProcessW or assign a process to a Job Object.
"""
from __future__ import annotations

import ctypes
from collections.abc import Sequence

from .windows_appcontainer import (
    DWORD,
    HANDLE,
    LPVOID,
    SIZE_T,
    STARTUPINFOEX,
    EmptyAppContainerCapabilities,
    PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
    PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
    require_win64,
)


ULONG_PTR = ctypes.c_size_t
BOOL = ctypes.c_int32
HANDLE_FLAG_INHERIT = 0x00000001
ERROR_INSUFFICIENT_BUFFER = 122
MAX_INHERITED_HANDLES = 3


def _normalize_handles(handles: Sequence[int | HANDLE]) -> tuple[int, ...]:
    if isinstance(handles, (str, bytes)) or not isinstance(handles, Sequence):
        raise TypeError("inherited_handles must be a finite sequence of HANDLE values")
    if not 1 <= len(handles) <= MAX_INHERITED_HANDLES:
        raise ValueError("the worker may inherit only one to three explicit pipe handles")

    normalized = []
    for handle in handles:
        value = handle.value if isinstance(handle, ctypes.c_void_p) else handle
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError("inherited handles must be valid positive native handle values")
        if value in normalized:
            raise ValueError("duplicate inherited handles are not allowed")
        normalized.append(value)
    return tuple(normalized)


class WorkerStartupAttributes:
    """Own a native attribute list and all buffers referenced by its attributes."""

    def __init__(
        self,
        capabilities: EmptyAppContainerCapabilities,
        inherited_handles: Sequence[int | HANDLE],
    ) -> None:
        require_win64()
        if not isinstance(capabilities, EmptyAppContainerCapabilities):
            raise TypeError("capabilities must be an EmptyAppContainerCapabilities lease")
        if capabilities._closed:
            raise RuntimeError("AppContainer capabilities lease is already closed")
        caps = capabilities.value
        if (
            not caps.AppContainerSid
            or caps.CapabilityCount != 0
            or bool(caps.Capabilities)
            or caps.Reserved != 0
        ):
            raise ValueError("worker launch requires a live AppContainer SID with zero capabilities")

        normalized = _normalize_handles(inherited_handles)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        get_handle_info = self._kernel32.GetHandleInformation
        get_handle_info.argtypes = [HANDLE, ctypes.POINTER(DWORD)]
        get_handle_info.restype = BOOL
        for value in normalized:
            flags = DWORD()
            if not get_handle_info(HANDLE(value), ctypes.byref(flags)):
                raise ctypes.WinError(ctypes.get_last_error())
            if not (flags.value & HANDLE_FLAG_INHERIT):
                raise ValueError("every explicitly inherited handle must have HANDLE_FLAG_INHERIT")

        self._initialize = self._kernel32.InitializeProcThreadAttributeList
        self._initialize.argtypes = [LPVOID, DWORD, DWORD, ctypes.POINTER(SIZE_T)]
        self._initialize.restype = BOOL
        self._update = self._kernel32.UpdateProcThreadAttribute
        self._update.argtypes = [
            LPVOID, DWORD, ULONG_PTR, LPVOID, SIZE_T, LPVOID, ctypes.POINTER(SIZE_T)
        ]
        self._update.restype = BOOL
        self._delete = self._kernel32.DeleteProcThreadAttributeList
        self._delete.argtypes = [LPVOID]
        self._delete.restype = None

        self._capabilities = capabilities
        self._inherited_handle_values = normalized
        self._handles = (HANDLE * len(normalized))(*(HANDLE(value) for value in normalized))
        required_size = SIZE_T()
        ctypes.set_last_error(0)
        first_result = self._initialize(None, 2, 0, ctypes.byref(required_size))
        first_error = ctypes.get_last_error()
        if first_result or first_error != ERROR_INSUFFICIENT_BUFFER or required_size.value <= 0:
            raise OSError(
                first_error,
                "InitializeProcThreadAttributeList size probe did not return ERROR_INSUFFICIENT_BUFFER",
            )

        self._buffer = ctypes.create_string_buffer(required_size.value)
        self._attribute_list = ctypes.cast(self._buffer, LPVOID)
        self._initialized = False
        try:
            if not self._initialize(
                self._attribute_list, 2, 0, ctypes.byref(required_size)
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            self._initialized = True

            if not self._update(
                self._attribute_list,
                0,
                PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
                ctypes.cast(self._handles, LPVOID),
                ctypes.sizeof(self._handles),
                None,
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())

            if not self._update(
                self._attribute_list,
                0,
                PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES,
                ctypes.byref(capabilities.value),
                ctypes.sizeof(capabilities.value),
                None,
                None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())

            self.value = STARTUPINFOEX()
            self.value.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEX)
            self.value.lpAttributeList = self._attribute_list
        except Exception:
            self.close()
            raise

    @property
    def inherited_handle_values(self) -> tuple[int, ...]:
        return self._inherited_handle_values

    @property
    def appcontainer_sid(self) -> str:
        return self._capabilities.appcontainer_sid

    def validate_live(self) -> None:
        if not self._initialized or not self._attribute_list:
            raise RuntimeError("STARTUPINFOEX attribute list is already closed")
        if self._capabilities._closed or not self._capabilities.value.AppContainerSid:
            raise RuntimeError("AppContainer capabilities lease must remain open through CreateProcessW")

    def close(self) -> None:
        if getattr(self, "_initialized", False):
            self._delete(self._attribute_list)
            self._initialized = False
            self._attribute_list = None

    def __enter__(self) -> "WorkerStartupAttributes":
        self.validate_live()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()
