"""Audited Win64 structure declarations for the AppContainer worker launcher.

This module intentionally contains declarations and layout checks only. It does
not launch a process and must not be treated as a sandbox implementation.
"""
from __future__ import annotations

import ctypes
import os
import re
import uuid


DWORD = ctypes.c_uint32
WORD = ctypes.c_uint16
BOOL = ctypes.c_int32
HANDLE = ctypes.c_void_p
LPVOID = ctypes.c_void_p
SIZE_T = ctypes.c_size_t
ULONG_PTR = ctypes.c_size_t
LARGE_INTEGER = ctypes.c_int64


class SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", LPVOID), ("Attributes", DWORD)]


class SECURITY_CAPABILITIES(ctypes.Structure):
    _fields_ = [
        ("AppContainerSid", LPVOID),
        ("Capabilities", ctypes.POINTER(SID_AND_ATTRIBUTES)),
        ("CapabilityCount", DWORD),
        ("Reserved", DWORD),
    ]


class STARTUPINFO(ctypes.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("lpReserved", ctypes.c_wchar_p),
        ("lpDesktop", ctypes.c_wchar_p),
        ("lpTitle", ctypes.c_wchar_p),
        ("dwX", DWORD),
        ("dwY", DWORD),
        ("dwXSize", DWORD),
        ("dwYSize", DWORD),
        ("dwXCountChars", DWORD),
        ("dwYCountChars", DWORD),
        ("dwFillAttribute", DWORD),
        ("dwFlags", DWORD),
        ("wShowWindow", WORD),
        ("cbReserved2", WORD),
        ("lpReserved2", ctypes.POINTER(ctypes.c_ubyte)),
        ("hStdInput", HANDLE),
        ("hStdOutput", HANDLE),
        ("hStdError", HANDLE),
    ]


class STARTUPINFOEX(ctypes.Structure):
    _fields_ = [
        ("StartupInfo", STARTUPINFO),
        ("lpAttributeList", LPVOID),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", HANDLE),
        ("hThread", HANDLE),
        ("dwProcessId", DWORD),
        ("dwThreadId", DWORD),
    ]


class SECURITY_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("nLength", DWORD),
        ("lpSecurityDescriptor", LPVOID),
        ("bInheritHandle", BOOL),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", LARGE_INTEGER),
        ("PerJobUserTimeLimit", LARGE_INTEGER),
        ("LimitFlags", DWORD),
        ("MinimumWorkingSetSize", SIZE_T),
        ("MaximumWorkingSetSize", SIZE_T),
        ("ActiveProcessLimit", DWORD),
        ("Affinity", ULONG_PTR),
        ("PriorityClass", DWORD),
        ("SchedulingClass", DWORD),
    ]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", SIZE_T),
        ("JobMemoryLimit", SIZE_T),
        ("PeakProcessMemoryUsed", SIZE_T),
        ("PeakJobMemoryUsed", SIZE_T),
    ]


class CPU_RATE_UNION(ctypes.Union):
    _fields_ = [("CpuRate", DWORD), ("Weight", DWORD)]


class JOBOBJECT_CPU_RATE_CONTROL_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("ControlFlags", DWORD),
        ("RateControl", CPU_RATE_UNION),
    ]


# Process creation flags and extended startup attributes.
CREATE_SUSPENDED = 0x00000004
CREATE_UNICODE_ENVIRONMENT = 0x00000400
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
STARTF_USESTDHANDLES = 0x00000100
PROC_THREAD_ATTRIBUTE_HANDLE_LIST = 0x00020002
PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES = 0x00020009

# Job Object limits. No breakaway flag is ever enabled by this backend.
JOB_OBJECT_LIMIT_ACTIVE_PROCESS = 0x00000008
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
JOB_OBJECT_LIMIT_DIE_ON_UNHANDLED_EXCEPTION = 0x00000400
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
JOB_OBJECT_CPU_RATE_CONTROL_INFORMATION_CLASS = 15
JOB_OBJECT_CPU_RATE_CONTROL_ENABLE = 0x00000001
JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP = 0x00000004

