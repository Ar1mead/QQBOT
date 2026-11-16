from __future__ import annotations

from pathlib import Path
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
    ProposalIdentityConflict,
)
from core.csd.cognitive import (
    DECISION_EVENT,
    GROUNDED_PROPOSAL_EVENT,
    OBSERVATION_EVENT,
    PROPOSAL_EVENT,
)


class GroundedMemoryV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "grounded.sqlite3"
        self.store = CognitiveMemoryStore(self.db_path)
        self.source_text = "A blue paper boat passed the bridge. 🌉 The scene was quiet."
        self.observation = CognitiveEvent(
            event_id="evt-grounded-observation",
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-grounded",
            event_type=OBSERVATION_EVENT,
            source="test.observation_fixture",
            payload={
                "observation_id": "obs-grounded",
                "observation_kind": "text_fixture",
                "content": self.source_text,
                "source_ref": "fixture://grounded/observation",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        )
        self.store.submit_event(self.observation)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def source_claim(self, *, claim_id="claim-source-1", quote=None,
                     start=None, end=None, event_id="evt-grounded-observation"):
        quote = quote or "A blue paper boat passed the bridge."
        if start is None:
            start = self.source_text.index(quote)
        if end is None:
            end = start + len(quote)
        return {
            "claim_id": claim_id,
            "text": quote,
            "epistemic_type": "source_assertion",
            "evidence": [{
                "event_id": event_id,
                "locator": {
                    "kind": "text_range",
                    "unit": "unicode_codepoint",
                    "start": start,
                    "end": end,
                },
                "quoted_text": quote,
            }],
            "uncertainty": {"label": "directly_quoted", "confidence": None},
        }

    def inference_claim(self, *, claim_id="claim-inference-1", refs=None,
                        text="The description may evoke a quiet mood."):
        return {
            "claim_id": claim_id,
            "text": text,
            "epistemic_type": "inference",
            "derived_from_claim_ids": refs or ["claim-source-1"],
            "reasoning_summary": "This is a tentative interpretation of the cited source description.",
            "uncertainty": {"label": "tentative_inference", "confidence": 0.42},
        }

    def proposal(self, *, event_id="evt-grounded-proposal",
                 proposal_id="grounded-proposal-1", claims=None, state_version=0):
        return CognitiveEvent(
            event_id=event_id,
            occurred_at="2026-11-14T10:01:00+00:00",
            correlation_id="corr-grounded",
            event_type=GROUNDED_PROPOSAL_EVENT,
            source="test.grounded_memory_fixture",
            payload={
                "proposal_id": proposal_id,
                "memory_kind": "episodic_candidate",
                "claims": claims if claims is not None else [self.source_claim()],
                "origin": {"component": "test.grounded_memory_fixture", "version": "0.2"},
                "based_on": {"state_version": state_version},
                "operation": "create",
            },
        )

    def submit_pending(self, **kwargs):
        event = self.proposal(**kwargs)
        self.store.submit_event(event)
        return event

    def rewrite_event_payload_with_valid_digests(self, event_id, mutate):
        original = self.store.get_event(event_id)
        payload = dict(original["payload"])
        mutate(payload)
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        payload_ref = "sha256:" + hashlib.sha256(
            payload_json.encode("utf-8")
        ).hexdigest()
        row = self.store._db.execute(
            "SELECT received_at FROM events WHERE event_id=?", (event_id,)
        ).fetchone()
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (payload_ref, payload_json),
        )
        rewritten = CognitiveEvent(
            event_id=original["event_id"],
            occurred_at=original["occurred_at"],
            correlation_id=original["correlation_id"],
            event_type=original["event_type"],
            source=original["source"],
            payload=payload,
        )
        event_digest = self.store._event_digest(
            rewritten, payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (payload_ref, event_digest, event_id),
        )

    def submit_supported_review(self, proposal_id="grounded-proposal-1",
                                claim_id="claim-inference-1",
                                review_id="review-supported-1",
                                outcome="supported",
                                supporting_claim_ids=None):
        stored = self.store.get_proposal(proposal_id)
        claim = next(
            item for item in stored["proposal"]["claims"]
            if item["claim_id"] == claim_id
        )
        canonical = lambda value: json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        digest = lambda value: "sha256:" + hashlib.sha256(
            canonical(value).encode("utf-8")
        ).hexdigest()
        event = CognitiveEvent(
            event_id=f"evt-{review_id}",
            occurred_at="2026-11-14T10:02:00+00:00",
            correlation_id="corr-grounded",
            event_type="cognition.semantic_review_recorded.v1",
            source="semantic-review.pipeline:test.reviewer",
            payload={
                "review_id": review_id,
                "proposal_id": proposal_id,
                "proposal_event_id": stored["proposal_event_id"],
                "proposal_digest": stored["proposal_digest"],
                "claim_id": claim_id,
                "claim_digest": digest(claim),
                "reviewer": {"component": "test.reviewer", "version": "0.1"},
                "contract_version": "semantic-review.v1",
                "outcome": outcome,
                "reasoning_summary": "Synthetic test review; not a truth oracle.",
                "supporting_claim_ids": supporting_claim_ids or ["claim-source-1"],
                "alternative_explanations": [],
                "limitations": ["Synthetic test fixture."],
            },
        )
        return self.store.submit_event(event)


    def test_grounded_memory_proposal_cannot_claim_a_future_snapshot_version(self):
        with self.assertRaisesRegex(ValueError, "future state_version"):
            self.store.submit_event(self.proposal(state_version=1))
        self.assertEqual(
            self.store._db.execute("SELECT COUNT(*) FROM proposals").fetchone()[0],
            0,
        )

    def test_grounded_proposal_is_pending_and_not_yet_memory(self):
        self.submit_pending()
        proposal = self.store.get_proposal("grounded-proposal-1")
        self.assertEqual(proposal["status"], "pending")
        self.assertEqual(proposal["proposal"]["claims"][0]["epistemic_type"], "source_assertion")
        self.assertEqual(self.store.get_memories(), [])

    def test_get_event_rejects_grounded_proposal_referencing_later_observation(self):
        proposal = self.submit_pending()
        later = CognitiveEvent(
            event_id="evt-grounded-later-observation",
            occurred_at="2026-11-14T10:02:00+00:00",
            correlation_id="corr-grounded",
            event_type=OBSERVATION_EVENT,
            source="test.observation_fixture",
            payload={
                "observation_id": "obs-grounded-later",
                "observation_kind": "text_fixture",
                "content": self.source_text,
                "source_ref": "fixture://grounded/later-observation",
                "observed_at": "2026-11-14T10:01:30+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        )
        self.store.submit_event(later)
        self.rewrite_event_payload_with_valid_digests(
            proposal.event_id,
            lambda payload: payload["claims"][0]["evidence"][0].__setitem__(
                "event_id", later.event_id
            ),
        )

        with self.assertRaisesRegex(
            CognitiveIntegrityError, "grounded proposal evidence must reference an earlier event"
        ):
            self.store.get_event(proposal.event_id)

    def test_get_event_validates_existing_grounded_source_observation(self):
        proposal = self.submit_pending()
        self.rewrite_event_payload_with_valid_digests(
            self.observation.event_id,
            lambda payload: payload.__setitem__("content", ""),
        )

        with self.assertRaisesRegex(
            CognitiveIntegrityError, "invalid durable event schema"
        ):
            self.store.get_event(proposal.event_id)

    def test_exact_text_span_is_accepted_and_preserved(self):
        self.submit_pending()
        decision = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(decision["status"], "accepted")
        memory = self.store.get_memories()[0]
        claim = memory["claims"][0]
        evidence = claim["evidence"][0]
        self.assertEqual(claim["epistemic_type"], "source_assertion")
        self.assertEqual(
            self.source_text[evidence["locator"]["start"]:evidence["locator"]["end"]],
            evidence["quoted_text"],
        )
        self.assertEqual(memory["claim_schema"], "grounded-memory-claims.v2")
        self.assertEqual(memory["evidence_event_ids"], ["evt-grounded-observation"])

    def test_unicode_codepoint_offsets_handle_astral_character(self):
        quote = "The scene was quiet."
        self.assertIn("🌉", self.source_text)
        self.submit_pending(claims=[self.source_claim(
            quote=quote,
            start=self.source_text.index(quote),
            end=self.source_text.index(quote) + len(quote),
        )])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "accepted")
        memory = self.store.get_memories()[0]
        locator = memory["claims"][0]["evidence"][0]["locator"]
        self.assertEqual(
            self.source_text[locator["start"]:locator["end"]],
            quote,
        )

    def test_inference_is_retained_as_inference_not_observation(self):
        self.submit_pending(claims=[
            self.source_claim(),
            self.inference_claim(),
        ])
        self.assertEqual(
            self.store.evaluate_proposal("grounded-proposal-1")["status"],
            "awaiting_review",
        )
        self.submit_supported_review()
        self.assertEqual(
            self.store.evaluate_proposal("grounded-proposal-1")["status"],
            "accepted",
        )
        claims = self.store.get_memories()[0]["claims"]
        self.assertEqual([c["epistemic_type"] for c in claims],
                         ["source_assertion", "inference"])
        self.assertEqual(claims[1]["derived_from_claim_ids"], ["claim-source-1"])
        self.assertNotIn("evidence", claims[1])

    def test_mismatched_quote_is_durably_rejected(self):
        claim = self.source_claim(
            quote="A blue paper boat was a submarine.",
            start=self.source_text.index("A blue paper boat passed the bridge."),
        )
        self.submit_pending(claims=[claim])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("does not match", result["reason"])
        self.assertEqual(self.store.get_memories(), [])
        self.assertEqual(self.store.get_proposal("grounded-proposal-1")["status"], "rejected")

    def test_source_assertion_text_must_equal_exact_quote(self):
        claim = self.source_claim()
        claim["text"] = "A paraphrase that has not been verified."
        self.submit_pending(claims=[claim])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("must equal", result["reason"])
        self.assertEqual(self.store.get_memories(), [])

    def test_out_of_bounds_end_offset_is_rejected(self):
        quote = "A blue paper boat passed the bridge."
        claim = self.source_claim(
            quote=quote,
            start=self.source_text.index(quote),
            end=len(self.source_text) + 10,
        )
        self.submit_pending(claims=[claim])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("out of bounds", result["reason"])
        self.assertEqual(self.store.get_memories(), [])

    def test_missing_observation_is_needs_more_evidence(self):
        self.submit_pending(claims=[self.source_claim(event_id="evt-not-yet-arrived")])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "needs_more_evidence")
        self.assertEqual(self.store.get_memories(), [])

    def test_non_text_observation_cannot_ground_v2_memory(self):
        image_observation = CognitiveEvent(
            event_id="evt-grounded-image-observation",
            occurred_at="2026-11-14T10:00:05+00:00",
            correlation_id="corr-grounded",
            event_type=OBSERVATION_EVENT,
            source="test.observation_fixture",
            payload={
                "observation_id": "obs-grounded-image",
                "observation_kind": "image_fixture",
                "content": "A caption extracted from an image.",
                "source_ref": "fixture://grounded/image",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "image", "complete_for_fixture": True},
            },
        )
        self.store.submit_event(image_observation)
        self.submit_pending(claims=[self.source_claim(
            quote="A blue paper boat passed the bridge.",
            event_id="evt-grounded-image-observation",
            start=0,
            end=len("A blue paper boat passed the bridge."),
        )])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("requires text evidence", result["reason"])
        self.assertEqual(self.store.get_memories(), [])

    def test_existing_non_observation_evidence_is_rejected(self):
        other = CognitiveEvent(
            event_id="evt-other-proposal",
            occurred_at="2026-11-14T10:00:30+00:00",
            correlation_id="corr-grounded",
            event_type=PROPOSAL_EVENT,
            source="test.fixture",
            payload={
                "proposal_id": "legacy-proposal",
                "memory_kind": "episodic_candidate",
                "candidate_content": "legacy candidate",
                "evidence_event_ids": ["evt-grounded-observation"],
                "origin": {"component": "test.fixture", "version": "0.1"},
                "uncertainty": {"label": "test", "confidence": None},
                "based_on": {"state_version": 0},
                "operation": "create",
            },
        )
        self.store.submit_event(other)
        self.submit_pending(claims=[self.source_claim(event_id="evt-other-proposal")])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("not an observation", result["reason"])

    def test_inference_with_missing_claim_reference_is_rejected(self):
        self.submit_pending(claims=[
            self.source_claim(),
            self.inference_claim(refs=["claim-does-not-exist"]),
        ])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("missing claim", result["reason"])

    def test_inference_cannot_derive_from_another_inference(self):
        self.submit_pending(claims=[
            self.source_claim(),
            self.inference_claim(claim_id="claim-inference-1"),
            self.inference_claim(
                claim_id="claim-inference-2",
                refs=["claim-inference-1"],
                text="A second-level inference.",
            ),
        ])
        result = self.store.evaluate_proposal("grounded-proposal-1")
        self.assertEqual(result["status"], "rejected")
        self.assertIn("only from source_assertion", result["reason"])

    def test_duplicate_claim_ids_are_rejected_at_submission(self):
        claim = self.source_claim()
        duplicate = dict(claim)
        before = self.store.get_state_snapshot()["event_count"]
        with self.assertRaises(ValueError):
            self.store.submit_event(self.proposal(claims=[claim, duplicate]))
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)
        with self.assertRaises(KeyError):
            self.store.get_proposal("grounded-proposal-1")

    def test_invalid_offset_types_are_rejected_at_submission(self):
        claim = self.source_claim()
        claim["evidence"][0]["locator"]["start"] = True
        event = self.proposal(claims=[claim])
        before = self.store.get_state_snapshot()["event_count"]
        with self.assertRaises(ValueError):
            self.store.submit_event(event)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)
        with self.assertRaises(KeyError):
            self.store.get_proposal("grounded-proposal-1")

    def test_multiple_observation_sources_are_out_of_scope_for_v2(self):
        second = CognitiveEvent(
            event_id="evt-grounded-observation-2",
            occurred_at="2026-11-14T10:00:10+00:00",
            correlation_id="corr-grounded",
            event_type=OBSERVATION_EVENT,
            source="test.observation_fixture",
            payload={
                "observation_id": "obs-grounded-2",
                "observation_kind": "text_fixture",
                "content": "A second synthetic source.",
                "source_ref": "fixture://grounded/observation-2",
                "observed_at": "2026-11-14T10:00:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        )
        self.store.submit_event(second)
        claims = [
            self.source_claim(),
            self.source_claim(
                claim_id="claim-source-2",
                quote="A second synthetic source.",
                start=0,
                end=len("A second synthetic source."),
                event_id="evt-grounded-observation-2",
            ),
        ]
        before = self.store.get_state_snapshot()["event_count"]
        with self.assertRaises(ValueError):
            self.store.submit_event(self.proposal(claims=claims))
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)

    def test_stale_grounded_proposal_is_deferred(self):
        self.submit_pending(proposal_id="grounded-first")
        self.assertEqual(self.store.evaluate_proposal("grounded-first")["status"], "accepted")
        self.submit_pending(
            event_id="evt-grounded-proposal-2",
            proposal_id="grounded-stale",
            state_version=0,
        )
        result = self.store.evaluate_proposal("grounded-stale")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(len(self.store.get_memories()), 1)

    def test_recovery_preserves_accepted_claims_and_locators(self):
        self.submit_pending(claims=[
            self.source_claim(),
            self.inference_claim(),
        ])
        self.submit_supported_review()
        self.store.evaluate_proposal("grounded-proposal-1")
        before = self.store.get_memories()
        self.store.close()
        self.store = CognitiveMemoryStore(self.db_path)
        result = self.store.recover()
        self.assertEqual(result["accepted_memories"], 1)
        self.assertEqual(self.store.get_memories(), before)

    def test_recovery_keeps_rejected_proposal_without_memory(self):
        self.submit_pending(claims=[
            self.source_claim(
                quote="text that does not exist in the source",
                start=0,
                end=5,
            )
        ])
        self.store.evaluate_proposal("grounded-proposal-1")
        self.store.close()
        self.store = CognitiveMemoryStore(self.db_path)
        result = self.store.recover()
        self.assertEqual(result["proposals"], 1)
        self.assertEqual(result["accepted_memories"], 0)
        self.assertEqual(self.store.get_proposal("grounded-proposal-1")["status"], "rejected")

    def test_recovery_does_not_call_proposal_evaluator(self):
        self.submit_pending()
        self.store.evaluate_proposal("grounded-proposal-1")

        def forbidden(*args, **kwargs):
            raise AssertionError("Recovery must not call the proposal evaluator")

        self.store.evaluate_proposal = forbidden
        result = self.store.recover()
        self.assertEqual(result["accepted_memories"], 1)

    def test_grounded_decision_and_memory_projection_roll_back_together(self):
        self.submit_pending()
        original = self.store._apply_projection_event

        def fail_on_decision(db, event, sequence, *, internal):
            if event.event_type == DECISION_EVENT:
                raise RuntimeError("synthetic failure before commit")
            return original(db, event, sequence, internal=internal)

        self.store._apply_projection_event = fail_on_decision
        with self.assertRaises(RuntimeError):
            self.store.evaluate_proposal("grounded-proposal-1")
        self.store._apply_projection_event = original
        self.assertEqual(self.store.get_memories(), [])
        self.assertEqual(self.store.get_proposal("grounded-proposal-1")["status"], "pending")
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 2)

    def test_same_proposal_id_with_changed_claims_conflicts(self):
        self.submit_pending()
        altered = self.proposal(
            event_id="evt-grounded-proposal-duplicate",
            claims=[self.source_claim(
                quote="The scene was quiet.",
                start=self.source_text.index("The scene was quiet."),
                end=len(self.source_text),
            )],
        )
        with self.assertRaises(ProposalIdentityConflict):
            self.store.submit_event(altered)

    def test_same_proposal_id_and_same_claims_maps_to_one_proposal(self):
        event = self.proposal()
        self.store.submit_event(event)
        duplicate = self.proposal(event_id="evt-grounded-proposal-duplicate")
        self.store.submit_event(duplicate)
        self.assertEqual(self.store.get_state_snapshot()["proposal_count"], 1)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 3)

    def test_proposal_with_unsupported_claim_type_is_rejected_at_submission(self):
        claim = self.source_claim()
        claim["epistemic_type"] = "system_experience"
        before = self.store.get_state_snapshot()["event_count"]
        with self.assertRaises(ValueError):
            self.store.submit_event(self.proposal(claims=[claim]))
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)

    def test_event_read_preserves_grounded_proposal_payload(self):
        event = self.proposal(claims=[self.source_claim(), self.inference_claim()])
        self.store.submit_event(event)
        read = self.store.get_event(event.event_id)
        self.assertEqual(read["event_type"], GROUNDED_PROPOSAL_EVENT)
        self.assertEqual(read["payload"]["claims"], event.payload["claims"])


if __name__ == "__main__":
    unittest.main()
