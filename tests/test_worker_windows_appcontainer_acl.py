import os
import tempfile
import unittest

from adapters.worker_backends import windows_acl as acl
from adapters.worker_backends import windows_appcontainer as win


class WindowsAppContainerAclLayoutTests(unittest.TestCase):
    def test_win64_acl_structure_sizes_match_documented_abi(self):
        if __import__("ctypes").sizeof(__import__("ctypes").c_void_p) != 8:
            self.skipTest("initial backend targets Win64")
        acl.assert_win64_acl_structure_layouts()

    def test_access_profiles_are_narrow_and_low_label_is_write_up_only(self):
        self.assertEqual(acl.GENERIC_READ_FILE, 0x00120089)
        self.assertEqual(acl.GENERIC_WRITE_FILE, 0x00120116)
        self.assertEqual(acl.GENERIC_EXECUTE_FILE, 0x001200A0)
        self.assertEqual(
            acl.GENERIC_READ_FILE | acl.GENERIC_EXECUTE_FILE,
            0x00120089 | 0x001200A0,
        )
        self.assertEqual(
            acl.SYSTEM_MANDATORY_LABEL_NO_WRITE_UP,
            0x00000001,
        )
        self.assertEqual(acl.LOW_INTEGRITY_SID, "S-1-16-4096")

    @unittest.skipUnless(os.name == "nt", "Windows ACL APIs")
    def test_runtime_and_temp_directory_acl_and_temp_low_label(self):
        sid = win.ensure_appcontainer_profile_sid("Ar1mead.QQBOT.Worker.CI")
        with tempfile.TemporaryDirectory(prefix="qqbot-worker-acl-") as root:
            runtime = os.path.join(root, "runtime")
            scratch = os.path.join(root, "scratch")
            os.mkdir(runtime)
            os.mkdir(scratch)

            acl.grant_runtime_read_execute(runtime, sid)
            acl.grant_temp_read_write(scratch, sid)
            acl.apply_low_integrity_no_write_up(scratch)

            # The helpers perform handle-based read-back checks for the exact
            # package SID, required access mask, inheritance flags, and label.
            self.assertTrue(os.path.isdir(runtime))
            self.assertTrue(os.path.isdir(scratch))

    def test_non_windows_acl_operations_fail_closed(self):
        if os.name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            acl.grant_runtime_read_execute("/tmp/runtime", "S-1-15-2-1-2-3-4-5-6-7")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            acl.apply_low_integrity_no_write_up("/tmp/scratch")


if __name__ == "__main__":
    unittest.main()
