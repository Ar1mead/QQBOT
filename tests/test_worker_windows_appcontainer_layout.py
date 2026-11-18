import ctypes
import unittest

from adapters.worker_backends import windows_appcontainer as win


class WindowsAppContainerLayoutTests(unittest.TestCase):
    def test_win64_structure_sizes_match_documented_abi(self):
        if ctypes.sizeof(ctypes.c_void_p) != 8:
            self.skipTest("initial backend targets Win64")
        win.assert_win64_structure_layouts()

    def test_security_capabilities_support_empty_capability_list(self):
        caps = win.SECURITY_CAPABILITIES()
        self.assertEqual(caps.CapabilityCount, 0)
        self.assertFalse(bool(caps.Capabilities))

    def test_required_job_limits_are_explicit_constants(self):
        self.assertTrue(win.JOB_OBJECT_LIMIT_ACTIVE_PROCESS)
        self.assertTrue(win.JOB_OBJECT_LIMIT_PROCESS_MEMORY)
        self.assertTrue(win.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE)
        self.assertFalse(hasattr(win, "JOB_OBJECT_LIMIT_BREAKAWAY_OK"))

    def test_platform_guard_rejects_non_windows(self):
        if __import__("os").name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            win.require_win64()


if __name__ == "__main__":
    unittest.main()
