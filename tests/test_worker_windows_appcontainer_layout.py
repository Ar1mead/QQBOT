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
        forbidden_breakaway = 0x00000800 | 0x00001000
        required = win.JOB_OBJECT_LIMIT_ACTIVE_PROCESS | win.JOB_OBJECT_LIMIT_PROCESS_MEMORY | win.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        self.assertEqual(required, 0x00002108)
        self.assertEqual(required & forbidden_breakaway, 0)


    def test_profile_name_validation_is_strict(self):
        for value in ("", "bad/name", "x" * 65):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    win.ensure_appcontainer_profile_sid(value)

    @unittest.skipUnless(__import__("os").name == "nt", "Windows AppContainer API")
    def test_windows_can_create_or_reuse_a_dedicated_profile(self):
        sid = win.ensure_appcontainer_profile_sid("Ar1mead.QQBOT.Worker.CI")
        self.assertRegex(sid, r"^S-1-15-2-(?:[0-9]+-){6}[0-9]+$")
        # Do not delete a profile that may have pre-existed this test.
        self.assertEqual(
            sid,
            win.ensure_appcontainer_profile_sid("Ar1mead.QQBOT.Worker.CI"),
        )

    def test_platform_guard_rejects_non_windows(self):
        if __import__("os").name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            win.require_win64()


if __name__ == "__main__":
    unittest.main()
