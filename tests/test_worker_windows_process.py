import os
import tempfile
import unittest

from adapters.worker_backends import windows_appcontainer as app
from adapters.worker_backends import windows_acl as acl
from adapters.worker_backends import windows_environment as environment
from adapters.worker_backends import windows_job as job
from adapters.worker_backends import windows_pipes as pipes
from adapters.worker_backends import windows_process as process
from adapters.worker_backends import windows_startup as startup
from adapters.worker_backends import windows_worker_io as worker_io


class WorkerIOValidationTests(unittest.TestCase):
    def test_rejects_invalid_request_and_limits_before_native_calls(self):
        invalid = [
            (b"", 1000, 100, 100),
            (b"x" * (worker_io.MAX_REQUEST_BYTES + 1), 1000, 100, 100),
            (b"x", True, 100, 100),
            (b"x", 0, 100, 100),
            (b"x", worker_io.MAX_TIMEOUT_MS + 1, 100, 100),
            (b"x", 1000, 0, 100),
            (b"x", 1000, 100, worker_io.MAX_STDERR_BYTES + 1),
        ]
        for args in invalid:
            with self.subTest(args=(len(args[0]), *args[1:])):
                with self.assertRaises(ValueError):
                    worker_io._validate_limits(*args)
        with self.assertRaises(TypeError):
            worker_io._validate_limits(bytearray(b"x"), 1000, 100, 100)

    def test_non_windows_stdio_execution_fails_closed(self):
        if os.name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            worker_io.execute_worker_stdio(
                worker=None,
                pipes=None,
                job=None,
                request_bytes=b"{}",
            )


@unittest.skipUnless(os.name == "nt", "Windows AppContainer process launch")
class WindowsAppContainerProcessLaunchTests(unittest.TestCase):
    def _prepare(self, worker_temp):
        system_root = os.environ["SystemRoot"]
        sid = app.ensure_appcontainer_profile_sid("Ar1mead.QQBOT.Worker.CI")
        acl.grant_temp_read_write(worker_temp, sid)
        acl.apply_low_integrity_no_write_up(worker_temp)
        env = environment.build_worker_environment(
            {
                "SystemRoot": system_root,
                "WINDIR": system_root,
                "LOCALAPPDATA": app.get_appcontainer_folder_path(sid),
                "TEMP": worker_temp,
                "TMP": worker_temp,
                "PATH": os.path.join(system_root, "System32"),
            }
        )
        return system_root, sid, env

    def _launch(self, worker_temp, arguments):
        system_root, sid, worker_env = self._prepare(worker_temp)
        application = os.path.join(system_root, "System32", "cmd.exe")
        worker_pipes = pipes.WorkerPipes.create()
        capabilities = app.EmptyAppContainerCapabilities(sid)
        startup_attributes = startup.WorkerStartupAttributes(
            capabilities, worker_pipes.child_handles_for_startup()
        )
        worker_job = job.create_worker_job(128 * 1024 * 1024, 10000)
        worker = process.launch_appcontainer_worker(
            application_path=application,
            arguments=arguments,
            current_directory=worker_temp,
            environment=worker_env,
            pipes=worker_pipes,
            startup=startup_attributes,
            job=worker_job,
        )
        return worker_pipes, capabilities, startup_attributes, worker_job, worker

    def test_worker_is_created_suspended_assigned_then_resumed_with_bounded_stdio(self):
        system_root = os.environ["SystemRoot"]
        temp_parent = os.path.join(system_root, "Temp")
        os.makedirs(temp_parent, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="qqbot-worker-", dir=temp_parent) as worker_temp:
            worker_pipes, capabilities, startup_attributes, worker_job, worker = self._launch(
                worker_temp, ["/d", "/c", "echo", "WORKER_OK"]
            )
            try:
                with worker:
                    result = worker_io.execute_worker_stdio(
                        worker=worker,
                        pipes=worker_pipes,
                        job=worker_job,
                        request_bytes=b"bounded test input\r\n",
                        timeout_ms=10000,
                        stdout_limit=4096,
                        stderr_limit=4096,
                    )
                    self.assertEqual(result.exit_code, 0)
                    self.assertIn(b"WORKER_OK", result.stdout)
                    self.assertEqual(result.stderr, b"")
                    self.assertTrue(
                        worker_job.query_configuration()["limit_flags"]
                        & job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                    )
            finally:
                worker_pipes.close()
                startup_attributes.close()
                capabilities.close()
                worker_job.close()

    def test_stdout_overflow_terminates_the_worker_job(self):
        system_root = os.environ["SystemRoot"]
        temp_parent = os.path.join(system_root, "Temp")
        os.makedirs(temp_parent, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="qqbot-worker-overflow-", dir=temp_parent) as worker_temp:
            worker_pipes, capabilities, startup_attributes, worker_job, worker = self._launch(
                worker_temp,
                ["/d", "/c", "for /l %i in (1,0,2) do @echo OVERFLOW"],
            )
            try:
                with worker:
                    with self.assertRaises(worker_io.WorkerOutputLimitError):
                        worker_io.execute_worker_stdio(
                            worker=worker,
                            pipes=worker_pipes,
                            job=worker_job,
                            request_bytes=b"ignored input\r\n",
                            timeout_ms=10000,
                            stdout_limit=128,
                            stderr_limit=1024,
                        )
                    self.assertTrue(worker.wait(5000), "overflow did not terminate the worker")
            finally:
                worker_pipes.close()
                startup_attributes.close()
                capabilities.close()
                worker_job.close()


if __name__ == "__main__":
    unittest.main()
