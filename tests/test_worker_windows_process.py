import ipaddress
import json
import os
import shutil
import socket
import tempfile
import sys
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
    def _worker_session(self, arguments, application_name="cmd.exe", runtime_builder=None):
        system_root = os.environ["SystemRoot"]
        system32 = os.path.join(system_root, "System32")
        temp_parent = os.path.join(system_root, "Temp")
        os.makedirs(temp_parent, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="qqbot-worker-", dir=temp_parent) as worker_temp:
            with tempfile.TemporaryDirectory(prefix="qqbot-runtime-", dir=temp_parent) as runtime_temp:
                with app.EphemeralAppContainerProfile.create() as profile:
                    sid = profile.appcontainer_sid
                    if runtime_builder is not None:
                        application = runtime_builder(runtime_temp)
                        acl.grant_runtime_read_execute(runtime_temp, sid)
                    elif application_name == "cmd.exe":
                        application = os.path.join(runtime_temp, application_name)
                        shutil.copy2(os.path.join(system32, application_name), application)
                        acl.grant_runtime_read_execute(runtime_temp, sid)
                    else:
                        application = os.path.join(system32, application_name)
                    if callable(arguments):
                        arguments = arguments(worker_temp, runtime_temp)
                    acl.grant_temp_read_write(worker_temp, sid)
                    acl.apply_low_integrity_no_write_up(worker_temp)
                    worker_env = environment.build_worker_environment(
                        {
                            "SystemRoot": system_root,
                            "WINDIR": system_root,
                            "LOCALAPPDATA": profile.local_appdata_path,
                            "TEMP": worker_temp,
                            "TMP": worker_temp,
                            "PATH": system32 + os.pathsep + runtime_temp,
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
                                        yield worker, worker_pipes, worker_job, worker_temp, runtime_temp

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


    def test_isolated_python_runtime_imports_stdlib_and_respects_readonly_boundary(self):
        def build_runtime(runtime_temp):
            source_root = os.path.realpath(sys.base_prefix)
            source_executable = os.path.realpath(getattr(sys, "_base_executable", sys.executable))
            if not os.path.isfile(source_executable):
                raise AssertionError("base Python executable is unavailable")
            shutil.copy2(source_executable, os.path.join(runtime_temp, "python.exe"))

            for name in os.listdir(source_root):
                source = os.path.join(source_root, name)
                if os.path.isfile(source) and name.lower().endswith(".dll"):
                    shutil.copy2(source, os.path.join(runtime_temp, name))

            for directory in ("Lib", "DLLs"):
                source = os.path.join(source_root, directory)
                if not os.path.isdir(source):
                    raise AssertionError(f"Python runtime is missing {directory}")
                shutil.copytree(
                    source,
                    os.path.join(runtime_temp, directory),
                    ignore=shutil.ignore_patterns("__pycache__", "site-packages", "test", "tests"),
                )

            version_tag = f"python{sys.version_info.major}{sys.version_info.minor}"
            for name in os.listdir(source_root):
                if name.lower() in {f"{version_tag}.zip", f"{version_tag}._pth"}:
                    source = os.path.join(source_root, name)
                    if os.path.isfile(source):
                        shutil.copy2(source, os.path.join(runtime_temp, name))
            return os.path.join(runtime_temp, "python.exe")

        script = r'''
import json, os, pathlib, sqlite3, ssl, sys
request = sys.stdin.buffer.readline()
runtime_root = pathlib.Path(sys.executable).resolve().parent
runtime_probe = runtime_root / "_worker_runtime_write_probe"
worker_temp = pathlib.Path(sys.argv[1])
worker_temp_probe = worker_temp / "python-worker-temp-probe.txt"
temp_env_root = pathlib.Path(os.environ["TEMP"])
local_appdata_root = pathlib.Path(os.environ["LOCALAPPDATA"])
temp_env_root.mkdir(parents=True, exist_ok=True)
temp_env_probe = temp_env_root / "python-appcontainer-temp-probe.txt"
try:
    runtime_probe.write_text("must not be writable", encoding="utf-8")
    runtime_write_denied = False
except OSError:
    runtime_write_denied = True
worker_temp_probe.write_text("WORKER_TEMP_WRITE_OK", encoding="utf-8")
temp_env_probe.write_text("APP_CONTAINER_TEMP_WRITE_OK", encoding="utf-8")
temp_env_norm = os.path.normcase(os.path.realpath(str(temp_env_root)))
local_appdata_norm = os.path.normcase(os.path.realpath(str(local_appdata_root)))
try:
    temp_env_within_localappdata = os.path.commonpath((local_appdata_norm, temp_env_norm)) == local_appdata_norm
except ValueError:
    temp_env_within_localappdata = False
with sqlite3.connect(":memory:") as connection:
    connection.execute("select 1").fetchone()
root = os.path.normcase(os.path.realpath(str(runtime_root)))
outside_paths = []
for item in sys.path:
    if not item:
        outside_paths.append(item)
        continue
    candidate = os.path.normcase(os.path.realpath(item))
    try:
        if os.path.commonpath((root, candidate)) != root:
            outside_paths.append(item)
    except ValueError:
        outside_paths.append(item)
print(json.dumps({
    "request_ok": request == b"bounded worker probe input\r\n",
    "python_version": list(sys.version_info[:3]),
    "isolated": sys.flags.isolated,
    "no_site": sys.flags.no_site,
    "dont_write_bytecode": sys.flags.dont_write_bytecode,
    "site_loaded": "site" in sys.modules,
    "ssl_available": bool(ssl.OPENSSL_VERSION),
    "sqlite_available": True,
    "runtime_write_denied": runtime_write_denied,
    "worker_temp_write_ok": worker_temp_probe.read_text(encoding="utf-8") == "WORKER_TEMP_WRITE_OK",
    "temp_env_write_ok": temp_env_probe.read_text(encoding="utf-8") == "APP_CONTAINER_TEMP_WRITE_OK",
    "temp_env_within_localappdata": temp_env_within_localappdata,
    "parent_secret_absent": os.environ.get("QQBOT_PARENT_SECRET") is None,
    "outside_sys_path": outside_paths,
}, sort_keys=True))
'''
        print("Host-positive TCP network probe targets:", host_targets)

        secret_name = "QQBOT_PARENT_SECRET"
        previous_secret = os.environ.get(secret_name)
        os.environ[secret_name] = "HOST_ONLY_SECRET_MARKER"
        try:
            with self._worker_session(
                lambda worker_temp, runtime_temp: ["-I", "-S", "-B", "-c", script, worker_temp],
                runtime_builder=build_runtime,
            ) as (worker, worker_pipes, worker_job, worker_temp, runtime_temp):
                result = self._execute(worker, worker_pipes, worker_job, timeout_ms=30000)
                self.assertEqual(result.exit_code, 0, result.stderr.decode("utf-8", errors="replace"))
                payload = json.loads(result.stdout.decode("utf-8").strip())
                self.assertTrue(payload["request_ok"])
                self.assertEqual(payload["python_version"][:2], list(sys.version_info[:2]))
                self.assertEqual(payload["isolated"], 1)
                self.assertEqual(payload["no_site"], 1)
                self.assertEqual(payload["dont_write_bytecode"], 1)
                self.assertFalse(payload["site_loaded"])
                self.assertTrue(payload["ssl_available"])
                self.assertTrue(payload["sqlite_available"])
                self.assertTrue(payload["runtime_write_denied"])
                self.assertTrue(payload["worker_temp_write_ok"])
                self.assertTrue(payload["temp_env_write_ok"])
                self.assertTrue(payload["temp_env_within_localappdata"])
                self.assertTrue(payload["parent_secret_absent"])
                self.assertEqual(payload["outside_sys_path"], [])
                self.assertFalse(os.path.exists(os.path.join(runtime_temp, "_worker_runtime_write_probe")))
                with open(os.path.join(worker_temp, "python-worker-temp-probe.txt"), "r", encoding="utf-8") as stream:
                    self.assertEqual(stream.read(), "WORKER_TEMP_WRITE_OK")
        finally:
            if previous_secret is None:
                os.environ.pop(secret_name, None)
            else:
                os.environ[secret_name] = previous_secret

    def test_worker_is_created_suspended_assigned_then_resumed_with_bounded_stdio(self):
        with self._worker_session(["/d", "/c", "set /p _= & echo WORKER_OK"]) as (worker, worker_pipes, worker_job, worker_temp, runtime_temp):
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
        with self._worker_session(["/d", "/c", command]) as (worker, worker_pipes, worker_job, worker_temp, runtime_temp):
            with self.assertRaises(worker_io.WorkerOutputLimitError):
                self._execute(worker, worker_pipes, worker_job, stdout_limit=128)
            self.assertTrue(worker.wait(5000), "overflow did not terminate the worker")

    def test_timeout_terminates_the_worker_job(self):
        command = "set /p _= & for /l %i in (1,1,2147483647) do @rem"
        with self._worker_session(["/d", "/c", command]) as (worker, worker_pipes, worker_job, worker_temp, runtime_temp):
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
                ) as (worker, worker_pipes, worker_job, worker_temp, runtime_temp):
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
            worker, worker_pipes, worker_job, worker_temp, runtime_temp
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
                worker, worker_pipes, worker_job, worker_temp, runtime_temp
            ):
                result = self._execute(worker, worker_pipes, worker_job)
                self.assertEqual(result.exit_code, 0)
                self.assertFalse(os.path.exists(outside_path))
                inside_path = os.path.join(worker_temp, "worker-write-test.txt")
                self.assertTrue(os.path.isfile(inside_path))
                with open(inside_path, "r", encoding="utf-8") as stream:
                    self.assertIn("TEMP_WRITE_MARKER", stream.read())


    def test_runtime_directory_is_read_execute_only_while_temp_remains_writable(self):
        def arguments(worker_temp, runtime_temp):
            blocked = os.path.join(runtime_temp, "runtime-write-must-fail.txt")
            return [
                "/d", "/c",
                f"set /p _= & echo RUNTIME_WRITE_MARKER > {blocked} & echo TEMP_WRITE_MARKER > worker-write-test.txt",
            ]

        with self._worker_session(arguments) as (
            worker, worker_pipes, worker_job, worker_temp, runtime_temp
        ):
            result = self._execute(worker, worker_pipes, worker_job)
            self.assertEqual(result.exit_code, 0)
            self.assertFalse(
                os.path.exists(os.path.join(runtime_temp, "runtime-write-must-fail.txt"))
            )
            with open(os.path.join(worker_temp, "worker-write-test.txt"), "r", encoding="utf-8") as stream:
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
            ) as (worker, worker_pipes, worker_job, worker_temp, runtime_temp):
                result = self._execute(worker, worker_pipes, worker_job, timeout_ms=8000)
                self.assertNotEqual(result.exit_code, 0)
                self.assertNotIn(b"NETWORK_ALLOWED_MARKER", result.stdout)
                self.assertNotIn(b"NETWORK_ALLOWED_MARKER", result.stderr)
        finally:
            listener.close()
            server.join(timeout=4)
        self.assertFalse(accepted, "AppContainer unexpectedly connected to host loopback")


    def test_appcontainer_cannot_connect_to_host_private_interface(self):
        system_root = os.environ["SystemRoot"]
        curl_path = os.path.join(system_root, "System32", "curl.exe")
        if not os.path.isfile(curl_path):
            self.skipTest("curl.exe is unavailable on this Windows runner")

        candidates = []
        for entry in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET, socket.SOCK_STREAM):
            address = entry[4][0]
            parsed = ipaddress.ip_address(address)
            if parsed.is_private and not parsed.is_loopback and not parsed.is_link_local:
                candidates.append(address)
        if not candidates:
            self.skipTest("Windows runner has no discoverable private IPv4 interface")

        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind((candidates[0], 0))
            listener.listen(2)
            listener.settimeout(3)
        except OSError:
            listener.close()
            self.skipTest("could not bind a test listener to the private interface")
        port = listener.getsockname()[1]
        accepted = []

        def serve_two():
            for _ in range(2):
                try:
                    connection, _ = listener.accept()
                    with connection:
                        accepted.append(True)
                        connection.sendall(b"PRIVATE_NETWORK_ALLOWED_MARKER")
                except OSError:
                    return

        server = threading.Thread(target=serve_two, name="worker-private-interface-server", daemon=True)
        server.start()
        try:
            # Positive control: prove the host itself can reach this listener.
            with socket.create_connection((candidates[0], port), timeout=2) as host_connection:
                self.assertIn(b"PRIVATE_NETWORK_ALLOWED_MARKER", host_connection.recv(128))

            with self._worker_session(
                [
                    "--max-time", "2", "--silent", "--show-error",
                    "--data-binary", "@-", f"http://{candidates[0]}:{port}/",
                ],
                application_name="curl.exe",
            ) as (worker, worker_pipes, worker_job, worker_temp, runtime_temp):
                result = self._execute(worker, worker_pipes, worker_job, timeout_ms=8000)
                self.assertNotEqual(result.exit_code, 0)
                self.assertNotIn(b"PRIVATE_NETWORK_ALLOWED_MARKER", result.stdout)
                self.assertNotIn(b"PRIVATE_NETWORK_ALLOWED_MARKER", result.stderr)
        finally:
            listener.close()
            server.join(timeout=4)
        self.assertEqual(len(accepted), 1, "AppContainer unexpectedly reached the private interface")

    def test_job_active_process_limit_blocks_child_process_creation(self):
        command = 'set /p _= & start /b cmd.exe /d /c echo CHILD_PROCESS_MARKER'
        with self._worker_session(["/d", "/c", command]) as (worker, worker_pipes, worker_job, worker_temp, runtime_temp):
            result = self._execute(worker, worker_pipes, worker_job)
            self.assertNotIn(b"CHILD_PROCESS_MARKER", result.stdout)
            self.assertEqual(worker_job.query_configuration()["active_process_limit"], 1)


if __name__ == "__main__":
    unittest.main()
