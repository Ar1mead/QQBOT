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


class WorkerLaunchValidationTests(unittest.TestCase):
    def test_non_windows_launch_fails_closed_before_native_setup(self):
        if os.name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            process.launch_appcontainer_worker(
                application_path="not-an-executable",
                arguments=[],
                current_directory="not-a-directory",
                environment=None,
                pipes=None,
                startup=None,
                job=None,
            )

    @unittest.skipUnless(os.name == "nt", "Windows path validation")
    def test_launch_spec_requires_absolute_existing_paths_and_string_arguments(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = os.path.join(directory, "worker.exe")
            with open(executable, "wb") as stream:
                stream.write(b"test")
            with self.assertRaises(ValueError):
                process._validate_launch_spec("relative.exe", [], directory)
            with self.assertRaises(ValueError):
                process._validate_launch_spec(os.path.join(directory, "missing.exe"), [], directory)
            with self.assertRaises(ValueError):
                process._validate_launch_spec(executable, ["bad\x00arg"], directory)
            with self.assertRaises(TypeError):
                process._validate_launch_spec(executable, "arg", directory)


@unittest.skipUnless(os.name == "nt", "Windows AppContainer process launch")
class WindowsAppContainerProcessLaunchTests(unittest.TestCase):
    def _read_pipe(self, handle, limit=4096):
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        read_file = kernel32.ReadFile
        read_file.argtypes = [
            app.HANDLE,
            app.LPVOID,
            app.DWORD,
            ctypes.POINTER(app.DWORD),
            app.LPVOID,
        ]
        read_file.restype = app.BOOL
        buffer = ctypes.create_string_buffer(limit)
        count = app.DWORD()
        if not read_file(handle, buffer, limit, ctypes.byref(count), None):
            error = ctypes.get_last_error()
            if error == 109:  # ERROR_BROKEN_PIPE after the child closed its writer.
                return b""
            raise ctypes.WinError(error)
        return buffer.raw[: count.value]

    def test_worker_is_created_suspended_assigned_then_resumed(self):
        system_root = os.environ["SystemRoot"]
        system32 = os.path.join(system_root, "System32")
        application = os.path.join(system32, "cmd.exe")
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
                                arguments=["/d", "/c", "echo", "WORKER_OK"],
                                current_directory=worker_temp,
                                environment=worker_env,
                                pipes=worker_pipes,
                                startup=startup_attributes,
                                job=worker_job,
                            ) as worker:
                                self.assertTrue(worker.wait(10000), "AppContainer worker timed out")
                                self.assertEqual(worker.exit_code(), 0)
                                output = self._read_pipe(worker_pipes.handles.parent_stdout)
                                self.assertIn(b"WORKER_OK", output)
                                self.assertTrue(
                                    worker_job.query_configuration()["limit_flags"]
                                    & job.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                                )


if __name__ == "__main__":
    unittest.main()
