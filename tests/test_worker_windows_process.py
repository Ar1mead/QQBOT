import os
import socket
import tempfile
import threading
import unittest
from contextlib import contextmanager

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
    @contextmanager
    def _worker_session(self, arguments, application_name="cmd.exe"):
        system_root = os.environ["SystemRoot"]
        system32 = os.path.join(system_root, "System32")
        application = os.path.join(system32, application_name)
        temp_parent = os.path.join(system_root, "Temp")
        os.makedirs(temp_parent, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="qqbot-worker-", dir=temp_parent) as worker_temp:
            sid = app.ensure_appcontainer_profile_sid("Ar1mead.QQBOT.Worker.CI")
            acl.grant_temp_read_write(worker_temp, sid)
            acl.apply_low_integrity_no_write_up(worker_temp)
            worker_env = environment.build_worker_environment(
                {
                    "SystemRoot": system_root,
                    "WINDIR": system_root,
                    "LOCALAPPDATA": app.get_appcontainer_folder_path(sid),
                    "TEMP": worker_temp,
                    "TMP": worker_temp,
                    "PATH": system32,
                }
            )

            with pipes.WorkerPipes.create() as worker_pipes:
                with app.EmptyAppContainerCapabilities(sid) as capabilities:
                    with startup.WorkerStartupAttributes(
                        capabilities, worker_pipes.child_handles_for_startup()
                    ) as startup_attributes:
                        with job.create_worker_job(128 * 1024 * 1024, 10000) as worker_job:
                            with process.launch_appcontainer_worker(
                                application_path=application,
                                arguments=arguments,
                                current_directory=worker_temp,
                                environment=worker_env,
                                pipes=worker_pipes,
                                startup=startup_attributes,
                                job=worker_job,
                            ) as worker:
                                yield worker, worker_pipes, worker_job, worker_temp

    def _execute(self, worker, worker_pipes, worker_job, timeout_ms=10000, stdout_limit=4096):
        return worker_io.execute_worker_stdio(
            worker=worker,
            pipes=worker_pipes,
            job=worker_job,
            request_bytes=b"bounded worker probe input\r\n",
            timeout_ms=timeout_ms,
            stdout_limit=stdout_limit,
            stderr_limit=4096,
        )

    def test_worker_is_created_suspended_assigned_then_resumed_with_bounded_stdio(self):
        with self._worker_session(["/d", "/c", "set /p _= & echo WORKER_OK"]) as (worker, worker_pipes, worker_job, worker_temp):
            result = self._execute(worker, worker_pipes, worker_job)
            self.assertEqual(result.exit_code, 0)
            self.assertIn(b"WORKER_OK", result.stdout)
            self.assertEqual(result.stderr, b"")
            self.assertTrue(
                worker_job.query_configuration()["limit_flags"]
                & job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            )

    def test_stdout_overflow_terminates_the_worker_job(self):
        command = "set /p _= & for /l %i in (1,0,2) do @echo OVERFLOW"
        with self._worker_session(["/d", "/c", command]) as (worker, worker_pipes, worker_job, worker_temp):
            with self.assertRaises(worker_io.WorkerOutputLimitError):
                self._execute(worker, worker_pipes, worker_job, stdout_limit=128)
            self.assertTrue(worker.wait(5000), "overflow did not terminate the worker")

    def test_timeout_terminates_the_worker_job(self):
        command = "set /p _= & for /l %i in (1,1,2147483647) do @rem"
        with self._worker_session(["/d", "/c", command]) as (worker, worker_pipes, worker_job, worker_temp):
            with self.assertRaises(worker_io.WorkerTimeoutError):
                self._execute(worker, worker_pipes, worker_job, timeout_ms=250)
            self.assertTrue(worker.wait(5000), "timeout did not terminate the worker")

    def test_host_secret_and_csd_marker_files_are_not_readable(self):
        with tempfile.TemporaryDirectory(prefix="qqbot-host-secret-") as host_temp:
            secret_path = os.path.join(host_temp, "host-secret.txt")
            fd, csd_path = tempfile.mkstemp(prefix="worker-csd-marker-", suffix=".tmp", dir=os.getcwd())
            os.close(fd)
            with open(secret_path, "w", encoding="utf-8") as stream:
                stream.write("HOST_SECRET_MARKER")
            with open(csd_path, "w", encoding="utf-8") as stream:
                stream.write("CSD_DATABASE_MARKER")
            try:
                with self._worker_session(
                    ["/d", "/c", f"set /p _= & type {secret_path} {csd_path}"]
                ) as (worker, worker_pipes, worker_job, worker_temp):
                    result = self._execute(worker, worker_pipes, worker_job)
                    self.assertNotIn(b"HOST_SECRET_MARKER", result.stdout)
                    self.assertNotIn(b"CSD_DATABASE_MARKER", result.stdout)
                    self.assertNotEqual(result.exit_code, 0)
            finally:
                try:
                    os.unlink(secret_path)
                except FileNotFoundError:
                    pass
                try:
                    os.unlink(csd_path)
                except FileNotFoundError:
                    pass



    def test_closing_job_object_kills_the_running_worker(self):
        command = "set /p _= & for /l %i in (1,1,2147483647) do @rem"
        with self._worker_session(["/d", "/c", command]) as (
            worker, worker_pipes, worker_job, worker_temp
        ):
            self.assertTrue(worker.handle)
            worker_job.close()
            self.assertFalse(worker_job.handle)
            self.assertTrue(worker.wait(5000), "kill-on-close did not terminate the worker")

    def test_worker_can_write_inside_temp_but_not_host_temp(self):
        with tempfile.TemporaryDirectory(prefix="qqbot-host-write-") as host_temp:
            outside_path = os.path.join(host_temp, "blocked-write.txt")
            command = (
                "set /p _= & "
                f"echo OUTSIDE_WRITE_MARKER > {outside_path} & "
                "echo TEMP_WRITE_MARKER > worker-write-test.txt"
            )
            with self._worker_session(["/d", "/c", command]) as (
                worker, worker_pipes, worker_job, worker_temp
            ):
                result = self._execute(worker, worker_pipes, worker_job)
                self.assertEqual(result.exit_code, 0)
                self.assertFalse(os.path.exists(outside_path))
                inside_path = os.path.join(worker_temp, "worker-write-test.txt")
                self.assertTrue(os.path.isfile(inside_path))
                with open(inside_path, "r", encoding="utf-8") as stream:
                    self.assertIn("TEMP_WRITE_MARKER", stream.read())

    def test_appcontainer_cannot_connect_to_host_loopback_listener(self):
        system_root = os.environ["SystemRoot"]
        curl_path = os.path.join(system_root, "System32", "curl.exe")
        if not os.path.isfile(curl_path):
            self.skipTest("curl.exe is unavailable on this Windows runner")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(3)
        port = listener.getsockname()[1]
        accepted = []

        def serve_once():
            try:
                connection, _ = listener.accept()
                with connection:
                    accepted.append(True)
                    connection.sendall(b"NETWORK_ALLOWED_MARKER")
            except OSError:
                pass

        server = threading.Thread(target=serve_once, name="worker-loopback-test-server", daemon=True)
        server.start()
        try:
            with self._worker_session(
                ["--max-time", "2", "--silent", "--show-error", "--data-binary", "@-", f"http://127.0.0.1:{port}/"],
                application_name="curl.exe",
            ) as (worker, worker_pipes, worker_job, worker_temp):
                result = self._execute(worker, worker_pipes, worker_job, timeout_ms=8000)
                self.assertNotEqual(result.exit_code, 0)
                self.assertNotIn(b"NETWORK_ALLOWED_MARKER", result.stdout)
                self.assertNotIn(b"NETWORK_ALLOWED_MARKER", result.stderr)
        finally:
            listener.close()
            server.join(timeout=4)
        self.assertFalse(accepted, "AppContainer unexpectedly connected to host loopback")

    def test_job_active_process_limit_blocks_child_process_creation(self):
        command = 'set /p _= & start /b cmd.exe /d /c echo CHILD_PROCESS_MARKER'
        with self._worker_session(["/d", "/c", command]) as (worker, worker_pipes, worker_job, worker_temp):
            result = self._execute(worker, worker_pipes, worker_job)
            self.assertNotIn(b"CHILD_PROCESS_MARKER", result.stdout)
            self.assertEqual(worker_job.query_configuration()["active_process_limit"], 1)


if __name__ == "__main__":
    unittest.main()
