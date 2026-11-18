import ctypes
import os
import unittest

from adapters.worker_backends import windows_appcontainer as win
from adapters.worker_backends import windows_pipes


@unittest.skipUnless(os.name == "nt", "Windows anonymous pipe APIs")
class WindowsWorkerPipesTests(unittest.TestCase):
    def test_pipe_endpoints_have_strict_inheritance_split(self):
        with windows_pipes.WorkerPipes.create() as pipes:
            child = pipes.child_handles_for_startup()
            self.assertEqual(len(child), 3)
            self.assertEqual(len(set(pipes.handles.child_handle_values)), 3)
            kernel32 = pipes._kernel32
            get_info = kernel32.GetHandleInformation
            get_info.argtypes = [win.HANDLE, ctypes.POINTER(win.DWORD)]
            get_info.restype = win.BOOL
            for handle in child:
                flags = win.DWORD()
                self.assertTrue(get_info(handle, ctypes.byref(flags)))
                self.assertTrue(flags.value & windows_pipes.HANDLE_FLAG_INHERIT)
            for handle in (
                pipes.handles.parent_stdin,
                pipes.handles.parent_stdout,
                pipes.handles.parent_stderr,
            ):
                flags = win.DWORD()
                self.assertTrue(get_info(handle, ctypes.byref(flags)))
                self.assertFalse(flags.value & windows_pipes.HANDLE_FLAG_INHERIT)

    def test_child_ends_can_be_closed_once_after_launch(self):
        pipes = windows_pipes.WorkerPipes.create()
        pipes.close_child_handles_after_launch()
        self.assertEqual(pipes.handles.child_handle_values, (0, 0, 0))
        with self.assertRaisesRegex(RuntimeError, "child pipe handles are already closed"):
            pipes.child_handles_for_startup()
        pipes.close()


class WorkerPipeValidationTests(unittest.TestCase):
    def test_buffer_size_validation_is_fail_closed(self):
        for value in (True, 0, 4095, 1024 * 1024 + 1, "65536"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    windows_pipes.WorkerPipes.create(value)

    def test_non_windows_pipe_creation_fails_closed(self):
        if os.name == "nt":
            self.skipTest("Windows host")
        with self.assertRaisesRegex(OSError, "only on Windows"):
            windows_pipes.WorkerPipes.create()


if __name__ == "__main__":
    unittest.main()
