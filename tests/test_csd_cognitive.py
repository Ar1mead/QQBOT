from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveIdempotencyConflict,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
    ProposalIdentityConflict,
)
from core.csd.cognitive import (
    DECISION_EVENT,
    OBSERVATION_EVENT,
    PROPOSAL_EVENT,
)


class CognitiveMemoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "cognitive.sqlite3"
        self.store = CognitiveMemoryStore(self.db_path)

    def tearDown(self):
        try:
            self.store.close()
        except sqlite3.ProgrammingError:
            pass
        self.temp_dir.cleanup()

    def observation(self, event_id="evt-observation-1"):
        return CognitiveEvent(
            event_id=event_id,
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-synthetic-1",
            event_type=OBSERVATION_EVENT,
            source="test.observation_fixture",
            payload={
                "observation_id": "obs-synthetic-1",
                "observation_kind": "text_fixture",
                "content": "A fictional blue paper boat floated beside a stone bridge.",
                "source_ref": "fixture://cognitive-slice/observation-1",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        )

    def proposal(self, event_id="evt-proposal-1", proposal_id="proposal-synthetic-1",
                 evidence_ids=None, state_version=0, content=None):
        return CognitiveEvent(
            event_id=event_id,
            occurred_at="2026-11-14T10:01:00+00:00",
            correlation_id="corr-synthetic-1",
            event_type=PROPOSAL_EVENT,
            source="test.memory_candidate_fixture",
            payload={
                "proposal_id": proposal_id,
                "memory_kind": "episodic_candidate",
                "candidate_content": content or (
                    "I encountered a fictional description of a blue paper boat "
                    "near a stone bridge."
                ),
                "evidence_event_ids": evidence_ids or ["evt-observation-1"],
                "origin": {"component": "test.memory_candidate_fixture", "version": "0.1"},
                "uncertainty": {"label": "fixture_only", "confidence": None},
                "based_on": {"state_version": state_version},
                "operation": "create",
            },
        )

    def seed_pending(self):
        self.store.submit_event(self.observation())
        self.store.submit_event(self.proposal())


    def test_memory_proposal_cannot_claim_a_future_snapshot_version(self):
        self.store.submit_event(self.observation())
        with self.assertRaisesRegex(ValueError, "future state_version"):
            self.store.submit_event(self.proposal(state_version=1))
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],
            0,
        )
        self.store.submit_event(self.proposal(state_version=0, proposal_id="valid-after-reject"))
        self.assertEqual(
            self.store.evaluate_proposal("valid-after-reject")["status"],
            "accepted",
        )

    def test_observation_is_not_automatically_a_memory(self):
        result = self.store.submit_event(self.observation())
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(self.store.get_memories(), [])
        self.assertEqual(self.store.get_state_snapshot()["accepted_memory_count"], 0)

    def test_candidate_proposal_is_not_an_accepted_memory(self):
        self.seed_pending()
        self.assertEqual(self.store.get_memories(), [])
        self.assertEqual(self.store.get_proposal("proposal-synthetic-1")["status"], "pending")

    def test_csd_evaluation_accepts_one_memory_with_provenance(self):
        self.seed_pending()
        result = self.store.evaluate_proposal("proposal-synthetic-1")
        self.assertEqual(result["status"], "accepted")
        memories = self.store.get_memories()
        self.assertEqual(len(memories), 1)
        memory = memories[0]
        self.assertEqual(memory["proposal_id"], "proposal-synthetic-1")
        self.assertEqual(memory["evidence_event_ids"], ["evt-observation-1"])
        self.assertEqual(memory["decision_event_id"], result["decision_event_id"])
        self.assertEqual(memory["status"], "accepted")
        self.assertEqual(memory["policy"]["id"], "csd.memory-provenance-check")

    def test_public_submit_cannot_claim_reserved_decision_event_id(self):
        reserved = CognitiveEvent(
            event_id="csd-decision:proposal-synthetic-1:1",
            occurred_at="2026-11-14T10:02:00+00:00",
            correlation_id="corr-synthetic-1",
            event_type=OBSERVATION_EVENT,
            source="test.fixture",
            payload={
                "observation_id": "obs-reserved",
                "observation_kind": "text_fixture",
                "content": "Reserved event identity test.",
                "source_ref": "fixture://reserved",
                "observed_at": "2026-11-14T10:01:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        )
        with self.assertRaises(ValueError):
            self.store.submit_event(reserved)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 0)

    def test_public_submit_cannot_forge_csd_decision(self):
        self.seed_pending()
        forged = CognitiveEvent(
            event_id="forged-decision",
            occurred_at="2026-11-14T10:02:00+00:00",
            correlation_id="corr-synthetic-1",
            event_type=DECISION_EVENT,
            source="test.fixture",
            payload={"proposal_id": "proposal-synthetic-1", "outcome": "accepted"},
        )
        with self.assertRaises(ValueError):
            self.store.submit_event(forged)
        self.assertEqual(self.store.get_memories(), [])

    def test_proposal_payload_cannot_smuggle_extra_authority_fields(self):
        self.store.submit_event(self.observation())
        event = self.proposal()
        payload = dict(event.payload)
        payload["accepted"] = True
        forged = CognitiveEvent(
            event_id=event.event_id,
            occurred_at=event.occurred_at,
            correlation_id=event.correlation_id,
            event_type=event.event_type,
            source=event.source,
            payload=payload,
        )
        with self.assertRaises(ValueError):
            self.store.submit_event(forged)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 1)
        self.assertEqual(self.store.get_memories(), [])


    def test_failed_commit_rolls_back_and_releases_transaction(self):
        with self.assertRaises(sqlite3.IntegrityError):
            with self.store._tx() as db:
                db.execute("PRAGMA defer_foreign_keys = ON")
                db.execute(
                    "INSERT INTO events(event_id,occurred_at,received_at,correlation_id,event_type,source,payload_ref,event_digest) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (
                        "event-with-missing-payload",
                        "2026-11-15T10:00:00+00:00",
                        "2026-11-15T10:00:01+00:00",
                        "corr-commit-failure",
                        OBSERVATION_EVENT,
                        "test.fixture",
                        "sha256:missing-payload",
                        "digest-placeholder",
                    ),
                )
        self.assertFalse(self.store._db.in_transaction)
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            0,
        )
        self.assertEqual(self.store.submit_event(self.observation())["status"], "accepted")


    def test_state_snapshot_is_consistent_during_concurrent_event_append(self):
        self.store.submit_event(self.observation())
        original_assert = self.store._assert_accepted_projection_consistent

        def append_during_snapshot():
            # A second SQLite connection is enough to interleave a committed
            # writer between reads while the snapshot connection holds BEGIN.
            # Keep connection creation and use on this same test thread because
            # sqlite3 connections enforce thread affinity by default.
            with CognitiveMemoryStore(self.db_path) as concurrent_store:
                concurrent_store.submit_event(
                    self.observation(event_id="evt-observation-concurrent-snapshot")
                )
            return original_assert()

        self.store._assert_accepted_projection_consistent = append_during_snapshot
        try:
            snapshot = self.store.get_state_snapshot()
        finally:
            self.store._assert_accepted_projection_consistent = original_assert

        self.assertEqual(snapshot["event_count"], 1)
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            2,
        )

    def test_same_event_id_and_content_is_idempotent(self):
        event = self.observation()
        first = self.store.submit_event(event)
        second = self.store.submit_event(event)
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 1)


    def test_duplicate_delivery_rejects_corrupted_prior_event_envelope(self):
        event = self.observation()
        self.store.submit_event(event)
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET event_digest='tampered' WHERE event_id=?",
            (event.event_id,),
        )
        with self.assertRaises(CognitiveIntegrityError):
            self.store.submit_event(event)
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            1,
        )

    def test_same_event_id_with_changed_content_conflicts(self):
        self.store.submit_event(self.observation())
        changed = self.observation()
        changed = CognitiveEvent(
            event_id=changed.event_id,
            occurred_at=changed.occurred_at,
            correlation_id=changed.correlation_id,
            event_type=changed.event_type,
            source=changed.source,
            payload={**changed.payload, "content": "Changed fixture"},
        )
        with self.assertRaises(CognitiveIdempotencyConflict):
            self.store.submit_event(changed)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 1)

    def test_same_proposal_identity_and_content_across_event_ids_is_one_proposal(self):
        self.store.submit_event(self.observation())
        first = self.proposal()
        second = self.proposal(event_id="evt-proposal-duplicate")
        self.store.submit_event(first)
        self.store.submit_event(second)
        state = self.store.get_state_snapshot()
        self.assertEqual(state["proposal_count"], 1)
        self.assertEqual(state["event_count"], 3)
        self.assertEqual(
            self.store.get_proposal("proposal-synthetic-1")["status"], "pending"
        )
        self.assertEqual(
            self.store.get_proposal("proposal-synthetic-1")["proposal"]["proposal_id"],
            "proposal-synthetic-1",
        )

    def test_same_proposal_identity_with_changed_content_conflicts(self):
        self.store.submit_event(self.observation())
        self.store.submit_event(self.proposal())
        changed = self.proposal(event_id="evt-proposal-conflict", content="A different claim.")
        with self.assertRaises(ProposalIdentityConflict):
            self.store.submit_event(changed)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 2)
        self.assertEqual(self.store.get_proposal("proposal-synthetic-1")["status"], "pending")

    def test_missing_evidence_produces_needs_more_evidence_not_memory(self):
        proposal = self.proposal(evidence_ids=["evt-missing"])
        self.store.submit_event(proposal)
        result = self.store.evaluate_proposal("proposal-synthetic-1")
        self.assertEqual(result["status"], "needs_more_evidence")
        self.assertEqual(self.store.get_memories(), [])
        self.assertEqual(
            self.store.get_proposal("proposal-synthetic-1")["status"],
            "needs_more_evidence",
        )

    def test_valid_observation_evidence_is_accepted(self):
        self.store.submit_event(CognitiveEvent(
            event_id="evt-other",
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-synthetic-1",
            event_type=OBSERVATION_EVENT,
            source="test.observation_fixture",
            payload={
                "observation_id": "obs-other",
                "observation_kind": "text_fixture",
                "content": "A separate fixture.",
                "source_ref": "fixture://other",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))
        self.store.submit_event(self.proposal(evidence_ids=["evt-other"]))
        self.assertEqual(
            self.store.evaluate_proposal("proposal-synthetic-1")["status"],
            "accepted",
        )

    def test_non_observation_event_cannot_be_used_as_evidence(self):
        # A proposal may only refer to observation event types. This event type
        # is outside the public schema, so submit it is rejected before storage.
        invalid = CognitiveEvent(
            event_id="evt-forbidden",
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-synthetic-1",
            event_type="action.like_result_observed.v1",
            source="test.fixture",
            payload={"result": "success"},
        )
        with self.assertRaises(ValueError):
            self.store.submit_event(invalid)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 0)

    def test_stale_proposal_is_deferred_after_another_memory_changes_state(self):
        self.seed_pending()
        self.assertEqual(
            self.store.evaluate_proposal("proposal-synthetic-1")["status"], "accepted"
        )
        stale = self.proposal(
            event_id="evt-proposal-2",
            proposal_id="proposal-synthetic-2",
            state_version=0,
        )
        self.store.submit_event(stale)
        result = self.store.evaluate_proposal("proposal-synthetic-2")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(len(self.store.get_memories()), 1)
        self.assertEqual(self.store.get_state_snapshot()["state_version"], 1)

    def test_decision_and_memory_projection_roll_back_together_on_failure(self):
        self.seed_pending()
        original = self.store._apply_projection_event

        def fail_on_decision(db, event, sequence, *, internal):
            if event.event_type == DECISION_EVENT:
                raise RuntimeError("injected failure before commit")
            return original(db, event, sequence, internal=internal)

        self.store._apply_projection_event = fail_on_decision
        with self.assertRaises(RuntimeError):
            self.store.evaluate_proposal("proposal-synthetic-1")
        self.store._apply_projection_event = original
        self.assertEqual(self.store.get_memories(), [])
        self.assertEqual(self.store.get_proposal("proposal-synthetic-1")["status"], "pending")
        self.assertEqual(
            self.store.get_state_snapshot()["event_count"], 2
        )

    def test_restart_and_recovery_preserve_accepted_memory(self):
        self.seed_pending()
        self.store.evaluate_proposal("proposal-synthetic-1")
        before = self.store.get_memories()
        self.store.close()
        self.store = CognitiveMemoryStore(self.db_path)
        result = self.store.recover()
        self.assertEqual(result["accepted_memories"], 1)
        self.assertEqual(self.store.get_memories(), before)

    def test_recovery_does_not_call_evaluator(self):
        self.seed_pending()
        self.store.evaluate_proposal("proposal-synthetic-1")

        def forbidden(*args, **kwargs):
            raise AssertionError("recovery must not evaluate proposals")

        self.store.evaluate_proposal = forbidden
        result = self.store.recover()
        self.assertEqual(result["accepted_memories"], 1)

    def test_recovery_detects_accepted_memory_content_tampering(self):
        self.seed_pending()
        self.assertEqual(
            self.store.evaluate_proposal("proposal-synthetic-1")["status"],
            "accepted",
        )
        expected = self.store.get_memory("csd-memory:proposal-synthetic-1")
        self.store._db.execute(
            "UPDATE accepted_memories SET memory_json='{}' "
            "WHERE memory_id='csd-memory:proposal-synthetic-1'"
        )
        self.assertFalse(self.store.get_state_snapshot()["projection_consistent"])
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_memory("csd-memory:proposal-synthetic-1")
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_memories()

        self.store.recover()
        self.assertTrue(self.store.get_state_snapshot()["projection_consistent"])
        self.assertEqual(
            self.store.get_memory("csd-memory:proposal-synthetic-1"),
            expected,
        )

    def test_memory_proposal_projection_status_is_checked_against_event_history(self):
        self.seed_pending()
        self.store.evaluate_proposal("proposal-synthetic-1")
        self.store._db.execute(
            "UPDATE proposals SET status='pending',decision_event_id=NULL "
            "WHERE proposal_id='proposal-synthetic-1'"
        )
        self.assertFalse(self.store.get_state_snapshot()["projection_consistent"])
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_proposal("proposal-synthetic-1")

        self.store.recover()
        self.assertEqual(
            self.store.get_proposal("proposal-synthetic-1")["status"],
            "accepted",
        )

    def test_recovery_rebuilds_deleted_projection_from_events(self):
        self.seed_pending()
        self.store.evaluate_proposal("proposal-synthetic-1")
        self.store._db.execute("DELETE FROM accepted_memories")
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_memories()
        self.assertFalse(self.store.get_state_snapshot()["projection_consistent"])
        result = self.store.recover()
        self.assertEqual(result["accepted_memories"], 1)
        self.assertEqual(len(self.store.get_memories()), 1)

    def test_evaluation_refuses_out_of_sync_memory_projection(self):
        self.seed_pending()
        self.store.evaluate_proposal("proposal-synthetic-1")
        self.store.submit_event(self.proposal(
            event_id="evt-proposal-2",
            proposal_id="proposal-synthetic-2",
            state_version=1,
        ))
        self.store._db.execute("DELETE FROM accepted_memories")
        with self.assertRaises(CognitiveIntegrityError):
            self.store.evaluate_proposal("proposal-synthetic-2")
        self.assertEqual(
            self.store.get_proposal("proposal-synthetic-2")["status"], "pending"
        )
        self.assertFalse(self.store.get_state_snapshot()["projection_consistent"])
        self.store.recover()
        self.assertTrue(self.store.get_state_snapshot()["projection_consistent"])
        self.assertEqual(
            self.store.evaluate_proposal("proposal-synthetic-2")["status"], "accepted"
        )



    def test_recovery_takes_event_snapshot_after_acquiring_writer_transaction(self):
        self.store.submit_event(self.observation())
        concurrent_store = CognitiveMemoryStore(self.db_path)
        original_tx = self.store._tx

        def append_before_recovery_transaction():
            # On the old implementation this hook ran after Recovery had already
            # fetched its event rows. With the lock moved to the start, the event
            # is appended before the snapshot query and must be included.
            concurrent_store.submit_event(
                self.observation(event_id="evt-observation-appended-during-recovery-entry")
            )
            return original_tx()

        self.store._tx = append_before_recovery_transaction
        try:
            recovered = self.store.recover()
        finally:
            self.store._tx = original_tx
            concurrent_store.close()

        self.assertEqual(recovered["events"], 2)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 2)


    def test_recovery_rejects_reserved_decision_namespace_on_observation_event(self):
        self.store.submit_event(self.observation())
        base_event = self.observation(event_id="csd-decision:forged-observation:1")
        event = CognitiveEvent(
            event_id=base_event.event_id,
            occurred_at=base_event.occurred_at,
            correlation_id=base_event.correlation_id,
            event_type=base_event.event_type,
            source=base_event.source,
            payload={**dict(base_event.payload), "observation_id": "obs-reserved-durable"},
        )
        payload_json = json.dumps(
            dict(event.payload), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        payload_ref = "sha256:" + hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        received_at = "2026-11-15T10:02:00+00:00"
        event_digest = self.store._event_digest(event, payload_ref, received_at)
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (payload_ref, payload_json),
        )
        self.store._db.execute(
            "INSERT INTO events(event_id,occurred_at,received_at,correlation_id,event_type,source,payload_ref,event_digest) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                event.event_id, event.occurred_at, received_at, event.correlation_id,
                event.event_type, event.source, payload_ref, event_digest,
            ),
        )
        with self.assertRaisesRegex(CognitiveIntegrityError, "invalid durable event envelope"):
            self.store.recover()
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],
            0,
        )

    def test_recovery_rejects_future_snapshot_proposal_in_durable_history(self):
        self.store.submit_event(self.observation())
        event = self.proposal(state_version=1)
        payload_json = json.dumps(
            dict(event.payload), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        payload_ref = "sha256:" + hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        received_at = "2026-11-14T10:02:00+00:00"
        event_digest = self.store._event_digest(event, payload_ref, received_at)
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (payload_ref, payload_json),
        )
        self.store._db.execute(
            "INSERT INTO events(event_id,occurred_at,received_at,correlation_id,event_type,source,payload_ref,event_digest) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                event.event_id, event.occurred_at, received_at, event.correlation_id,
                event.event_type, event.source, payload_ref, event_digest,
            ),
        )
        with self.assertRaises(CognitiveIntegrityError):
            self.store.recover()
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM events").fetchone()[0],
            2,
        )
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],
            0,
        )

    def test_recovery_rejects_event_digest_tampering(self):
        self.store.submit_event(self.observation())
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET event_digest='tampered' WHERE event_id='evt-observation-1'"
        )
        with self.assertRaises(CognitiveIntegrityError):
            self.store.recover()

    def test_evaluating_same_proposal_twice_does_not_duplicate_memory(self):
        self.seed_pending()
        first = self.store.evaluate_proposal("proposal-synthetic-1")
        second = self.store.evaluate_proposal("proposal-synthetic-1")
        self.assertEqual(first["status"], "accepted")
        self.assertEqual(second["status"], "already_decided")
        self.assertEqual(len(self.store.get_memories()), 1)
        self.assertEqual(self.store.get_state_snapshot()["state_version"], 1)

    def test_concurrent_evaluation_commits_exactly_one_decision(self):
        self.seed_pending()
        self.store.close()

        def evaluate_in_own_connection():
            with CognitiveMemoryStore(self.db_path) as worker_store:
                return worker_store.evaluate_proposal("proposal-synthetic-1")

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(evaluate_in_own_connection),
                pool.submit(evaluate_in_own_connection),
            ]
            results = [future.result() for future in futures]

        self.store = CognitiveMemoryStore(self.db_path)
        self.assertEqual(
            sorted(result["status"] for result in results),
            ["accepted", "already_decided"],
        )
        self.assertEqual(len(self.store.get_memories()), 1)
        self.assertEqual(self.store.get_state_snapshot()["state_version"], 1)


if __name__ == "__main__":
    unittest.main()