# AppContainer capability names are intentionally not declared as defaults:
# the first worker must pass an empty capability array.


def require_win64() -> None:
    """Reject unsupported hosts before any native security API is invoked."""
    if os.name != "nt":
        raise OSError("Windows AppContainer backend is available only on Windows")
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise OSError("the initial Windows worker backend supports Win64 only")


def assert_win64_structure_layouts() -> None:
    """Fail loudly if ctypes declarations drift from the Win64 ABI."""
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("Win64 structure layout checks require 64-bit pointers")
    expected = {
        SID_AND_ATTRIBUTES: 16,
        SECURITY_CAPABILITIES: 24,
        STARTUPINFO: 104,
        STARTUPINFOEX: 112,
        PROCESS_INFORMATION: 24,
        SECURITY_ATTRIBUTES: 24,
        JOBOBJECT_BASIC_LIMIT_INFORMATION: 64,
        IO_COUNTERS: 48,
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION: 144,
        JOBOBJECT_CPU_RATE_CONTROL_INFORMATION: 8,
    }
    for structure, size in expected.items():
        actual = ctypes.sizeof(structure)
        if actual != size:
            raise RuntimeError(
                f"{structure.__name__} has size {actual}; expected Win64 size {size}"
            )


# HRESULT_FROM_WIN32(ERROR_ALREADY_EXISTS), returned when the profile exists.
HRESULT_PROFILE_ALREADY_EXISTS = 0x800700B7
_PROFILE_NAME_RE = re.compile(r"[-_. A-Za-z0-9]{1,64}\Z")


def _windows_userenv():
    require_win64()
    return ctypes.WinDLL("userenv", use_last_error=True)


def ensure_appcontainer_profile_sid(profile_name: str) -> str:
    """Create the named per-user AppContainer profile or derive its existing SID.

    The profile is deliberately persistent. This function never deletes an
    existing profile and never treats a derived SID as proof that a profile
    exists. The returned value is a canonical SID string, not an owned pointer.
    """
    if not isinstance(profile_name, str) or not _PROFILE_NAME_RE.fullmatch(profile_name):
        raise ValueError("profile_name must match [-_. A-Za-z0-9]{1,64}")

    userenv = _windows_userenv()
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    create = userenv.CreateAppContainerProfile
    create.argtypes = [
        ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
        ctypes.POINTER(SID_AND_ATTRIBUTES), DWORD, ctypes.POINTER(LPVOID),
    ]
    create.restype = ctypes.c_long

    derive = userenv.DeriveAppContainerSidFromAppContainerName
    derive.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(LPVOID)]
    derive.restype = ctypes.c_long

    convert = advapi32.ConvertSidToStringSidW
    convert.argtypes = [LPVOID, ctypes.POINTER(ctypes.c_wchar_p)]
    convert.restype = BOOL

    free_sid = advapi32.FreeSid
    free_sid.argtypes = [LPVOID]
    free_sid.restype = LPVOID

    local_free = kernel32.LocalFree
    local_free.argtypes = [HANDLE]
    local_free.restype = HANDLE

    sid = LPVOID()
    hr = int(create(
        profile_name,
        "QQBOT Isolated Adapter Worker",
        "Dedicated low-privilege profile for offline adapter workers",
        None,
        0,
        ctypes.byref(sid),
    )) & 0xFFFFFFFF

    if hr == 0:
        if not sid:
            raise OSError("CreateAppContainerProfile succeeded without returning a SID")
    elif hr == HRESULT_PROFILE_ALREADY_EXISTS:
        sid = LPVOID()
        derive_hr = int(derive(profile_name, ctypes.byref(sid))) & 0xFFFFFFFF
        if derive_hr != 0 or not sid:
            raise OSError(
                f"DeriveAppContainerSidFromAppContainerName failed: HRESULT 0x{derive_hr:08X}"
            )
    else:
        raise OSError(f"CreateAppContainerProfile failed: HRESULT 0x{hr:08X}")

    sid_text = ctypes.c_wchar_p()
    try:
        if not convert(sid, ctypes.byref(sid_text)):
            raise ctypes.WinError(ctypes.get_last_error())
        value = sid_text.value
        if not value or not value.startswith("S-1-15-2-"):
            raise OSError("AppContainer profile returned a non-AppContainer SID")
        return value
    finally:
        if sid_text:
            local_free(ctypes.cast(sid_text, HANDLE))
        if sid:
            free_sid(sid)



