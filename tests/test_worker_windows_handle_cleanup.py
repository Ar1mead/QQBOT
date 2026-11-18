import unittest
from unittest.mock import patch

from adapters.worker_backends import windows_job, windows_pipes, windows_process


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


if __name__ == "__main__":
    unittest.main()
