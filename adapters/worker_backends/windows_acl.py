"""Handle-based, fail-closed Windows directory ACL helpers for AppContainer workers.

This module prepares directory security descriptors only. It does not launch a
worker and does not prove effective access from an AppContainer token.
"""
from __future__ import annotations

import ctypes
import os
from typing import Final

from .windows_appcontainer import HANDLE, LPVOID, require_win64


DWORD = ctypes.c_uint32

# Win32 file and security constants.
GENERIC_READ_FILE: Final[int] = 0x00120089
GENERIC_WRITE_FILE: Final[int] = 0x00120116
GENERIC_EXECUTE_FILE: Final[int] = 0x001200A0
FILE_READ_ATTRIBUTES: Final[int] = 0x00000080
READ_CONTROL: Final[int] = 0x00020000
WRITE_DAC: Final[int] = 0x00040000
WRITE_OWNER: Final[int] = 0x00080000
SHARE_ALL: Final[int] = 0x00000007
OPEN_EXISTING: Final[int] = 3
FILE_FLAG_OPEN_REPARSE_POINT: Final[int] = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS: Final[int] = 0x02000000
FILE_ATTRIBUTE_DIRECTORY: Final[int] = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT: Final[int] = 0x00000400
FILE_ATTRIBUTE_TAG_INFO_CLASS: Final[int] = 9

SE_FILE_OBJECT: Final[int] = 1
DACL_SECURITY_INFORMATION: Final[int] = 0x00000004
LABEL_SECURITY_INFORMATION: Final[int] = 0x00000010
ACL_REVISION: Final[int] = 2
ACL_SIZE_INFORMATION_CLASS: Final[int] = 2

GRANT_ACCESS: Final[int] = 1
TRUSTEE_IS_SID: Final[int] = 0
TRUSTEE_IS_UNKNOWN: Final[int] = 0
OBJECT_INHERIT_ACE: Final[int] = 0x01
CONTAINER_INHERIT_ACE: Final[int] = 0x02
ACCESS_ALLOWED_ACE_TYPE: Final[int] = 0x00
SYSTEM_MANDATORY_LABEL_ACE_TYPE: Final[int] = 0x11
SYSTEM_MANDATORY_LABEL_NO_WRITE_UP: Final[int] = 0x01
LOW_INTEGRITY_SID: Final[str] = "S-1-16-4096"
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


class TRUSTEE_W(ctypes.Structure):
    _fields_ = [
        ("pMultipleTrustee", LPVOID),
        ("MultipleTrusteeOperation", DWORD),
        ("TrusteeForm", DWORD),
        ("TrusteeType", DWORD),
        ("ptstrName", ctypes.c_wchar_p),
    ]


class EXPLICIT_ACCESS_W(ctypes.Structure):
    _fields_ = [
        ("grfAccessPermissions", DWORD),
        ("grfAccessMode", DWORD),
        ("grfInheritance", DWORD),
        ("Trustee", TRUSTEE_W),
    ]


class ACL_SIZE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("AceCount", DWORD),
        ("AclBytesInUse", DWORD),
        ("AclBytesFree", DWORD),
    ]


class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
    _fields_ = [("FileAttributes", DWORD), ("ReparseTag", DWORD)]


class ACE_HEADER(ctypes.Structure):
    _fields_ = [("AceType", ctypes.c_ubyte), ("AceFlags", ctypes.c_ubyte), ("AceSize", ctypes.c_uint16)]


class ACCESS_ALLOWED_ACE(ctypes.Structure):
    _fields_ = [("Header", ACE_HEADER), ("Mask", DWORD), ("SidStart", DWORD)]


def assert_win64_acl_structure_layouts() -> None:
    """Fail loudly if ACL-related ctypes declarations drift from the Win64 ABI."""
    if ctypes.sizeof(ctypes.c_void_p) != 8:
        raise RuntimeError("Win64 ACL layout checks require 64-bit pointers")
    expected = {
        TRUSTEE_W: 32,
        EXPLICIT_ACCESS_W: 48,
        ACL_SIZE_INFORMATION: 12,
        FILE_ATTRIBUTE_TAG_INFO: 8,
        ACE_HEADER: 4,
        ACCESS_ALLOWED_ACE: 12,
    }
    for structure, size in expected.items():
        actual = ctypes.sizeof(structure)
        if actual != size:
            raise RuntimeError(
                f"{structure.__name__} has size {actual}; expected Win64 size {size}"
            )


