from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from core.csd import CognitiveEvent, CognitiveMemoryStore, SemanticReviewCandidate
from core.csd.cognitive import (
    DECISION_EVENT,
    GROUNDED_PROPOSAL_EVENT,
    OBSERVATION_EVENT,
    SEMANTIC_REVIEW_EVENT,
    SemanticReviewIdentityConflict,
)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


class SemanticReviewStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "semantic-review.sqlite3"
        self.store = CognitiveMemoryStore(self.db_path)
        self.source_text = "A silver leaf rested on the windowsill."
        self.store.submit_event(CognitiveEvent(
            event_id="evt-review-source",
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-review",
            event_type=OBSERVATION_EVENT,
            source="test.observation",
            payload={
                "observation_id": "obs-review",
                "observation_kind": "text_fixture",
                "content": self.source_text,
                "source_ref": "fixture://semantic-review/source",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def source_claim(self, claim_id="claim-source-1"):
        return {
            "claim_id": claim_id,
            "text": self.source_text,
            "epistemic_type": "source_assertion",
            "evidence": [{
                "event_id": "evt-review-source",
                "locator": {
                    "kind": "text_range", "unit": "unicode_codepoint",
                    "start": 0, "end": len(self.source_text),
                },
                "quoted_text": self.source_text,
            }],
            "uncertainty": {"label": "directly_quoted", "confidence": None},
        }

    def inference_claim(self, claim_id="claim-inference-1", source_ids=None):
        return {
            "claim_id": claim_id,
            "text": "The scene may feel calm and delicate.",
            "epistemic_type": "inference",
            "derived_from_claim_ids": source_ids or ["claim-source-1"],
            "reasoning_summary": "A tentative stylistic interpretation.",
            "uncertainty": {"label": "tentative_inference", "confidence": 0.4},
        }

    def submit_proposal(self, proposal_id="proposal-review-1", two_inferences=False,
                        bad_source=False, state_version=None):
        source = self.source_claim()
        if bad_source:
            source["text"] = "A paraphrase not present in the source."
        claims = [source]
        claims.append(self.inference_claim())
        if two_inferences:
            claims.append(self.inference_claim("claim-inference-2"))
        event = CognitiveEvent(
            event_id=f"evt-{proposal_id}",
            occurred_at="2026-11-14T10:01:00+00:00",
            correlation_id="corr-review",
            event_type=GROUNDED_PROPOSAL_EVENT,
            source="test.grounded",
            payload={
                "proposal_id": proposal_id,
                "memory_kind": "episodic_candidate",
                "claims": claims,
                "origin": {"component": "test.grounded", "version": "0.2"},
                "based_on": {"state_version": (
                    self.store.get_state_snapshot()["state_version"]
                    if state_version is None else state_version
                )},
                "operation": "create",
            },
        )
        self.store.submit_event(event)
        return event

    def make_review(self, proposal_id="proposal-review-1",
                    claim_id="claim-inference-1", outcome="supported",
                    review_id="review-1", support_ids=None,
                    alter_proposal_digest=None, alter_claim_digest=None,
                    reasoning="Synthetic review; not a truth oracle."):
        stored = self.store.get_proposal(proposal_id)
        claim = next(
            item for item in stored["proposal"]["claims"]
            if item["claim_id"] == claim_id
        )
        payload = {
            "review_id": review_id,
            "proposal_id": proposal_id,
            "proposal_event_id": stored["proposal_event_id"],
            "proposal_digest": alter_proposal_digest or stored["proposal_digest"],
            "claim_id": claim_id,
            "claim_digest": alter_claim_digest or digest(claim),
            "reviewer": {"component": "test.reviewer", "version": "0.1"},
            "contract_version": "semantic-review.v1",
            "outcome": outcome,
            "reasoning_summary": reasoning,
            "supporting_claim_ids": support_ids if support_ids is not None else ["claim-source-1"],
            "alternative_explanations": ["The scene could have another interpretation."],
            "limitations": ["Only one short text source was supplied."],
        }
        return CognitiveEvent(
            event_id=f"evt-{review_id}",
            occurred_at="2026-11-14T10:02:00+00:00",
            correlation_id="corr-review",
            event_type=SEMANTIC_REVIEW_EVENT,
            source="semantic-review.pipeline:test.reviewer",
            payload=payload,
        )

    def add_review(self, **kwargs):
        return self.store.submit_event(self.make_review(**kwargs))

    def test_get_event_rejects_schema_invalid_observation_with_valid_digests(self):
        original = self.store.get_event("evt-review-source")
        malformed_payload = dict(original["payload"])
        malformed_payload["observation_kind"] = ""
        malformed_json = canonical(malformed_payload)
        new_payload_ref = "sha256:" + hashlib.sha256(
            malformed_json.encode("utf-8")
        ).hexdigest()
        row = self.store._db.execute(
            "SELECT received_at FROM events WHERE event_id=?",
            (original["event_id"],),
        ).fetchone()

        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (new_payload_ref, malformed_json),
        )
        corrupted_event = CognitiveEvent(
            event_id=original["event_id"],
            occurred_at=original["occurred_at"],
            correlation_id=original["correlation_id"],
            event_type=original["event_type"],
            source=original["source"],
            payload=malformed_payload,
        )
        event_digest = self.store._event_digest(
            corrupted_event, new_payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (new_payload_ref, event_digest, original["event_id"]),
        )

        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "invalid prior event schema"
        ):
            self.store.get_event(original["event_id"])

    def test_no_review_keeps_proposal_pending_without_decision_event(self):
        self.submit_proposal()
        before = self.store.get_state_snapshot()["event_count"]
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "awaiting_review")
        self.assertEqual(result["claim_ids"], ["claim-inference-1"])
        self.assertEqual(self.store.get_proposal("proposal-review-1")["status"], "pending")
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)
        self.assertEqual(self.store.get_memories(), [])

    def test_recovery_rejects_memory_decision_with_rebound_wrong_correlation(self):
        self.submit_proposal()
        self.add_review()
        decision = self.store.evaluate_proposal("proposal-review-1")
        event_id = decision["decision_event_id"]
        stored = self.store.get_event(event_id)
        row = self.store._db.execute(
            "SELECT payload_ref,received_at FROM events WHERE event_id=?",
            (event_id,),
        ).fetchone()
        corrupted = CognitiveEvent(
            event_id=stored["event_id"],
            occurred_at=stored["occurred_at"],
            correlation_id="proposal:wrong-identity",
            event_type=stored["event_type"],
            source=stored["source"],
            payload=stored["payload"],
        )
        digest = self.store._event_digest(
            corrupted, row["payload_ref"], row["received_at"]
        )
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET correlation_id=?,event_digest=? WHERE event_id=?",
            (corrupted.correlation_id, digest, event_id),
        )
        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "identity or correlation_id mismatch"
        ):
            self.store.get_memories()
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "identity or correlation_id mismatch"
        ):
            self.store.recover()

    def test_recovery_rejects_memory_decision_with_rebound_wrong_event_id(self):
        self.submit_proposal()
        self.add_review()
        decision = self.store.evaluate_proposal("proposal-review-1")
        event_id = decision["decision_event_id"]
        stored = self.store.get_event(event_id)
        row = self.store._db.execute(
            "SELECT payload_ref,received_at FROM events WHERE event_id=?",
            (event_id,),
        ).fetchone()
        corrupted = CognitiveEvent(
            event_id="csd-decision:proposal-review-1:999",
            occurred_at=stored["occurred_at"],
            correlation_id=stored["correlation_id"],
            event_type=stored["event_type"],
            source=stored["source"],
            payload=stored["payload"],
        )
        digest = self.store._event_digest(
            corrupted, row["payload_ref"], row["received_at"]
        )
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET event_id=?,event_digest=? WHERE event_id=?",
            (corrupted.event_id, digest, event_id),
        )
        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "identity or correlation_id mismatch"
        ):
            self.store.get_memories()
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "identity or correlation_id mismatch"
        ):
            self.store.recover()

    def test_supported_review_allows_csd_to_accept_and_preserves_review_ref(self):
        self.submit_proposal()
        review = self.add_review()
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "accepted")
        memory = self.store.get_memories()[0]
        self.assertEqual(memory["semantic_review_status"], "supported")
        self.assertEqual(memory["semantic_review_event_ids"], [review["event_id"]])
        self.assertEqual(memory["claims"][1]["epistemic_type"], "inference")
        self.assertEqual(
            self.store.get_proposal("proposal-review-1")["status"], "accepted"
        )

    def test_uncertain_review_defers_proposal(self):
        self.submit_proposal()
        self.add_review(outcome="uncertain")
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(self.store.get_memories(), [])

    def test_unsupported_review_rejects_proposal(self):
        self.submit_proposal()
        self.add_review(outcome="unsupported")
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.get_memories(), [])

    def test_insufficient_context_maps_to_needs_more_evidence(self):
        self.submit_proposal()
        self.add_review(outcome="insufficient_context")
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "needs_more_evidence")
        self.assertEqual(self.store.get_memories(), [])

    def test_conflicting_reviews_are_preserved_and_deferred(self):
        self.submit_proposal()
        first = self.add_review(outcome="supported", review_id="review-supported")
        second = self.add_review(outcome="uncertain", review_id="review-uncertain")
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(
            {item["event_id"] for item in self.store.get_semantic_reviews("proposal-review-1")},
            {first["event_id"], second["event_id"]},
        )
        self.assertEqual(self.store.get_memories(), [])

    def test_all_inference_claims_need_reviews(self):
        self.submit_proposal(two_inferences=True)
        self.add_review(claim_id="claim-inference-1", review_id="review-one")
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "awaiting_review")
        self.assertEqual(result["claim_ids"], ["claim-inference-2"])
        self.add_review(claim_id="claim-inference-2", review_id="review-two")
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(len(self.store.get_memories()[0]["semantic_review_event_ids"]), 2)

    def test_proposal_digest_mismatch_is_rejected(self):
        self.submit_proposal()
        event = self.make_review(alter_proposal_digest="sha256:wrong")
        before = self.store.get_state_snapshot()["event_count"]
        with self.assertRaises(ValueError):
            self.store.submit_event(event)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)

    def test_claim_digest_mismatch_is_rejected(self):
        self.submit_proposal()
        event = self.make_review(alter_claim_digest="sha256:wrong")
        with self.assertRaises(ValueError):
            self.store.submit_event(event)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 2)

    def test_review_cannot_target_source_assertion(self):
        self.submit_proposal()
        event = self.make_review(claim_id="claim-source-1")
        with self.assertRaises(ValueError):
            self.store.submit_event(event)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 2)

    def test_supporting_claims_must_be_direct_declared_sources(self):
        self.submit_proposal()
        event = self.make_review(support_ids=["claim-not-in-proposal"])
        with self.assertRaises(ValueError):
            self.store.submit_event(event)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 2)

    def test_identical_review_id_and_payload_is_idempotent(self):
        self.submit_proposal()
        event = self.make_review(review_id="review-idempotent")
        first = self.store.submit_event(event)
        duplicate = CognitiveEvent(
            event_id="evt-review-idempotent-retry",
            occurred_at="2026-11-14T10:03:00+00:00",
            correlation_id=event.correlation_id,
            event_type=event.event_type,
            source=event.source,
            payload=dict(event.payload),
        )
        before = self.store.get_state_snapshot()["event_count"]
        result = self.store.submit_event(duplicate)
        self.assertEqual(result["status"], "duplicate_review")
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)
        self.assertEqual(self.store.get_semantic_reviews("proposal-review-1")[0]["event_id"], first["event_id"])


    def test_duplicate_review_rejects_corrupted_prior_event_envelope(self):
        self.submit_proposal()
        original = self.make_review(review_id="review-corrupt-retry")
        self.store.submit_event(original)
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET event_digest='tampered' WHERE event_id=?",
            (original.event_id,),
        )
        retry = CognitiveEvent(
            event_id="evt-review-corrupt-retry-delivery",
            occurred_at="2026-11-14T10:03:00+00:00",
            correlation_id=original.correlation_id,
            event_type=original.event_type,
            source=original.source,
            payload=dict(original.payload),
        )
        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaises(CognitiveIntegrityError):
            self.store.submit_event(retry)
        self.assertEqual(
            self.store._db.execute(
                "SELECT COUNT(*) FROM events WHERE event_type=?",
                (SEMANTIC_REVIEW_EVENT,),
            ).fetchone()[0],
            1,
        )

    def test_duplicate_review_rejects_noncanonical_prior_payload_even_with_matching_digests(self):
        self.submit_proposal()
        original = self.make_review(review_id="review-noncanonical-retry")
        self.store.submit_event(original)

        row = self.store._db.execute(
            "SELECT e.payload_ref,p.payload_json,e.received_at FROM events e "
            "JOIN payloads p ON p.payload_ref=e.payload_ref WHERE e.event_id=?",
            (original.event_id,),
        ).fetchone()
        noncanonical_json = json.dumps(
            json.loads(row["payload_json"]), ensure_ascii=False, indent=2
        )
        new_payload_ref = "sha256:" + hashlib.sha256(
            noncanonical_json.encode("utf-8")
        ).hexdigest()
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (new_payload_ref, noncanonical_json),
        )
        corrupted_event = CognitiveEvent(
            event_id=original.event_id,
            occurred_at=original.occurred_at,
            correlation_id=original.correlation_id,
            event_type=original.event_type,
            source=original.source,
            payload=original.payload,
        )
        event_digest = self.store._event_digest(
            corrupted_event, new_payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (new_payload_ref, event_digest, original.event_id),
        )

        retry = CognitiveEvent(
            event_id="evt-review-noncanonical-retry-delivery",
            occurred_at="2026-11-14T10:03:00+00:00",
            correlation_id=original.correlation_id,
            event_type=original.event_type,
            source=original.source,
            payload=dict(original.payload),
        )
        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "not canonically serialized"
        ):
            self.store.submit_event(retry)
        self.assertEqual(
            self.store._db.execute(
                "SELECT COUNT(*) FROM events WHERE event_type=?",
                (SEMANTIC_REVIEW_EVENT,),
            ).fetchone()[0],
            1,
        )

    def test_same_event_id_duplicate_rejects_decision_with_extra_payload_field(self):
        self.submit_proposal()
        self.store.submit_event(self.make_review())
        decision = self.store.evaluate_proposal("proposal-review-1")
        stored = self.store.get_event(decision["decision_event_id"])
        row = self.store._db.execute(
            "SELECT received_at FROM events WHERE event_id=?",
            (stored["event_id"],),
        ).fetchone()
        malformed_payload = dict(stored["payload"])
        malformed_payload["unexpected"] = "tampered"
        malformed_json = canonical(malformed_payload)
        new_payload_ref = "sha256:" + hashlib.sha256(
            malformed_json.encode("utf-8")
        ).hexdigest()
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (new_payload_ref, malformed_json),
        )
        corrupted_event = CognitiveEvent(
            event_id=stored["event_id"],
            occurred_at=stored["occurred_at"],
            correlation_id=stored["correlation_id"],
            event_type=stored["event_type"],
            source=stored["source"],
            payload=malformed_payload,
        )
        event_digest = self.store._event_digest(
            corrupted_event, new_payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (new_payload_ref, event_digest, stored["event_id"]),
        )
        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "durable decision contains missing or unsupported fields"
        ):
            self.store._append_event(
                corrupted_event, malformed_json, internal=True
            )

    def test_same_event_id_internal_decision_retry_remains_idempotent(self):
        self.submit_proposal()
        self.store.submit_event(self.make_review())
        decision = self.store.evaluate_proposal("proposal-review-1")
        stored = self.store.get_event(decision["decision_event_id"])
        retry = CognitiveEvent(
            event_id=stored["event_id"],
            occurred_at=stored["occurred_at"],
            correlation_id=stored["correlation_id"],
            event_type=stored["event_type"],
            source=stored["source"],
            payload=dict(stored["payload"]),
        )
        payload_json = canonical(dict(retry.payload))
        result = self.store._append_event(retry, payload_json, internal=True)
        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["event_id"], retry.event_id)

    def test_same_event_id_duplicate_rejects_prior_event_with_invalid_review_schema(self):
        self.submit_proposal()
        original = self.make_review(review_id="review-same-event-invalid-schema")
        self.store.submit_event(original)
        stored = self.store.get_event(original.event_id)
        row = self.store._db.execute(
            "SELECT received_at FROM events WHERE event_id=?",
            (original.event_id,),
        ).fetchone()
        malformed_payload = dict(stored["payload"])
        malformed_payload["outcome"] = "not-a-review-outcome"
        malformed_json = canonical(malformed_payload)
        new_payload_ref = "sha256:" + hashlib.sha256(
            malformed_json.encode("utf-8")
        ).hexdigest()
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (new_payload_ref, malformed_json),
        )
        corrupted_event = CognitiveEvent(
            event_id=original.event_id,
            occurred_at=original.occurred_at,
            correlation_id=original.correlation_id,
            event_type=original.event_type,
            source=original.source,
            payload=malformed_payload,
        )
        event_digest = self.store._event_digest(
            corrupted_event, new_payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (new_payload_ref, event_digest, original.event_id),
        )

        from core.csd.cognitive import CognitiveIntegrityError
        retry = CognitiveEvent(
            event_id=original.event_id,
            occurred_at=original.occurred_at,
            correlation_id=original.correlation_id,
            event_type=original.event_type,
            source=original.source,
            payload=malformed_payload,
        )
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "invalid prior event schema"
        ):
            self.store.submit_event(retry)

    def test_duplicate_review_rejects_prior_event_with_invalid_review_schema(self):
        self.submit_proposal()
        original = self.make_review(review_id="review-invalid-schema-retry")
        self.store.submit_event(original)
        stored = self.store.get_event(original.event_id)
        row = self.store._db.execute(
            "SELECT received_at FROM events WHERE event_id=?",
            (original.event_id,),
        ).fetchone()
        malformed_payload = dict(stored["payload"])
        malformed_payload["outcome"] = "not-a-review-outcome"
        malformed_json = canonical(malformed_payload)
        new_payload_ref = "sha256:" + hashlib.sha256(
            malformed_json.encode("utf-8")
        ).hexdigest()
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (new_payload_ref, malformed_json),
        )
        corrupted_event = CognitiveEvent(
            event_id=original.event_id,
            occurred_at=original.occurred_at,
            correlation_id=original.correlation_id,
            event_type=original.event_type,
            source=original.source,
            payload=malformed_payload,
        )
        event_digest = self.store._event_digest(
            corrupted_event, new_payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (new_payload_ref, event_digest, original.event_id),
        )
        retry = CognitiveEvent(
            event_id="evt-review-invalid-schema-retry-delivery",
            occurred_at="2026-11-14T10:03:00+00:00",
            correlation_id=original.correlation_id,
            event_type=original.event_type,
            source=original.source,
            payload=malformed_payload,
        )

        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "invalid prior semantic review event"
        ):
            self.store.submit_event(retry)

    def test_duplicate_event_rejects_prior_event_with_invalid_timestamp_as_integrity_error(self):
        self.submit_proposal()
        original = self.make_review()
        self.store.submit_event(original)
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET occurred_at=? WHERE event_id=?",
            ("not-a-timestamp", original.event_id),
        )

        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "invalid durable event envelope"
        ):
            self.store.submit_event(original)
        self.assertEqual(
            self.store._db.execute(
                "SELECT COUNT(*) FROM events WHERE event_type=?",
                (SEMANTIC_REVIEW_EVENT,),
            ).fetchone()[0],
            1,
        )

    def test_event_reads_and_recovery_reject_non_text_payload_storage(self):
        self.submit_proposal()
        review = self.make_review()
        self.store.submit_event(review)
        row = self.store._db.execute(
            "SELECT payload_ref FROM events WHERE event_id=?",
            (review.event_id,),
        ).fetchone()
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "UPDATE payloads SET payload_json=? WHERE payload_ref=?",
            (b"{}", row["payload_ref"]),
        )

        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(CognitiveIntegrityError, "not stored as text"):
            self.store.get_event(review.event_id)
        with self.assertRaisesRegex(CognitiveIntegrityError, "not stored as text"):
            self.store.recover()

    def test_event_reads_and_recovery_normalize_deeply_nested_payload_json(self):
        self.submit_proposal()
        review = self.make_review()
        self.store.submit_event(review)
        row = self.store._db.execute(
            "SELECT e.payload_ref,e.received_at FROM events e WHERE e.event_id=?",
            (review.event_id,),
        ).fetchone()
        nested_json = "[" * 2000 + "0" + "]" * 2000
        new_payload_ref = "sha256:" + hashlib.sha256(
            nested_json.encode("utf-8")
        ).hexdigest()
        corrupted = CognitiveEvent(
            event_id=review.event_id,
            occurred_at=review.occurred_at,
            correlation_id=review.correlation_id,
            event_type=review.event_type,
            source=review.source,
            payload=review.payload,
        )
        event_digest = self.store._event_digest(
            corrupted, new_payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (new_payload_ref, nested_json),
        )
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (new_payload_ref, event_digest, review.event_id),
        )

        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_event(review.event_id)
        with self.assertRaises(CognitiveIntegrityError):
            self.store.recover()

    def test_recovery_normalizes_malformed_event_timestamp(self):
        self.submit_proposal()
        review = self.make_review()
        self.store.submit_event(review)
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET occurred_at=? WHERE event_id=?",
            ("not-a-timestamp", review.event_id),
        )

        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "invalid durable event envelope"
        ):
            self.store.recover()

    def test_recovery_normalizes_invalid_observation_projection(self):
        original = self.store.get_event("evt-review-source")
        row = self.store._db.execute(
            "SELECT received_at FROM events WHERE event_id=?",
            ("evt-review-source",),
        ).fetchone()
        malformed_payload = dict(original["payload"])
        malformed_payload["coverage"] = {
            "modality": "text",
            "complete_for_fixture": "yes",
        }
        malformed_json = canonical(malformed_payload)
        new_payload_ref = "sha256:" + hashlib.sha256(
            malformed_json.encode("utf-8")
        ).hexdigest()
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (new_payload_ref, malformed_json),
        )
        corrupted_event = CognitiveEvent(
            event_id=original["event_id"],
            occurred_at=original["occurred_at"],
            correlation_id=original["correlation_id"],
            event_type=original["event_type"],
            source=original["source"],
            payload=malformed_payload,
        )
        event_digest = self.store._event_digest(
            corrupted_event, new_payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (new_payload_ref, event_digest, original["event_id"]),
        )

        from core.csd.cognitive import CognitiveIntegrityError
        with self.assertRaisesRegex(
            CognitiveIntegrityError, "invalid durable event projection"
        ):
            self.store.recover()

    def test_same_review_id_with_changed_content_conflicts(self):
        self.submit_proposal()
        first = self.make_review(review_id="review-conflict")
        self.store.submit_event(first)
        changed = self.make_review(
            review_id="review-conflict",
            outcome="unsupported",
            reasoning="Changed review content.",
        )
        changed = CognitiveEvent(
            event_id="evt-review-conflict-changed",
            occurred_at=changed.occurred_at,
            correlation_id=changed.correlation_id,
            event_type=changed.event_type,
            source=changed.source,
            payload=changed.payload,
        )
        with self.assertRaises(SemanticReviewIdentityConflict):
            self.store.submit_event(changed)

    def test_review_after_terminal_decision_is_rejected(self):
        self.submit_proposal()
        self.add_review()
        self.assertEqual(self.store.evaluate_proposal("proposal-review-1")["status"], "accepted")
        late = self.make_review(review_id="review-too-late")
        with self.assertRaises(ValueError):
            self.store.submit_event(late)

    def test_recovery_restores_review_events_without_reviewer_invocation(self):
        self.submit_proposal()
        self.add_review()
        expected = self.store.get_semantic_reviews("proposal-review-1")
        self.store.close()
        self.store = CognitiveMemoryStore(self.db_path)
        result = self.store.recover()
        self.assertEqual(result["proposals"], 1)
        self.assertEqual(self.store.get_semantic_reviews("proposal-review-1"), expected)
        self.assertEqual(
            self.store.evaluate_proposal("proposal-review-1")["status"], "accepted"
        )

    def test_invalid_deterministic_source_is_rejected_without_required_review(self):
        self.submit_proposal(bad_source=True)
        result = self.store.evaluate_proposal("proposal-review-1")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.get_semantic_reviews("proposal-review-1"), [])
        self.assertEqual(self.store.get_memories(), [])

    def test_stale_inference_proposal_still_waits_for_required_review(self):
        self.submit_proposal("first-proposal", two_inferences=False)
        self.add_review(proposal_id="first-proposal", review_id="first-review")
        self.assertEqual(self.store.evaluate_proposal("first-proposal")["status"], "accepted")
        self.submit_proposal("stale-proposal", two_inferences=False, state_version=0)
        result = self.store.evaluate_proposal("stale-proposal")
        self.assertEqual(result["status"], "awaiting_review")
        self.assertEqual(self.store.get_proposal("stale-proposal")["status"], "pending")
        self.add_review(
            proposal_id="stale-proposal",
            review_id="stale-review",
        )
        result = self.store.evaluate_proposal("stale-proposal")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(len(self.store.get_memories()), 1)


if __name__ == "__main__":
    unittest.main()
