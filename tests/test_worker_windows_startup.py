import ctypes
import os
import unittest

from adapters.worker_backends import windows_appcontainer as win
from adapters.worker_backends import windows_startup as startup


@unittest.skipUnless(os.name == "nt", "Windows process attribute-list APIs")
class WindowsStartupAttributeTests(unittest.TestCase):
    def setUp(self):
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel32.CreateEventW.argtypes = [
            ctypes.POINTER(win.SECURITY_ATTRIBUTES),
            win.BOOL,
            win.BOOL,
            ctypes.c_wchar_p,
        ]
        self.kernel32.CreateEventW.restype = win.HANDLE
        self.kernel32.CloseHandle.argtypes = [win.HANDLE]
        self.kernel32.CloseHandle.restype = win.BOOL

    def _event_handle(self, inheritable):
        security = win.SECURITY_ATTRIBUTES()
        security.nLength = ctypes.sizeof(security)
        security.lpSecurityDescriptor = None
        security.bInheritHandle = bool(inheritable)
        handle = self.kernel32.CreateEventW(
            ctypes.byref(security), False, False, None
        )
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        return handle

    def test_attribute_list_contains_only_handle_allowlist_and_empty_appcontainer(self):
        sid = win.ensure_appcontainer_profile_sid("Ar1mead.QQBOT.Worker.CI")
        handle = self._event_handle(True)
        try:
            with win.EmptyAppContainerCapabilities(sid) as caps:
                with startup.WorkerStartupAttributes(caps, [handle]) as attributes:
                    attributes.validate_live()
                    self.assertEqual(
                        attributes.value.StartupInfo.cb,
                        ctypes.sizeof(win.STARTUPINFOEX),
                    )
                    self.assertTrue(bool(attributes.value.lpAttributeList))
                    self.assertEqual(caps.value.CapabilityCount, 0)
                with self.assertRaisesRegex(RuntimeError, "already closed"):
                    attributes.validate_live()
        finally:
            self.kernel32.CloseHandle(handle)

    def test_noninheritable_and_duplicate_handles_are_rejected(self):
        sid = win.ensure_appcontainer_profile_sid("Ar1mead.QQBOT.Worker.CI")
        handle = self._event_handle(False)
        inheritable = self._event_handle(True)
        try:
            with win.EmptyAppContainerCapabilities(sid) as caps:
                with self.assertRaisesRegex(ValueError, "HANDLE_FLAG_INHERIT"):
                    startup.WorkerStartupAttributes(caps, [handle])
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    startup.WorkerStartupAttributes(caps, [inheritable, inheritable])
        finally:
            self.kernel32.CloseHandle(handle)
            self.kernel32.CloseHandle(inheritable)


class StartupAttributeValidationTests(unittest.TestCase):
    def test_handle_list_rejects_invalid_values_and_excess_handles(self):
        for handles in ([], [0], [-1], [True], [1, 1], [1, 2, 3, 4]):
            with self.subTest(handles=handles):
                with self.assertRaises((TypeError, ValueError)):
                    startup._normalize_handles(handles)

    def test_non_windows_startup_attribute_creation_fails_closed(self):
        if os.name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            startup.WorkerStartupAttributes(None, [1])


if __name__ == "__main__":
    unittest.main()
