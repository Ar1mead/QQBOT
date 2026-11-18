import ctypes
import os
import unittest
from unittest.mock import patch

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
        with win.EmptyAppContainerCapabilities(sid) as capabilities:
            self.assertEqual(capabilities.value.CapabilityCount, 0)
            self.assertFalse(bool(capabilities.value.Capabilities))
            self.assertTrue(bool(capabilities.value.AppContainerSid))
        with self.assertRaisesRegex(RuntimeError, "already closed"):
            capabilities.__enter__()


    @unittest.skipUnless(os.name == "nt", "Windows AppContainer API")
    def test_profile_local_appdata_path_is_returned_by_userenv(self):
        sid = win.ensure_appcontainer_profile_sid("Ar1mead.QQBOT.Worker.CI")
        path = win.get_appcontainer_folder_path(sid)
        self.assertTrue(os.path.isabs(path))
        self.assertTrue(os.path.isdir(path))



    def test_delete_profile_retries_once_after_documented_indeterminate_failure(self):
        class FakeDelete:
            def __init__(self, results):
                self.results = list(results)
                self.calls = []

            def __call__(self, name):
                self.calls.append(name)
                return self.results.pop(0)

        class FakeUserEnv:
            pass

        fake_delete = FakeDelete([0x80004005, 0])
        fake_userenv = FakeUserEnv()
        fake_userenv.DeleteAppContainerProfile = fake_delete
        with patch.object(win, "_windows_userenv", return_value=fake_userenv):
            win._delete_appcontainer_profile("QQBOT.Worker.test")
        self.assertEqual(fake_delete.calls, ["QQBOT.Worker.test", "QQBOT.Worker.test"])

    def test_delete_profile_fails_closed_after_two_failed_attempts(self):
        class FakeDelete:
            def __init__(self):
                self.calls = 0

            def __call__(self, name):
                self.calls += 1
                return 0x80004005

        class FakeUserEnv:
            pass

        fake_delete = FakeDelete()
        fake_userenv = FakeUserEnv()
        fake_userenv.DeleteAppContainerProfile = fake_delete
        with patch.object(win, "_windows_userenv", return_value=fake_userenv):
            with self.assertRaisesRegex(OSError, "failed twice"):
                win._delete_appcontainer_profile("QQBOT.Worker.test")
        self.assertEqual(fake_delete.calls, 2)

    @unittest.skipUnless(os.name == "nt", "Windows AppContainer profile lifecycle")
    def test_ephemeral_profile_is_unique_and_deleted_on_close(self):
        first = win.EphemeralAppContainerProfile.create()
        first_name = first.profile_name
        first_sid = first.appcontainer_sid
        first_path = first.local_appdata_path
        self.assertTrue(first_name.startswith("QQBOT.Worker."))
        self.assertTrue(os.path.isdir(first_path))
        self.assertTrue(first_sid.startswith("S-1-15-2-"))
        first.close()
        self.assertTrue(first._closed)
        self.assertFalse(os.path.exists(first_path))
        with self.assertRaisesRegex(RuntimeError, "already closed"):
            first.__enter__()

        with win.EphemeralAppContainerProfile.create() as second:
            self.assertNotEqual(second.profile_name, first_name)
            self.assertNotEqual(second.appcontainer_sid, first_sid)
            self.assertTrue(os.path.isdir(second.local_appdata_path))

    def test_platform_guard_rejects_non_windows(self):
        if __import__("os").name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            win.require_win64()


if __name__ == "__main__":
    unittest.main()
