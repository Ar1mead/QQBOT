import os
import unittest

from adapters.worker_backends import windows_appcontainer as win
from adapters.worker_backends import windows_job as job


class WindowsWorkerJobTests(unittest.TestCase):
    def test_limits_reject_unbounded_or_invalid_values_before_native_calls(self):
        invalid = [
            (True, 2000),
            (16 * 1024 * 1024, 2000),
            (9 * 1024 * 1024 * 1024, 2000),
            (64 * 1024 * 1024, True),
            (64 * 1024 * 1024, 0),
            (64 * 1024 * 1024, 10001),
        ]
        for memory, cpu in invalid:
            with self.subTest(memory=memory, cpu=cpu):
                with self.assertRaises(ValueError):
                    job.create_worker_job(memory, cpu)

    def test_job_policy_constants_require_single_process_and_no_breakaway(self):
        self.assertEqual(job.REQUIRED_LIMIT_FLAGS, 0x00002308)
        self.assertEqual(job.FORBIDDEN_BREAKAWAY_FLAGS, 0x00001800)
        self.assertEqual(job.MAX_CPU_RATE_10000, 10000)

    @unittest.skipUnless(os.name == "nt", "Windows Job Object APIs")
    def test_windows_job_object_policy_is_applied_and_read_back(self):
        memory_limit = 64 * 1024 * 1024
        cpu_rate = 2500
        with job.create_worker_job(memory_limit, cpu_rate) as worker_job:
            actual = worker_job.query_configuration()
            self.assertEqual(
                actual["limit_flags"] & job.REQUIRED_LIMIT_FLAGS,
                job.REQUIRED_LIMIT_FLAGS,
            )
            self.assertEqual(
                actual["limit_flags"] & job.FORBIDDEN_BREAKAWAY_FLAGS,
                0,
            )
            self.assertEqual(actual["active_process_limit"], 1)
            self.assertEqual(actual["process_memory_limit"], memory_limit)
            self.assertEqual(actual["job_memory_limit"], memory_limit)
            self.assertEqual(
                actual["cpu_control_flags"],
                win.JOB_OBJECT_CPU_RATE_CONTROL_ENABLE
                | win.JOB_OBJECT_CPU_RATE_CONTROL_HARD_CAP,
            )
            self.assertEqual(actual["cpu_rate_10000"], cpu_rate)
        with self.assertRaisesRegex(RuntimeError, "already closed"):
            worker_job.query_configuration()

    def test_non_windows_valid_configuration_fails_closed(self):
        if os.name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            job.create_worker_job(64 * 1024 * 1024, 2000)


if __name__ == "__main__":
    unittest.main()