def _raise_winerror(code: int, operation: str) -> None:
    if code:
        raise OSError(code, f"{operation} failed: {ctypes.FormatError(code).strip()}")


class _AclObjectHandle:
    """Own a verified file/directory handle opened without following reparse points."""

    def __init__(self, path: str, desired_access: int, expected_directory: bool | None) -> None:
        require_win64()
        if not isinstance(path, str) or not path or "\\x00" in path:
            raise ValueError("path must be a non-empty filesystem path")
        if not os.path.isabs(path):
            raise ValueError("ACL target path must be absolute")

        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = self._kernel32.CreateFileW
        create_file.argtypes = [
            ctypes.c_wchar_p, DWORD, DWORD, LPVOID, DWORD, DWORD, HANDLE
        ]
        create_file.restype = HANDLE
        self._close_handle = self._kernel32.CloseHandle
        self._close_handle.argtypes = [HANDLE]
        self._close_handle.restype = ctypes.c_int32
        flags = FILE_FLAG_OPEN_REPARSE_POINT
        if expected_directory is not False:
            flags |= FILE_FLAG_BACKUP_SEMANTICS
        self.value = create_file(
            os.path.abspath(path),
            desired_access,
            SHARE_ALL,
            None,
            OPEN_EXISTING,
            flags,
            None,
        )
        if self.value == INVALID_HANDLE_VALUE or not self.value:
            raise ctypes.WinError(ctypes.get_last_error())

        try:
            info = FILE_ATTRIBUTE_TAG_INFO()
            get_info = self._kernel32.GetFileInformationByHandleEx
            get_info.argtypes = [HANDLE, ctypes.c_int, LPVOID, DWORD]
            get_info.restype = ctypes.c_int32
            if not get_info(
                self.value,
                FILE_ATTRIBUTE_TAG_INFO_CLASS,
                ctypes.byref(info),
                ctypes.sizeof(info),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if info.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
                raise ValueError("ACL target must not be a reparse point")
            is_directory = bool(info.FileAttributes & FILE_ATTRIBUTE_DIRECTORY)
            if expected_directory is not None and is_directory is not expected_directory:
                kind = "directory" if expected_directory else "regular file"
                raise ValueError(f"ACL target must be a {kind}")
        except Exception:
            self.close()
            raise

    def close(self) -> None:
        handle = getattr(self, "value", None)
        if handle:
            if not self._close_handle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
            self.value = None

    def __enter__(self) -> "_AclObjectHandle":
        if not self.value:
            raise RuntimeError("ACL object handle is already closed")
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()


class _DirectoryHandle(_AclObjectHandle):
    def __init__(self, path: str, desired_access: int) -> None:
        super().__init__(path, desired_access, expected_directory=True)


class _FileHandle(_AclObjectHandle):
    def __init__(self, path: str, desired_access: int) -> None:
        super().__init__(path, desired_access, expected_directory=False)


class _NativeSecurity:
    def __init__(self) -> None:
        require_win64()
        self.advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        self.local_free = self.kernel32.LocalFree
        self.local_free.argtypes = [HANDLE]
        self.local_free.restype = HANDLE

        self.convert_sid = self.advapi32.ConvertStringSidToSidW
        self.convert_sid.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(LPVOID)]
        self.convert_sid.restype = ctypes.c_int32

        self.set_entries = self.advapi32.SetEntriesInAclW
        self.set_entries.argtypes = [
            DWORD, ctypes.POINTER(EXPLICIT_ACCESS_W), LPVOID, ctypes.POINTER(LPVOID)
        ]
        self.set_entries.restype = DWORD

        self.get_security = self.advapi32.GetSecurityInfo
        self.get_security.argtypes = [
            HANDLE, DWORD, DWORD, ctypes.POINTER(LPVOID), ctypes.POINTER(LPVOID),
            ctypes.POINTER(LPVOID), ctypes.POINTER(LPVOID), ctypes.POINTER(LPVOID)
        ]
        self.get_security.restype = DWORD

        self.set_security = self.advapi32.SetSecurityInfo
        self.set_security.argtypes = [HANDLE, DWORD, DWORD, LPVOID, LPVOID, LPVOID, LPVOID]
        self.set_security.restype = DWORD

        self.get_acl_info = self.advapi32.GetAclInformation
        self.get_acl_info.argtypes = [LPVOID, LPVOID, DWORD, DWORD]
        self.get_acl_info.restype = ctypes.c_int32

        self.get_ace = self.advapi32.GetAce
        self.get_ace.argtypes = [LPVOID, DWORD, ctypes.POINTER(LPVOID)]
        self.get_ace.restype = ctypes.c_int32

        self.equal_sid = self.advapi32.EqualSid
        self.equal_sid.argtypes = [LPVOID, LPVOID]
        self.equal_sid.restype = ctypes.c_int32

        self.initialize_acl = self.advapi32.InitializeAcl
        self.initialize_acl.argtypes = [LPVOID, DWORD, DWORD]
        self.initialize_acl.restype = ctypes.c_int32

        self.add_mandatory_ace = self.advapi32.AddMandatoryAce
        self.add_mandatory_ace.argtypes = [LPVOID, DWORD, DWORD, DWORD, LPVOID]
        self.add_mandatory_ace.restype = ctypes.c_int32

    def sid_from_string(self, value: str) -> LPVOID:
        sid = LPVOID()
        if not self.convert_sid(value, ctypes.byref(sid)):
            raise ctypes.WinError(ctypes.get_last_error())
        return sid

    def acl_entries(self, acl: LPVOID):
        if not acl:
            raise OSError("refusing to modify a null ACL")
        info = ACL_SIZE_INFORMATION()
        if not self.get_acl_info(
            acl, ctypes.byref(info), ctypes.sizeof(info), ACL_SIZE_INFORMATION_CLASS
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        for index in range(info.AceCount):
            ace = LPVOID()
            if not self.get_ace(acl, index, ctypes.byref(ace)):
                raise ctypes.WinError(ctypes.get_last_error())
            yield ace

    def has_allowed_ace(
        self, acl: LPVOID, sid: LPVOID, required_mask: int,
        required_inheritance_flags: int | None = None,
    ) -> bool:
        for ace_ptr in self.acl_entries(acl):
            ace = ctypes.cast(ace_ptr, ctypes.POINTER(ACCESS_ALLOWED_ACE)).contents
            if ace.Header.AceType != ACCESS_ALLOWED_ACE_TYPE:
                continue
            ace_sid = ctypes.c_void_p(ace_ptr.value + ACCESS_ALLOWED_ACE.SidStart.offset)
            if self.equal_sid(ace_sid, sid) and (ace.Mask & required_mask) == required_mask:
                if required_inheritance_flags is None:
                    return True
                inheritance_mask = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
                if (ace.Header.AceFlags & inheritance_mask) == required_inheritance_flags:
                    return True
        return False

    def has_low_integrity_label(self, acl: LPVOID, low_sid: LPVOID) -> bool:
        for ace_ptr in self.acl_entries(acl):
            ace = ctypes.cast(ace_ptr, ctypes.POINTER(ACCESS_ALLOWED_ACE)).contents
            if ace.Header.AceType != SYSTEM_MANDATORY_LABEL_ACE_TYPE:
                continue
            ace_sid = ctypes.c_void_p(ace_ptr.value + ACCESS_ALLOWED_ACE.SidStart.offset)
            required_flags = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
            if (
                self.equal_sid(ace_sid, low_sid)
                and (ace.Mask & SYSTEM_MANDATORY_LABEL_NO_WRITE_UP)
                    == SYSTEM_MANDATORY_LABEL_NO_WRITE_UP
                and (ace.Header.AceFlags & required_flags) == required_flags
            ):
                return True
        return False


def _read_acl(api: _NativeSecurity, handle: HANDLE, security_info: int):
    owner = LPVOID()
    group = LPVOID()
    dacl = LPVOID()
    sacl = LPVOID()
    descriptor = LPVOID()
    code = api.get_security(
        handle, SE_FILE_OBJECT, security_info,
        ctypes.byref(owner), ctypes.byref(group), ctypes.byref(dacl),
        ctypes.byref(sacl), ctypes.byref(descriptor),
    )
    _raise_winerror(int(code), "GetSecurityInfo")
    return dacl, sacl, descriptor


def _grant_access(
    path: str,
    appcontainer_sid: str,
    access_mask: int,
    *,
    inheritance_flags: int,
    expected_directory: bool,
) -> None:
    if not isinstance(appcontainer_sid, str) or not appcontainer_sid.startswith("S-1-15-2-"):
        raise ValueError("appcontainer_sid must be an AppContainer package SID")

    api = _NativeSecurity()
    sid = api.sid_from_string(appcontainer_sid)
    new_acl = LPVOID()
    try:
        handle_type = _DirectoryHandle if expected_directory else _FileHandle
        with handle_type(path, FILE_READ_ATTRIBUTES | READ_CONTROL | WRITE_DAC) as directory:
            old_dacl, _, descriptor = _read_acl(api, directory.value, DACL_SECURITY_INFORMATION)
            try:
                if not old_dacl:
                    # A null DACL grants everyone full access; do not silently rewrite it.
                    raise OSError("refusing to change an object with a null DACL")
                entry = EXPLICIT_ACCESS_W()
                entry.grfAccessPermissions = access_mask
                entry.grfAccessMode = GRANT_ACCESS
                entry.grfInheritance = inheritance_flags
                entry.Trustee.pMultipleTrustee = None
                entry.Trustee.MultipleTrusteeOperation = 0
                entry.Trustee.TrusteeForm = TRUSTEE_IS_SID
                entry.Trustee.TrusteeType = TRUSTEE_IS_UNKNOWN
                entry.Trustee.ptstrName = ctypes.cast(sid, ctypes.c_wchar_p)
                code = int(api.set_entries(1, ctypes.byref(entry), old_dacl, ctypes.byref(new_acl)))
                _raise_winerror(code, "SetEntriesInAclW")
                if not new_acl:
                    raise OSError("SetEntriesInAclW returned success without an ACL")
                code = int(api.set_security(
                    directory.value, SE_FILE_OBJECT, DACL_SECURITY_INFORMATION,
                    None, None, new_acl, None,
                ))
                _raise_winerror(code, "SetSecurityInfo(DACL)")
                check_dacl, _, check_descriptor = _read_acl(
                    api, directory.value, DACL_SECURITY_INFORMATION
                )
                try:
                    expected_inheritance = inheritance_flags if expected_directory else None
                    if not api.has_allowed_ace(
                        check_dacl, sid, access_mask, expected_inheritance
                    ):
                        raise OSError("AppContainer DACL grant did not survive read-back verification")
                finally:
                    if check_descriptor:
                        api.local_free(check_descriptor)
            finally:
                if descriptor:
                    api.local_free(descriptor)
    finally:
        if new_acl:
            api.local_free(new_acl)
        if sid:
            api.local_free(sid)


MAX_RUNTIME_TREE_ENTRIES: Final[int] = 100000


def _runtime_tree_entries(root: str) -> list[tuple[str, bool]]:
    """Enumerate a pinned runtime tree without following any reparse point."""
    require_win64()
    if not isinstance(root, str) or not root or "\\x00" in root or not os.path.isabs(root):
        raise ValueError("runtime root must be an absolute NUL-free directory path")
    root = os.path.abspath(root)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_attributes = kernel32.GetFileAttributesW
    get_attributes.argtypes = [ctypes.c_wchar_p]
    get_attributes.restype = DWORD

    # Reject reparse points in every ancestor, including the supplied root.
    ancestor = root
    while ancestor:
        ancestor_attributes = int(get_attributes(ancestor))
        if ancestor_attributes == 0xFFFFFFFF:
            raise ctypes.WinError(ctypes.get_last_error())
        if ancestor_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
            raise ValueError(f"runtime path contains a reparse-point ancestor: {ancestor}")
        parent = os.path.dirname(ancestor)
        if parent == ancestor:
            break
        ancestor = parent

    root_attributes = int(get_attributes(root))
    if not (root_attributes & FILE_ATTRIBUTE_DIRECTORY):
        raise ValueError("runtime root must be a directory")
    entries: list[tuple[str, bool]] = [(root, True)]
    pending = [root]

    while pending:
        directory = pending.pop()
        with os.scandir(directory) as iterator:
            children = sorted(iterator, key=lambda entry: entry.name.casefold())
        for child in children:
            child_path = child.path
            attributes = int(get_attributes(child_path))
            if attributes == 0xFFFFFFFF:
                raise ctypes.WinError(ctypes.get_last_error())
            if attributes & FILE_ATTRIBUTE_REPARSE_POINT or child.is_symlink():
                raise ValueError(f"runtime tree contains a reparse point: {child_path}")
            is_directory = bool(attributes & FILE_ATTRIBUTE_DIRECTORY)
            entries.append((child_path, is_directory))
            if is_directory:
                pending.append(child_path)
            if len(entries) > MAX_RUNTIME_TREE_ENTRIES:
                raise ValueError("runtime tree exceeds the configured entry ceiling")

    # Parent directories are secured before descendants; each existing file
    # receives a direct non-inheritable ACE, while directories also propagate.
    entries.sort(key=lambda item: (item[0].count(os.sep), item[0].casefold()))
    return entries


def grant_runtime_read_execute(path: str, appcontainer_sid: str) -> None:
    """Grant read/execute to every existing runtime object, rejecting reparse points."""
    entries = _runtime_tree_entries(path)
    access_mask = GENERIC_READ_FILE | GENERIC_EXECUTE_FILE
    for entry_path, is_directory in entries:
        _grant_access(
            entry_path,
            appcontainer_sid,
            access_mask,
            inheritance_flags=(
                OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE if is_directory else 0
            ),
            expected_directory=is_directory,
        )


def grant_temp_read_write(path: str, appcontainer_sid: str) -> None:
    """Grant the worker package SID read/write (not execute) access below path."""
    _grant_access(
        path,
        appcontainer_sid,
        GENERIC_READ_FILE | GENERIC_WRITE_FILE,
        inheritance_flags=OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE,
        expected_directory=True,
    )


def apply_low_integrity_no_write_up(path: str) -> None:
    """Set Low Integrity on a per-run temp directory and its descendants.

    LABEL_SECURITY_INFORMATION targets the mandatory label only; this deliberately
    avoids replacing the object's audit SACL or requiring SE_SECURITY_NAME.
    """
    api = _NativeSecurity()
    low_sid = api.sid_from_string(LOW_INTEGRITY_SID)
    acl_buffer = ctypes.create_string_buffer(1024)
    try:
        if not api.initialize_acl(acl_buffer, ctypes.sizeof(acl_buffer), ACL_REVISION):
            raise ctypes.WinError(ctypes.get_last_error())
        inherit = OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE
        if not api.add_mandatory_ace(
            acl_buffer, ACL_REVISION, inherit,
            SYSTEM_MANDATORY_LABEL_NO_WRITE_UP, low_sid,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        with _DirectoryHandle(path, FILE_READ_ATTRIBUTES | READ_CONTROL | WRITE_OWNER) as directory:
            code = int(api.set_security(
                directory.value, SE_FILE_OBJECT, LABEL_SECURITY_INFORMATION,
                None, None, None, ctypes.cast(acl_buffer, LPVOID),
            ))
            _raise_winerror(code, "SetSecurityInfo(LABEL)")
            _, check_sacl, check_descriptor = _read_acl(
                api, directory.value, LABEL_SECURITY_INFORMATION
            )
            try:
                if not api.has_low_integrity_label(check_sacl, low_sid):
                    raise OSError("Low Integrity label did not survive read-back verification")
            finally:
                if check_descriptor:
                    api.local_free(check_descriptor)
    finally:
        if low_sid:
            api.local_free(low_sid)
