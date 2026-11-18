"""Bounded, concurrent stdio supervision for a launched Windows worker.

The supervisor writes one bounded request, closes stdin, and concurrently drains
stdout/stderr. It caps retained bytes while streaming and terminates the Job
Object on timeout, I/O error, or output overflow.
"""
from __future__ import annotations

import ctypes
import queue
import threading
import time
from dataclasses import dataclass

from .windows_appcontainer import HANDLE, LPVOID, require_win64
from .windows_job import WorkerJobObject
from .windows_pipes import WorkerPipes
from .windows_process import WorkerProcess


DWORD = ctypes.c_uint32
BOOL = ctypes.c_int32
IO_CHUNK_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 1024 * 1024
MAX_STDOUT_BYTES = 1024 * 1024
MAX_STDERR_BYTES = 64 * 1024
MAX_TIMEOUT_MS = 5 * 60 * 1000
ERROR_BROKEN_PIPE = 109
ERROR_NO_DATA = 232
ERROR_HANDLE_EOF = 38
PIPE_EOF_ERRORS = frozenset({ERROR_BROKEN_PIPE, ERROR_NO_DATA, ERROR_HANDLE_EOF})


class WorkerIOError(RuntimeError):
    pass


class WorkerTimeoutError(WorkerIOError):
    pass


class WorkerOutputLimitError(WorkerIOError):
    pass


class WorkerTerminationError(WorkerIOError):
    pass


@dataclass(frozen=True)
class WorkerIOResult:
    stdout: bytes
    stderr: bytes
    exit_code: int


@dataclass(frozen=True)
class _IOEvent:
    stream: str
    data: bytes = b""
    error: str | None = None
    overflow: bool = False


