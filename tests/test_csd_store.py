from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import inspect
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import threading
import tempfile
import unittest
from unittest.mock import patch

from core.csd import CSDStore, Event, IdempotencyConflict, StorageIntegrityError


def sqlite_environment_diagnostics(connection, database_path, error=None):
    path = Path(database_path).resolve()
    diagnostics = {
        "python_version": sys.version,
        "sqlite_version": sqlite3.sqlite_version,
        "database_path": str(path),
        "parent_writable": os.access(path.parent, os.W_OK),
        "sqlite_errorcode": getattr(error, "sqlite_errorcode", None),
        "sqlite_errorname": getattr(error, "sqlite_errorname", None),
    }
    if connection is not None:
        for key, statement in (
            ("journal_mode", "PRAGMA journal_mode"),
            ("locking_mode", "PRAGMA locking_mode"),
            ("database_list", "PRAGMA database_list"),
        ):
            try:
                diagnostics[key] = [tuple(row) for row in connection.execute(statement).fetchall()]
            except sqlite3.Error as exc:
                diagnostics[key] = f"{type(exc).__name__}: {exc}"
    files = {}
    for label, candidate in (
        ("database", path),
        ("wal", Path(f"{path}-wal")),
        ("shm", Path(f"{path}-shm")),
    ):
        try:
            metadata = candidate.stat()
            files[label] = {
                "exists": True,
                "size": metadata.st_size,
                "mode": oct(stat.S_IMODE(metadata.st_mode)),
                "readonly_mode_bit": not bool(metadata.st_mode & stat.S_IWRITE),
                "windows_readonly_attribute": bool(
                    getattr(metadata, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_READONLY", 1)
                ),
            }
        except FileNotFoundError:
            files[label] = {"exists": False}
        except OSError as exc:
            files[label] = f"{type(exc).__name__}: {exc}"
    diagnostics["files"] = files
    return diagnostics


class FailingReducerStore(CSDStore):
    @staticmethod
    def _reduce(state, event, sequence):
        raise RuntimeError("synthetic reducer failure")


class FaultingTransactionConnection:
    def __init__(self, *, fail_commit=False, fail_rollback=False):
        self.fail_commit = fail_commit
        self.fail_rollback = fail_rollback
        self.in_transaction = True
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        if statement == "COMMIT" and self.fail_commit:
            raise sqlite3.OperationalError("synthetic commit failure")
        if statement == "ROLLBACK" and self.fail_rollback:
            raise sqlite3.OperationalError("synthetic rollback failure")
        if statement in {"COMMIT", "ROLLBACK"}:
            self.in_transaction = False


class CSDStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "csd.sqlite3"
        self.store = CSDStore(self.db_path)

    def tearDown(self):
        try:
            self.store.close()
        except sqlite3.ProgrammingError:
            pass
        self.temp_dir.cleanup()

    def event(self, event_id="evt-1", payload=None, event_type="test.observation_recorded.v1"):
        return Event(
            event_id=event_id,
            occurred_at="2026-11-14T12:00:00+00:00",
            correlation_id="corr-1",
            event_type=event_type,
            source="test.fixture",
            payload=payload if payload is not None else {"label": "sample"},
        )

    def test_constructor_closes_connection_when_schema_initialization_fails(self):
        failed_path = self.db_path.parent / "constructor-failure.sqlite3"
        real_connect = sqlite3.connect
        opened_connections = []

        def tracked_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            opened_connections.append(connection)
            return connection

        with patch("core.csd.store.sqlite3.connect", side_effect=tracked_connect):
            with patch.object(
                CSDStore,
                "_initialize_schema",
                side_effect=RuntimeError("synthetic schema initialization failure"),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "synthetic schema initialization failure"
                ):
                    CSDStore(failed_path)

        self.assertEqual(len(opened_connections), 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            opened_connections[0].execute("SELECT 1")

    def test_transaction_rolls_back_after_commit_failure(self):
        connection = FaultingTransactionConnection(fail_commit=True)
        with self.assertRaisesRegex(sqlite3.OperationalError, "synthetic commit failure"):
            with CSDStore._Transaction(connection):
                pass
        self.assertEqual(connection.statements, ["COMMIT", "ROLLBACK"])
        self.assertFalse(connection.in_transaction)

    def test_transaction_preserves_body_error_when_rollback_fails(self):
        connection = FaultingTransactionConnection(fail_rollback=True)
        with self.assertRaisesRegex(RuntimeError, "primary body failure") as raised:
            with CSDStore._Transaction(connection):
                raise RuntimeError("primary body failure")
        self.assertIsInstance(raised.exception.__cause__, sqlite3.OperationalError)
        self.assertIn("ROLLBACK", connection.statements)

    def test_transaction_preserves_commit_error_when_rollback_fails(self):
        connection = FaultingTransactionConnection(
            fail_commit=True,
            fail_rollback=True,
        )
        with self.assertRaisesRegex(
            sqlite3.OperationalError, "synthetic commit failure"
        ) as raised:
            with CSDStore._Transaction(connection):
                pass
        self.assertIsInstance(raised.exception.__cause__, sqlite3.OperationalError)
        self.assertIn("ROLLBACK", connection.statements)

    def test_accepts_event_and_updates_projection(self):
        result = self.store.submit_event(self.event())
        self.assertEqual(result["status"], "accepted")
        snapshot = self.store.get_state_snapshot()
        self.assertEqual(snapshot["through_sequence"], 1)
        self.assertEqual(snapshot["state"]["accepted_event_count"], 1)
        self.assertEqual(snapshot["state"]["event_counts"]["test.observation_recorded.v1"], 1)

    def test_duplicate_event_is_not_reduced_twice(self):
        first = self.store.submit_event(self.event())
        second = self.store.submit_event(self.event())
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(first["sequence"], second["sequence"])
        self.assertEqual(self.store.get_state_snapshot()["state"]["accepted_event_count"], 1)

    def test_same_id_with_different_payload_is_conflict(self):
        self.store.submit_event(self.event())
        with self.assertRaises(IdempotencyConflict):
            self.store.submit_event(self.event(payload={"label": "different"}))
        self.assertEqual(self.store.get_state_snapshot()["state"]["accepted_event_count"], 1)

    def test_reducer_failure_rolls_back_payload_event_and_projection(self):
        self.store.close()
        failing = FailingReducerStore(self.db_path)
        with self.assertRaises(RuntimeError):
            failing.submit_event(self.event())
        failing.close()
        with CSDStore(self.db_path) as reopened:
            self.assertEqual(reopened.get_state_snapshot()["through_sequence"], 0)
            count = reopened._connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            payload_count = reopened._connection.execute("SELECT COUNT(*) FROM event_payloads").fetchone()[0]
            self.assertEqual(count, 0)
            self.assertEqual(payload_count, 0)

    def test_snapshot_plus_tail_recovers_after_reopen(self):
        self.store.submit_event(self.event("evt-1"))
        snapshot_id = self.store.create_snapshot()
        self.store.submit_event(self.event("evt-2", {"label": "second"}))
        expected = self.store.get_state_snapshot()["state"]
        self.store.close()
        with CSDStore(self.db_path) as reopened:
            result = reopened.recover()
            self.assertEqual(result.source_snapshot_id, snapshot_id)
            self.assertEqual(result.replayed_events, 1)
            self.assertEqual(result.state, expected)

    def test_recovery_serializes_concurrent_writer_before_projection_replace(self):
        self.store.submit_event(self.event("before-recovery"))
        self.store.close()

        replay_started = threading.Event()
        allow_replay_to_finish = threading.Event()
        writer_ready = threading.Event()
        allow_writer_to_submit = threading.Event()
        writer_attempted_begin = threading.Event()
        writer_done = threading.Event()
        recovery_results = []
        recovery_errors = []
        writer_errors = []
        writer_results = []

        class PausingRecoveryStore(CSDStore):
            def _reduce(self, state, event, sequence):
                replay_started.set()
                if not allow_replay_to_finish.wait(timeout=10):
                    raise TimeoutError("recovery replay was not released")
                return super()._reduce(state, event, sequence)

        def run_recovery():
            try:
                with PausingRecoveryStore(self.db_path) as recovering:
                    recovery_results.append(recovering.recover())
            except BaseException as exc:
                recovery_errors.append(exc)

        def run_writer():
            writer = None
            try:
                # Create the connection in the same thread that will use it.
                writer = CSDStore(self.db_path, busy_timeout_ms=10000)
                writer._connection.set_trace_callback(
                    lambda statement: writer_attempted_begin.set()
                    if statement.strip().upper() == "BEGIN IMMEDIATE"
                    else None
                )
                writer_ready.set()
                if not allow_writer_to_submit.wait(timeout=10):
                    raise TimeoutError("writer was not released")
                writer_results.append(
                    writer.submit_event(self.event("during-recovery"))
                )
            except BaseException as exc:
                writer_errors.append(exc)
            finally:
                if writer is not None:
                    writer.close()
                writer_done.set()

        recovery_thread = threading.Thread(
            target=run_recovery,
            name="csd-recovery-race-test",
        )
        writer_thread = threading.Thread(
            target=run_writer,
            name="csd-concurrent-writer-test",
        )
        recovery_started = False
        writer_thread.start()
        try:
            self.assertTrue(writer_ready.wait(timeout=5))
            recovery_thread.start()
            recovery_started = True
            self.assertTrue(replay_started.wait(timeout=5))
            allow_writer_to_submit.set()
            self.assertTrue(writer_attempted_begin.wait(timeout=5))
            self.assertFalse(
                writer_done.wait(timeout=0.5),
                "writer should wait while Recovery owns the write transaction",
            )
        finally:
            allow_writer_to_submit.set()
            allow_replay_to_finish.set()
            if recovery_started:
                recovery_thread.join(timeout=10)
            writer_thread.join(timeout=10)

        self.assertFalse(
            recovery_thread.is_alive() if recovery_started else False,
            "Recovery thread did not finish",
        )
        self.assertFalse(writer_thread.is_alive(), "writer thread did not finish")
        self.assertEqual(recovery_errors, [])
        self.assertEqual(writer_errors, [])
        self.assertEqual(recovery_results[0].state["accepted_event_count"], 1)
        with CSDStore(self.db_path) as reopened:
            final = reopened.get_state_snapshot()
            self.assertEqual(final["through_sequence"], 2)
            self.assertEqual(final["state"]["accepted_event_count"], 2)

    def test_corrupt_snapshot_is_rejected_and_rebuilt_from_event_log(self):
        self.store.submit_event(self.event())
        snapshot_id = self.store.create_snapshot()
        expected = self.store.get_state_snapshot()["state"]
        self.store._connection.execute(
            "UPDATE snapshots SET state_json = ? WHERE snapshot_id = ?",
            ('{"tampered":true}', snapshot_id),
        )
        result = self.store.recover()
        self.assertIsNone(result.source_snapshot_id)
        self.assertEqual(len(result.rejected_snapshots), 1)
        self.assertEqual(result.state, expected)

    def test_corrupt_payload_causes_safe_stop(self):
        self.store.submit_event(self.event())
        # Simulate out-of-band disk/database corruption by bypassing the guard trigger.
        self.store._connection.execute("DROP TRIGGER payloads_no_update")
        self.store._connection.execute(
            "UPDATE event_payloads SET payload_json = '{\"tampered\":true}'"
        )
        with self.assertRaises(StorageIntegrityError):
            self.store.recover()
        self.assertTrue(self.db_path.exists())

    def test_recovery_api_has_no_action_executor_parameter(self):
        parameters = inspect.signature(CSDStore.recover).parameters
        self.assertEqual(tuple(parameters), ("self",))

    def test_journal_and_synchronous_mode_matrix_round_trip(self):
        self.store.close()
        for journal_mode in ("WAL", "DELETE"):
            for synchronous in ("FULL", "NORMAL"):
                with self.subTest(journal_mode=journal_mode, synchronous=synchronous):
                    db_path = self.db_path.parent / f"{journal_mode.lower()}-{synchronous.lower()}.sqlite3"
                    with CSDStore(
                        db_path,
                        journal_mode=journal_mode,
                        synchronous=synchronous,
                    ) as candidate:
                        candidate.submit_event(self.event(event_id=f"{journal_mode}-{synchronous}"))
                        expected = candidate.get_state_snapshot()["state"]
                    with CSDStore(
                        db_path,
                        journal_mode=journal_mode,
                        synchronous=synchronous,
                    ) as reopened:
                        result = reopened.recover()
                        self.assertEqual(result.state, expected)

    def test_process_exit_mid_transaction_rolls_back_event(self):
        self.store.close()
        repo_root = Path(__file__).resolve().parents[1]
        script = r'''
import os, sys
from core.csd import CSDStore, Event
store = CSDStore(sys.argv[1])
store._reduce = lambda state, event, sequence: os._exit(23)
store.submit_event(Event(
    event_id="crash-mid-transaction",
    occurred_at="2026-11-14T12:00:00+00:00",
    correlation_id="crash-test",
    event_type="test.crash.v1",
    source="test.subprocess",
    payload={"marker": "must-roll-back"},
))
'''
        child = subprocess.run(
            [sys.executable, "-c", script, str(self.db_path)],
            cwd=repo_root,
            check=False,
        )
        self.assertEqual(child.returncode, 23)
        with CSDStore(self.db_path) as reopened:
            recovered = reopened.recover()
            self.assertEqual(recovered.state["accepted_event_count"], 0)
            count = reopened._connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            self.assertEqual(count, 0)

    def test_process_exit_after_commit_is_safe_to_retry(self):
        self.store.close()
        repo_root = Path(__file__).resolve().parents[1]
        script = r'''
import os, sys
from core.csd import CSDStore, Event
store = CSDStore(sys.argv[1])
original_transaction = store._transaction
class ExitAfterCommit:
    def __enter__(self):
        self.inner = original_transaction()
        return self.inner.__enter__()
    def __exit__(self, exc_type, exc, traceback):
        result = self.inner.__exit__(exc_type, exc, traceback)
        os._exit(24)
store._transaction = lambda: ExitAfterCommit()
store.submit_event(Event(
    event_id="crash-after-commit",
    occurred_at="2026-11-14T12:00:00+00:00",
    correlation_id="crash-test",
    event_type="test.crash.v1",
    source="test.subprocess",
    payload={"marker": "already-committed"},
))
'''
        child = subprocess.run(
            [sys.executable, "-c", script, str(self.db_path)],
            cwd=repo_root,
            check=False,
        )
        self.assertEqual(child.returncode, 24)
        with CSDStore(self.db_path) as reopened:
            result = reopened.submit_event(Event(
                event_id="crash-after-commit",
                occurred_at="2026-11-14T12:00:00+00:00",
                correlation_id="crash-test",
                event_type="test.crash.v1",
                source="test.subprocess",
                payload={"marker": "already-committed"},
            ))
            self.assertEqual(result["status"], "duplicate")
            self.assertEqual(reopened.get_state_snapshot()["state"]["accepted_event_count"], 1)

    def test_concurrent_connection_bootstrap_without_writes(self):
        self.store.close()

        def open_and_close(index):
            try:
                with CSDStore(self.db_path, busy_timeout_ms=10000) as candidate:
                    return candidate._connection.execute(
                        "PRAGMA journal_mode"
                    ).fetchone()[0]
            except sqlite3.OperationalError as exc:
                diagnostics = sqlite_environment_diagnostics(
                    None, self.db_path, exc
                )
                raise AssertionError(
                    "concurrent SQLite connection bootstrap failed; "
                    f"diagnostics={diagnostics!r}"
                ) from exc

        with ThreadPoolExecutor(max_workers=8) as executor:
            modes = list(executor.map(open_and_close, range(20)))
        self.assertEqual(modes, ["wal"] * 20)

    def test_preopened_connections_serialize_concurrent_writers(self):
        self.store.close()
        writers = []
        try:
            for _ in range(8):
                writers.append(CSDStore(self.db_path, busy_timeout_ms=10000))

            def submit(item):
                index, writer = item
                return writer.submit_event(self.event(
                    event_id=f"preopened-{index}",
                    payload={"index": index},
                ))

            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(executor.map(submit, enumerate(writers)))
        finally:
            for writer in writers:
                writer.close()

        self.assertEqual(
            sum(result["status"] == "accepted" for result in results),
            len(writers),
        )
        with CSDStore(self.db_path) as reopened:
            self.assertEqual(
                reopened.get_state_snapshot()["state"]["accepted_event_count"],
                len(writers),
            )

    def test_multiple_connections_serialize_concurrent_writers(self):
        self.store.close()

        def submit(index):
            with CSDStore(self.db_path, busy_timeout_ms=10000) as writer:
                try:
                    return writer.submit_event(Event(
                        event_id=f"concurrent-{index}",
                        occurred_at="2026-11-14T12:00:00+00:00",
                        correlation_id="concurrent-test",
                        event_type="test.concurrent.v1",
                        source="test.worker",
                        payload={"index": index},
                    ))
                except sqlite3.OperationalError as exc:
                    diagnostics = sqlite_environment_diagnostics(
                        writer._connection, self.db_path, exc
                    )
                    raise AssertionError(
                        "concurrent SQLite write failed; "
                        f"errorcode={getattr(exc, 'sqlite_errorcode', None)!r}, "
                        f"errorname={getattr(exc, 'sqlite_errorname', None)!r}, "
                        f"diagnostics={diagnostics!r}"
                    ) from exc

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(submit, range(20)))
        self.assertEqual(sum(result["status"] == "accepted" for result in results), 20)
        with CSDStore(self.db_path) as reopened:
            recovered = reopened.recover()
            self.assertEqual(recovered.state["accepted_event_count"], 20)

    def test_busy_timeout_fails_cleanly_then_retry_succeeds(self):
        self.store.close()
        candidate = CSDStore(self.db_path, busy_timeout_ms=50)
        locker = sqlite3.connect(str(self.db_path), isolation_level=None)
        try:
            locker.execute("BEGIN IMMEDIATE")
            with self.assertRaises(sqlite3.OperationalError):
                candidate.submit_event(self.event())
            locker.execute("ROLLBACK")
            result = candidate.submit_event(self.event())
            self.assertEqual(result["status"], "accepted")
        finally:
            if locker.in_transaction:
                locker.execute("ROLLBACK")
            locker.close()
            candidate.close()

    def test_sqlite_backup_restores_event_log_and_projection(self):
        self.store.submit_event(self.event("backup-1"))
        self.store.submit_event(self.event("backup-2", {"label": "two"}))
        expected = self.store.get_state_snapshot()["state"]
        backup_path = self.db_path.parent / "backup.sqlite3"
        backup_connection = sqlite3.connect(str(backup_path))
        try:
            self.store._connection.backup(backup_connection)
        finally:
            backup_connection.close()
        with CSDStore(backup_path) as restored:
            result = restored.recover()
            self.assertEqual(result.state, expected)

    def test_event_envelope_tampering_causes_safe_stop(self):
        self.store.submit_event(self.event())
        self.store._connection.execute("DROP TRIGGER events_no_update")
        self.store._connection.execute("UPDATE events SET source = 'tampered.source'")
        with self.assertRaises(StorageIntegrityError):
            self.store.recover()

    def test_invalid_timezone_is_rejected(self):
        bad = Event(
            event_id="evt-bad",
            occurred_at="2026-11-14T12:00:00",
            correlation_id="corr-1",
            event_type="test.observation_recorded.v1",
            source="test.fixture",
            payload={"label": "sample"},
        )
        with self.assertRaises(ValueError):
            self.store.submit_event(bad)


if __name__ == "__main__":
    unittest.main()
