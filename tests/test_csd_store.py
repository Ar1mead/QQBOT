from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import inspect
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from core.csd import CSDStore, Event, IdempotencyConflict, StorageIntegrityError


class FailingReducerStore(CSDStore):
    @staticmethod
    def _reduce(state, event, sequence):
        raise RuntimeError("synthetic reducer failure")


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

    def test_multiple_connections_serialize_concurrent_writers(self):
        self.store.close()

        def submit(index):
            with CSDStore(self.db_path, busy_timeout_ms=10000) as writer:
                return writer.submit_event(Event(
                    event_id=f"concurrent-{index}",
                    occurred_at="2026-11-14T12:00:00+00:00",
                    correlation_id="concurrent-test",
                    event_type="test.concurrent.v1",
                    source="test.worker",
                    payload={"index": index},
                ))

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