class EphemeralAppContainerProfile:
    """Own a uniquely named AppContainer profile and delete it on close.

    Use one profile per worker invocation so AppContainer LOCALAPPDATA does not
    become a persistent cross-run storage area. The profile is deleted only
    after the caller has stopped and closed the worker process.
    """

    def __init__(self, profile_name: str, appcontainer_sid: str, local_appdata_path: str) -> None:
        self.profile_name = profile_name
        self.appcontainer_sid = appcontainer_sid
        self.local_appdata_path = local_appdata_path
        self._closed = False

    @classmethod
    def create(cls) -> "EphemeralAppContainerProfile":
        require_win64()
        profile_name = "QQBOT.Worker." + uuid.uuid4().hex
        if not _PROFILE_NAME_RE.fullmatch(profile_name):
            raise ValueError("generated AppContainer profile name is invalid")

        userenv = _windows_userenv()
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        create = userenv.CreateAppContainerProfile
        create.argtypes = [
            ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
            ctypes.POINTER(SID_AND_ATTRIBUTES), DWORD, ctypes.POINTER(LPVOID),
        ]
        create.restype = ctypes.c_long

        convert = advapi32.ConvertSidToStringSidW
        convert.argtypes = [LPVOID, ctypes.POINTER(ctypes.c_wchar_p)]
        convert.restype = BOOL
        free_sid = advapi32.FreeSid
        free_sid.argtypes = [LPVOID]
        free_sid.restype = LPVOID
        local_free = kernel32.LocalFree
        local_free.argtypes = [HANDLE]
        local_free.restype = HANDLE

        sid = LPVOID()
        hr = int(create(
            profile_name,
            "QQBOT Isolated Adapter Worker",
            "Ephemeral profile for one offline adapter worker invocation",
            None,
            0,
            ctypes.byref(sid),
        )) & 0xFFFFFFFF
        if hr != 0:
            raise OSError(f"CreateAppContainerProfile failed: HRESULT 0x{hr:08X}")
        if not sid:
            raise OSError("CreateAppContainerProfile succeeded without returning a SID")

        sid_text = ctypes.c_wchar_p()
        try:
            if not convert(sid, ctypes.byref(sid_text)):
                raise ctypes.WinError(ctypes.get_last_error())
            sid_value = sid_text.value
            if not sid_value or not sid_value.startswith("S-1-15-2-"):
                raise OSError("AppContainer profile returned a non-AppContainer SID")
        except Exception:
            # The profile was newly created by this call; do not leave it behind.
            delete = userenv.DeleteAppContainerProfile
            delete.argtypes = [ctypes.c_wchar_p]
            delete.restype = ctypes.c_long
            delete(profile_name)
            raise
        finally:
            if sid_text:
                local_free(ctypes.cast(sid_text, HANDLE))
            if sid:
                free_sid(sid)

        try:
            local_appdata = get_appcontainer_folder_path(sid_value)
            if not os.path.isdir(local_appdata):
                raise OSError("new AppContainer profile LocalAppData folder does not exist")
            return cls(profile_name, sid_value, local_appdata)
        except Exception:
            delete = userenv.DeleteAppContainerProfile
            delete.argtypes = [ctypes.c_wchar_p]
            delete.restype = ctypes.c_long
            delete(profile_name)
            raise

    def close(self) -> None:
        if self._closed:
            return
        userenv = _windows_userenv()
        delete = userenv.DeleteAppContainerProfile
        delete.argtypes = [ctypes.c_wchar_p]
        delete.restype = ctypes.c_long
        hr = int(delete(self.profile_name)) & 0xFFFFFFFF
        if hr != 0:
            raise OSError(f"DeleteAppContainerProfile failed: HRESULT 0x{hr:08X}")
        self._closed = True

    def __enter__(self) -> "EphemeralAppContainerProfile":
        if self._closed:
            raise RuntimeError("ephemeral AppContainer profile is already closed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class EmptyAppContainerCapabilities:
    """Own a SECURITY_CAPABILITIES value with zero network capabilities.

    Keep this object alive through CreateProcessW: the native SID and structure
    must remain valid while PROC_THREAD_ATTRIBUTE_SECURITY_CAPABILITIES is used.
    """

    def __init__(self, appcontainer_sid: str) -> None:
        require_win64()
        if not isinstance(appcontainer_sid, str) or not appcontainer_sid.startswith("S-1-15-2-"):
            raise ValueError("appcontainer_sid must be an AppContainer package SID")

        self.appcontainer_sid = appcontainer_sid
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        convert = self._advapi32.ConvertStringSidToSidW
        convert.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(LPVOID)]
        convert.restype = BOOL
        self._local_free = self._kernel32.LocalFree
        self._local_free.argtypes = [HANDLE]
        self._local_free.restype = HANDLE

        self._sid = LPVOID()
        if not convert(appcontainer_sid, ctypes.byref(self._sid)):
            raise ctypes.WinError(ctypes.get_last_error())

        self.value = SECURITY_CAPABILITIES()
        self.value.AppContainerSid = self._sid
        self.value.Capabilities = None
        self.value.CapabilityCount = 0
        self.value.Reserved = 0
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            if self._sid:
                self._local_free(self._sid)
                self._sid = LPVOID()
            self._closed = True

    def __enter__(self) -> "EmptyAppContainerCapabilities":
        if self._closed:
            raise RuntimeError("AppContainer capabilities lease is already closed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


def get_appcontainer_folder_path(appcontainer_sid: str) -> str:
    """Return the OS-managed LocalAppData folder for this AppContainer SID.

    Windows requires the AppContainer profile path in the child's LOCALAPPDATA
    environment variable when constructing the process environment. The native
    string is allocated by COM and must be released with CoTaskMemFree.
    """
    require_win64()
    if (
        not isinstance(appcontainer_sid, str)
        or not re.fullmatch(r"S-1-15-2-(?:[0-9]+-){6}[0-9]+", appcontainer_sid)
    ):
        raise ValueError("appcontainer_sid must be a canonical AppContainer package SID")

    userenv = ctypes.WinDLL("userenv", use_last_error=True)
    ole32 = ctypes.WinDLL("ole32", use_last_error=True)
    get_path = userenv.GetAppContainerFolderPath
    get_path.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_wchar_p)]
    get_path.restype = ctypes.c_long
    free = ole32.CoTaskMemFree
    free.argtypes = [LPVOID]
    free.restype = None

    path_pointer = ctypes.c_wchar_p()
    hr = int(get_path(appcontainer_sid, ctypes.byref(path_pointer))) & 0xFFFFFFFF
    if hr != 0 or not path_pointer.value:
        raise OSError(f"GetAppContainerFolderPath failed: HRESULT 0x{hr:08X}")
    try:
        path = path_pointer.value
        if not path or not os.path.isabs(path):
            raise OSError("GetAppContainerFolderPath returned a non-absolute path")
        return os.path.normpath(path)
    finally:
        if path_pointer:
            free(ctypes.cast(path_pointer, LPVOID))