def _validate_limits(
    request_bytes: bytes,
    timeout_ms: int,
    stdout_limit: int,
    stderr_limit: int,
) -> None:
    if not isinstance(request_bytes, bytes):
        raise TypeError("worker request must be immutable bytes")
    if not 1 <= len(request_bytes) <= MAX_REQUEST_BYTES:
        raise ValueError(f"worker request must contain 1 through {MAX_REQUEST_BYTES} bytes")
    for name, value, maximum in (
        ("timeout_ms", timeout_ms, MAX_TIMEOUT_MS),
        ("stdout_limit", stdout_limit, MAX_STDOUT_BYTES),
        ("stderr_limit", stderr_limit, MAX_STDERR_BYTES),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be an integer from 1 through {maximum}")


def _terminate_and_confirm(worker: WorkerProcess, job: WorkerJobObject) -> None:
    """Stop the worker and prove termination; never hide a failed fallback."""
    fallback_close_error: Exception | None = None
    try:
        job.terminate(0xE0010002)
    except Exception:
        try:
            # Kill-on-close is the fallback containment mechanism.
            job.close()
        except Exception as exc:
            fallback_close_error = exc

    try:
        if worker.wait(5000):
            if fallback_close_error is not None:
                raise WorkerTerminationError(
                    "worker exited, but the Job Object fallback close failed"
                ) from fallback_close_error
            return
    except WorkerTerminationError:
        raise
    except Exception as exc:
        raise WorkerTerminationError(
            "could not verify worker termination after Job Object termination"
        ) from exc

    # Last resort: the worker is the Job's only allowed process.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    terminate = kernel32.TerminateProcess
    terminate.argtypes = [HANDLE, DWORD]
    terminate.restype = BOOL
    if not worker.handle:
        raise WorkerTerminationError("worker process handle closed before termination")
    if not terminate(worker.handle, 0xE0010003):
        error = ctypes.get_last_error()
        # The process may have exited between WaitForSingleObject and TerminateProcess.
        try:
            if not worker.wait(5000):
                raise WorkerTerminationError(
                    f"TerminateProcess failed with Win32 error {error}; process remains active"
                )
        except WorkerTerminationError:
            raise
        except Exception as exc:
            raise WorkerTerminationError(
                f"TerminateProcess failed with Win32 error {error}; exit could not be verified"
            ) from exc
    elif not worker.wait(5000):
        raise WorkerTerminationError(
            f"could not confirm worker process {worker.process_id} termination"
        )

    if fallback_close_error is not None:
        raise WorkerTerminationError(
            "worker process terminated, but the Job Object handle could not be closed"
        ) from fallback_close_error


def execute_worker_stdio(
    *,
    worker: WorkerProcess,
    pipes: WorkerPipes,
    job: WorkerJobObject,
    request_bytes: bytes,
    timeout_ms: int = 30000,
    stdout_limit: int = MAX_STDOUT_BYTES,
    stderr_limit: int = MAX_STDERR_BYTES,
) -> WorkerIOResult:
    """Exchange one request with a worker using bounded concurrent pipe I/O.

    This function does not validate the worker protocol or close the worker
    process handle. The caller owns the WorkerProcess, WorkerPipes, and Job.
    """
    _validate_limits(request_bytes, timeout_ms, stdout_limit, stderr_limit)
    require_win64()
    if not isinstance(worker, WorkerProcess) or not worker.handle:
        raise TypeError("worker must be an open WorkerProcess")
    if not isinstance(pipes, WorkerPipes):
        raise TypeError("pipes must be a WorkerPipes owner")
    if not isinstance(job, WorkerJobObject) or not job.handle:
        raise TypeError("job must be an open WorkerJobObject")
    if not pipes.handles.parent_stdin or not pipes.handles.parent_stdout or not pipes.handles.parent_stderr:
        raise RuntimeError("all parent pipe endpoints must be open")

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    read_file = kernel32.ReadFile
    read_file.argtypes = [
        HANDLE, LPVOID, DWORD, ctypes.POINTER(DWORD), LPVOID
    ]
    read_file.restype = BOOL
    write_file = kernel32.WriteFile
    write_file.argtypes = [
        HANDLE, LPVOID, DWORD, ctypes.POINTER(DWORD), LPVOID
    ]
    write_file.restype = BOOL

    events: queue.Queue[_IOEvent] = queue.Queue()
    result_buffers: dict[str, bytes] = {}
    completed: set[str] = set()

    def read_stream(name: str, handle: HANDLE, maximum: int) -> None:
        collected = bytearray()
        try:
            while True:
                request_size = min(IO_CHUNK_BYTES, maximum - len(collected) + 1)
                buffer = ctypes.create_string_buffer(request_size)
                count = DWORD()
                if not read_file(
                    handle, ctypes.cast(buffer, LPVOID), request_size,
                    ctypes.byref(count), None,
                ):
                    error = ctypes.get_last_error()
                    if error in PIPE_EOF_ERRORS:
                        break
                    events.put(_IOEvent(name, error=f"ReadFile failed with Win32 error {error}"))
                    return
                if count.value == 0:
                    break
                if len(collected) + count.value > maximum:
                    events.put(_IOEvent(name, overflow=True))
                    return
                collected.extend(buffer.raw[: count.value])
            events.put(_IOEvent(name, data=bytes(collected)))
        except Exception as exc:
            events.put(_IOEvent(name, error=f"{name} reader failed: {type(exc).__name__}: {exc}"))

    def write_request() -> None:
        try:
            offset = 0
            handle = pipes.handles.parent_stdin
            while offset < len(request_bytes):
                chunk = request_bytes[offset : offset + IO_CHUNK_BYTES]
                buffer = ctypes.create_string_buffer(chunk)
                count = DWORD()
                if not write_file(
                    handle, ctypes.cast(buffer, LPVOID), len(chunk),
                    ctypes.byref(count), None,
                ):
                    error = ctypes.get_last_error()
                    events.put(_IOEvent("stdin", error=f"WriteFile failed with Win32 error {error}"))
                    return
                if count.value == 0:
                    events.put(_IOEvent("stdin", error="WriteFile completed without writing bytes"))
                    return
                offset += count.value
            pipes.close_parent_stdin()
            events.put(_IOEvent("stdin"))
        except Exception as exc:
            events.put(_IOEvent("stdin", error=f"stdin writer failed: {type(exc).__name__}: {exc}"))

    threads = [
        threading.Thread(
            target=read_stream,
            args=("stdout", pipes.handles.parent_stdout, stdout_limit),
            name="qqbot-worker-stdout",
            daemon=False,
        ),
        threading.Thread(
            target=read_stream,
            args=("stderr", pipes.handles.parent_stderr, stderr_limit),
            name="qqbot-worker-stderr",
            daemon=False,
        ),
        threading.Thread(
            target=write_request,
            name="qqbot-worker-stdin",
            daemon=False,
        ),
    ]

    deadline = time.monotonic() + timeout_ms / 1000.0
    started_threads: list[threading.Thread] = []

    try:
        for thread in threads:
            thread.start()
            started_threads.append(thread)

        while len(completed) < 3:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate_and_confirm(worker, job)
                raise WorkerTimeoutError(
                    f"worker process {worker.process_id} exceeded {timeout_ms} ms"
                )

            try:
                event = events.get(timeout=min(0.05, remaining))
            except queue.Empty:
                event = None

            if event is not None:
                if event.error:
                    _terminate_and_confirm(worker, job)
                    raise WorkerIOError(event.error)
                if event.overflow:
                    _terminate_and_confirm(worker, job)
                    limit = stdout_limit if event.stream == "stdout" else stderr_limit
                    raise WorkerOutputLimitError(
                        f"worker {event.stream} exceeded its {limit}-byte limit"
                    )
                completed.add(event.stream)
                if event.stream in {"stdout", "stderr"}:
                    result_buffers[event.stream] = event.data

            # If the process exited but a pipe thread has not finished, allow a
            # short drain interval; a leaked writer handle must not hang forever.
            if worker.wait(0) and len(completed) < 3:
                drain_deadline = min(deadline, time.monotonic() + 2.0)
                while len(completed) < 3 and time.monotonic() < drain_deadline:
                    try:
                        event = events.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    if event.error:
                        raise WorkerIOError(event.error)
                    if event.overflow:
                        limit = stdout_limit if event.stream == "stdout" else stderr_limit
                        raise WorkerOutputLimitError(
                            f"worker {event.stream} exceeded its {limit}-byte limit"
                        )
                    completed.add(event.stream)
                    if event.stream in {"stdout", "stderr"}:
                        result_buffers[event.stream] = event.data
                if len(completed) < 3:
                    raise WorkerIOError("worker exited but stdio pipes did not reach EOF")

        # Closing stdio can precede process termination by a short interval.
        # Keep supervising the process until exit or the original deadline.
        while not worker.wait(50):
            if time.monotonic() >= deadline:
                _terminate_and_confirm(worker, job)
                raise WorkerTimeoutError(
                    f"worker process {worker.process_id} exceeded {timeout_ms} ms"
                )

        return WorkerIOResult(
            stdout=result_buffers["stdout"],
            stderr=result_buffers["stderr"],
            exit_code=worker.exit_code(),
        )
    except Exception as primary_error:
        # If the process is still active, stop it before waiting for the readers.
        try:
            if not worker.wait(0):
                _terminate_and_confirm(worker, job)
        except Exception as cleanup_error:
            raise WorkerTerminationError(
                "worker I/O failed and process termination could not be confirmed; "
                f"primary={type(primary_error).__name__}: {primary_error}; "
                f"cleanup={type(cleanup_error).__name__}: {cleanup_error}"
            ) from cleanup_error
        raise
    finally:
        for thread in started_threads:
            thread.join(timeout=5.0)
        alive = [thread.name for thread in started_threads if thread.is_alive()]
        if alive:
            try:
                _terminate_and_confirm(worker, job)
            except Exception as cleanup_error:
                raise WorkerTerminationError(
                    "worker stdio threads remained active and termination failed: "
                    + ", ".join(alive)
                ) from cleanup_error
            raise WorkerTerminationError(
                "worker stdio threads did not stop: " + ", ".join(alive)
            )
