"""Audited Win64 structure declarations for the AppContainer worker launcher.

This module intentionally contains declarations and layout checks only. It does
not launch a process and must not be treated as a sandbox implementation.
"""
from __future__ import annotations

import ctypes
import os


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
ERROR_ALREADY_EXISTS = 183
_PROFILE_NAME_RE = __import__("re").compile(r"[-_. A-Za-z0-9]{1,64}\\Z")


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
