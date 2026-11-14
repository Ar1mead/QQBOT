from __future__ import annotations

import inspect
from pathlib import Path
import sqlite3
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
