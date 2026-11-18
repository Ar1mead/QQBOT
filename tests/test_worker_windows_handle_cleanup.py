import unittest
from unittest.mock import patch

from adapters.worker_backends import windows_acl, windows_appcontainer, windows_job, windows_pipes, windows_process


class _CloseSequence:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)

    def __call__(self, handle):
        return self.outcomes.pop(0) if self.outcomes else True


class NativeHandleCleanupTests(unittest.TestCase):
    def test_job_handle_is_retained_when_close_fails_then_cleared_on_retry(self):
        owner = windows_job.WorkerJobObject.__new__(windows_job.WorkerJobObject)
        owner.handle = 101
        owner._close_handle = _CloseSequence([False, True])
        with patch.object(windows_job.ctypes, "WinError", side_effect=OSError("close failed"), create=True):
            with self.assertRaisesRegex(OSError, "close failed"):
                owner.close()
        self.assertEqual(owner.handle, 101)
        owner.close()
        self.assertIsNone(owner.handle)

    def test_process_handle_is_retained_when_close_fails_then_cleared_on_retry(self):
        owner = windows_process.WorkerProcess.__new__(windows_process.WorkerProcess)
        owner.handle = 202
        owner._close = _CloseSequence([False, True])
        with patch.object(windows_process.ctypes, "WinError", side_effect=OSError("close failed"), create=True):
            with self.assertRaisesRegex(OSError, "close failed"):
                owner.close()
        self.assertEqual(owner.handle, 202)
        owner.close()
        self.assertIsNone(owner.handle)

    def test_pipe_close_keeps_only_failed_handles_for_retry(self):
        owner = windows_pipes.WorkerPipes.__new__(windows_pipes.WorkerPipes)
        owner.handles = windows_pipes.WorkerPipeHandles(1, 2, 3, 4, 5, 6)
        owner._close = _CloseSequence([False, True, True, True, True, True, True])
        owner._closed = False
        owner._child_closed = False
        with patch.object(windows_pipes.ctypes, "get_last_error", return_value=5, create=True), patch.object(
            windows_pipes.ctypes, "WinError", side_effect=OSError("close failed"), create=True
        ):
            with self.assertRaisesRegex(OSError, "close failed"):
                owner.close()
        self.assertEqual(owner.handles.child_stdin, 1)
        self.assertEqual(
            (owner.handles.child_stdout, owner.handles.child_stderr, owner.handles.parent_stdin,
             owner.handles.parent_stdout, owner.handles.parent_stderr),
            (None, None, None, None, None),
        )
        self.assertFalse(owner._closed)
        owner.close()
        self.assertTrue(owner._closed)
        self.assertIsNone(owner.handles.child_stdin)

    def test_acl_object_handle_is_retained_when_close_fails_then_cleared_on_retry(self):
        owner = windows_acl._AclObjectHandle.__new__(windows_acl._AclObjectHandle)
        owner.value = 303
        owner._close_handle = _CloseSequence([False, True])
        with patch.object(windows_acl.ctypes, "WinError", side_effect=OSError("close failed"), create=True), patch.object(
            windows_acl.ctypes, "get_last_error", return_value=5, create=True
        ):
            with self.assertRaisesRegex(OSError, "close failed"):
                owner.close()
        self.assertEqual(owner.value, 303)
        owner.close()
        self.assertIsNone(owner.value)

    def test_appcontainer_sid_buffer_is_retained_when_local_free_fails(self):
        owner = windows_appcontainer.EmptyAppContainerCapabilities.__new__(
            windows_appcontainer.EmptyAppContainerCapabilities
        )
        owner._sid = windows_appcontainer.LPVOID(404)
        owner._closed = False
        owner._local_free = _CloseSequence([404, None])
        with patch.object(windows_appcontainer.ctypes, "WinError", side_effect=OSError("LocalFree failed"), create=True), patch.object(
            windows_appcontainer.ctypes, "get_last_error", return_value=5, create=True
        ):
            with self.assertRaisesRegex(OSError, "LocalFree failed"):
                owner.close()
        self.assertEqual(owner._sid.value, 404)
        self.assertFalse(owner._closed)
        owner.close()
        self.assertIsNone(owner._sid.value)
        self.assertTrue(owner._closed)

    def test_process_information_cleanup_attempts_both_handles_and_retains_failure(self):
        info = windows_process.PROCESS_INFORMATION()
        info.hThread = 22
        info.hProcess = 11
        closer = _CloseSequence([False, True])
        with patch.object(windows_process.ctypes, "get_last_error", return_value=6, create=True):
            failures = windows_process._close_owned_process_handles(info, closer)
        self.assertEqual(failures, (("hThread", 6),))
        self.assertEqual(info.hThread, 22)
        self.assertIsNone(info.hProcess)

        retry = _CloseSequence([True])
        self.assertEqual(windows_process._close_owned_process_handles(info, retry), ())
        self.assertIsNone(info.hThread)


if __name__ == "__main__":
    unittest.main()
