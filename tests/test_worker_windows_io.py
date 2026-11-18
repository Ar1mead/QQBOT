import unittest

from adapters.worker_backends import windows_worker_io as worker_io


class _FakeJob:
    def __init__(self, *, terminate_error=None, close_error=None):
        self.terminate_error = terminate_error
        self.close_error = close_error
        self.terminated = False
        self.closed = False

    def terminate(self, exit_code):
        self.terminated = True
        if self.terminate_error is not None:
            raise self.terminate_error

    def close(self):
        self.closed = True
        if self.close_error is not None:
            raise self.close_error


class _FakeWorker:
    def __init__(self, waits):
        self.waits = list(waits)
        self.handle = 123
        self.process_id = 456

    def wait(self, timeout_ms):
        result = self.waits.pop(0) if self.waits else True
        if isinstance(result, Exception):
            raise result
        return result


class WorkerTerminationTests(unittest.TestCase):
    def test_job_termination_and_process_exit_are_confirmed(self):
        job = _FakeJob()
        worker = _FakeWorker([True])
        worker_io._terminate_and_confirm(worker, job)
        self.assertTrue(job.terminated)
        self.assertFalse(job.closed)

    def test_job_close_is_used_when_termination_fails(self):
        job = _FakeJob(terminate_error=OSError("TerminateJobObject failed"))
        worker = _FakeWorker([True])
        worker_io._terminate_and_confirm(worker, job)
        self.assertTrue(job.terminated)
        self.assertTrue(job.closed)

    def test_failed_job_close_is_not_hidden_even_if_worker_exits(self):
        job = _FakeJob(
            terminate_error=OSError("TerminateJobObject failed"),
            close_error=OSError("CloseHandle failed"),
        )
        worker = _FakeWorker([True])
        with self.assertRaisesRegex(worker_io.WorkerTerminationError, "fallback close failed"):
            worker_io._terminate_and_confirm(worker, job)

    def test_wait_failure_is_reported(self):
        job = _FakeJob()
        worker = _FakeWorker([OSError("wait failed")])
        with self.assertRaisesRegex(worker_io.WorkerTerminationError, "could not verify"):
            worker_io._terminate_and_confirm(worker, job)


if __name__ == "__main__":
    unittest.main()
