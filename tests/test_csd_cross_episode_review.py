from __future__ import annotations

from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveMemoryStore,
    GroundedMemoryCandidate,
    GroundedMemoryProposalPipeline,
    GroundedSourceAssertion,
    append_cross_episode_proposal,
    build_accepted_claim_reference_context,
)
from core.csd.cross_episode_proposals import build_cross_episode_proposal
from core.csd.cognitive import (
    CognitiveIntegrityError,
    CROSS_EPISODE_REVIEW_EVENT,
    CROSS_EPISODE_REVIEW_SOURCE,
)
from core.csd.cross_episode_review import (
    CrossEpisodeReviewCandidate,
    CrossEpisodeReviewError,
    CrossEpisodeReviewPipeline,
)
from core.csd.cognitive import OBSERVATION_EVENT


class FakeCrossEpisodeReviewer:
    reviewer_id = "test.cross_episode_reviewer"
    reviewer_version = "0.1"

    def __init__(self, *, result=None, failure=None):
        self.result = result or CrossEpisodeReviewCandidate(
            outcome="supported",
            confidence=0.62,
            reasoning_summary="The source supports a limited, context-specific interpretation.",
            supporting_reference_keys=["support-01"],
            counter_evidence_reference_keys=[],
            scope_assessment="fits",
            alternative_explanations=["The choice may have been situational."],
            limitations=["Only one independent source event is available."],
        )
        self.failure = failure
        self.calls = []
        self.transaction_states = []

    def review_cross_episode(self, review_input):
        self.calls.append(review_input)
        self.transaction_states.append(self.store._db.in_transaction)
        if self.failure:
            raise self.failure
        return self.result


class CrossEpisodeReviewPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CognitiveMemoryStore(Path(self.temp.name) / "review.sqlite3")
        self.source_text = "The user chose a quiet corner table."
        self.store.submit_event(CognitiveEvent(
            event_id="evt-review-source",
            occurred_at="2026-11-20T08:00:00+00:00",
            correlation_id="corr-review-source",
            event_type=OBSERVATION_EVENT,
            source="test.cross_episode_review",
            payload={
                "observation_id": "obs-review-source",
                "observation_kind": "text_fixture",
                "content": self.source_text,
                "source_ref": "fixture://review-source",
                "observed_at": "2026-11-20T07:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

        class GroundedProvider:
            provider_id = "test.review_grounded_provider"
            provider_version = "1"

            def propose_grounded(inner_self, observation, *, state_version):
                return [GroundedMemoryCandidate(
                    proposal_id="review-memory-proposal",
                    memory_kind="episodic_candidate",
                    source_assertions=[GroundedSourceAssertion(
                        claim_id="claim-quiet-table",
                        text=self.source_text,
                        quoted_text=self.source_text,
                        start=0,
                        end=len(self.source_text),
                    )],
                )]

        GroundedMemoryProposalPipeline(self.store, GroundedProvider()).propose_from_observation(
            "evt-review-source"
        )
        self.store.evaluate_proposal("review-memory-proposal")
        memory = self.store.get_memories()[0]
        self.version = self.store.get_state_snapshot()["state_version"]
        context = build_accepted_claim_reference_context(
            self.store,
            [{"memory_id": memory["memory_id"], "claim_id": "claim-quiet-table"}],
            expected_state_version=self.version,
        )
        payload = {
            "schema_version": 1,
            "based_on_state_version": self.version,
            "candidate_kind": "preference_candidate",
            "owner": "user",
            "domain": "dining_environment",
            "statement": "The user may prefer quieter dining environments.",
            "scope": "Restaurant choices when atmosphere is relevant.",
            "exclusions": ["This does not imply a preference for isolation."],
            "confidence": 0.55,
            "uncertainty": "moderate",
            "reasoning_summary": "One accepted episode provides limited evidence.",
            "alternatives": ["The choice may have been situational."],
            "limitations": ["Only one independent source event is available."],
            "support_reference_keys": ["historical-claim-0001"],
            "counter_evidence_reference_keys": [],
        }
        proposal = build_cross_episode_proposal(
            self.store, payload, context,
            proposal_id="review-cross-episode-proposal",
            provider_id="test.cross_episode_model",
            provider_version="1",
            expected_state_version=self.version,
        )
        append_cross_episode_proposal(
            self.store, proposal, occurred_at="2026-11-20T08:10:00+00:00"
        )

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def pipeline(self, reviewer):
        reviewer.store = self.store
        return CrossEpisodeReviewPipeline(self.store, reviewer)

    def test_review_returns_ephemeral_artifact_and_does_not_write_csd(self):
        reviewer = FakeCrossEpisodeReviewer()
        before = self.store.get_state_snapshot()["state_version"]
        artifact = self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")
        self.assertEqual(artifact.candidate.outcome, "supported")
        self.assertTrue(artifact.proposal_digest.startswith("sha256:"))
        self.assertTrue(artifact.review_input_digest.startswith("sha256:"))
        self.assertEqual(reviewer.transaction_states, [False])
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before)
        self.assertEqual(len(reviewer.calls), 1)
        self.assertEqual(
            reviewer.calls[0]["source_evidence"][0]["content"], self.source_text
        )
        self.assertEqual(
            reviewer.calls[0]["evidence_spans"][0]["quoted_text"], self.source_text
        )

    def test_provider_cannot_select_invented_reference_keys(self):
        reviewer = FakeCrossEpisodeReviewer(result=CrossEpisodeReviewCandidate(
            outcome="supported", confidence=0.8, reasoning_summary="Unsupported key.",
            supporting_reference_keys=["model-invented"], counter_evidence_reference_keys=[],
            scope_assessment="fits",
        ))
        with self.assertRaisesRegex(CrossEpisodeReviewError, "unknown supporting"):
            self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], self.version)

    def test_conflicting_outcome_requires_both_support_and_counter_evidence(self):
        reviewer = FakeCrossEpisodeReviewer(result=CrossEpisodeReviewCandidate(
            outcome="conflicting", confidence=0.5, reasoning_summary="Conflict.",
            supporting_reference_keys=["support-01"], counter_evidence_reference_keys=[],
            scope_assessment="unclear",
        ))
        with self.assertRaisesRegex(CrossEpisodeReviewError, "requires support"):
            self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")

    def test_unsupported_risk_flags_and_non_boolean_human_review_fail_closed(self):
        reviewer = FakeCrossEpisodeReviewer(result=CrossEpisodeReviewCandidate(
            outcome="uncertain", confidence=0.5, reasoning_summary="Unclear.",
            supporting_reference_keys=[], counter_evidence_reference_keys=[],
            scope_assessment="unclear", risk_flags=["grant_tools"],
        ))
        with self.assertRaisesRegex(CrossEpisodeReviewError, "risk flag"):
            self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")

        reviewer = FakeCrossEpisodeReviewer(result=CrossEpisodeReviewCandidate(
            outcome="uncertain", confidence=0.5, reasoning_summary="Unclear.",
            supporting_reference_keys=[], counter_evidence_reference_keys=[],
            scope_assessment="unclear", requires_human_review=1,
        ))
        with self.assertRaisesRegex(CrossEpisodeReviewError, "must be boolean"):
            self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")

    def test_sensitive_inference_flag_requires_human_review(self):
        reviewer = FakeCrossEpisodeReviewer(result=CrossEpisodeReviewCandidate(
            outcome="uncertain", confidence=0.4, reasoning_summary="Potentially sensitive.",
            supporting_reference_keys=[], counter_evidence_reference_keys=[],
            scope_assessment="unclear", risk_flags=["sensitive_inference"],
            requires_human_review=False,
        ))
        with self.assertRaisesRegex(CrossEpisodeReviewError, "requires independent human review"):
            self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")

    def test_provider_subclass_with_extra_fields_is_rejected(self):
        class ExtendedCandidate(CrossEpisodeReviewCandidate):
            pass
        reviewer = FakeCrossEpisodeReviewer(result=ExtendedCandidate(
            outcome="uncertain", confidence=0.4, reasoning_summary="Extended.",
            supporting_reference_keys=[], counter_evidence_reference_keys=[],
            scope_assessment="unclear",
        ))
        with self.assertRaises(TypeError):
            self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")

    def test_provider_failure_does_not_change_csd(self):
        reviewer = FakeCrossEpisodeReviewer(failure=TimeoutError("offline"))
        before = self.store.get_state_snapshot()["state_version"]
        with self.assertRaises(TimeoutError):
            self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before)

    def test_returned_artifact_freezes_provider_sequences(self):
        alternatives = ["The choice may have been situational."]
        reviewer = FakeCrossEpisodeReviewer(result=CrossEpisodeReviewCandidate(
            outcome="supported", confidence=0.7, reasoning_summary="Bounded.",
            supporting_reference_keys=["support-01"], counter_evidence_reference_keys=[],
            scope_assessment="fits", alternative_explanations=alternatives,
        ))
        artifact = self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")
        alternatives.append("Mutated after review.")
        self.assertIsInstance(artifact.candidate.alternative_explanations, tuple)
        self.assertEqual(
            artifact.candidate.alternative_explanations,
            ("The choice may have been situational.",),
        )

    def test_record_review_appends_immutable_audit_event_without_state_transition(self):
        reviewer = FakeCrossEpisodeReviewer()
        pipeline = self.pipeline(reviewer)
        artifact = pipeline.review_proposal("review-cross-episode-proposal")
        before = self.store.get_state_snapshot()["state_version"]

        recorded = pipeline.record_review(artifact)
        event = self.store.get_event(recorded["event_id"])

        self.assertEqual(recorded["status"], "accepted")
        self.assertEqual(event["event_type"], CROSS_EPISODE_REVIEW_EVENT)
        self.assertEqual(event["source"], CROSS_EPISODE_REVIEW_SOURCE)
        self.assertEqual(
            event["correlation_id"],
            "cross-episode-proposal:review-cross-episode-proposal",
        )
        self.assertEqual(event["payload"]["proposal_event_id"], artifact.proposal_event_id)
        self.assertEqual(event["payload"]["proposal_digest"], artifact.proposal_digest)
        self.assertEqual(event["payload"]["review_input_digest"], artifact.review_input_digest)
        self.assertEqual(event["payload"]["based_on_state_version"], artifact.based_on_state_version)
        self.assertEqual(event["payload"]["reviewer"], {
            "id": "test.cross_episode_reviewer",
            "version": "0.1",
        })
        self.assertEqual(event["payload"]["candidate"]["outcome"], "supported")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before)
        self.assertEqual(
            self.store.list_cross_episode_proposals()[0]["status"],
            "pending_shadow",
        )

    def test_public_submit_cannot_forge_reserved_review_event(self):
        event = CognitiveEvent(
            event_id="csd-cross-episode-review:forged",
            occurred_at="2026-11-20T08:20:00+00:00",
            correlation_id="cross-episode-proposal:review-cross-episode-proposal",
            event_type=CROSS_EPISODE_REVIEW_EVENT,
            source=CROSS_EPISODE_REVIEW_SOURCE,
            payload={},
        )
        with self.assertRaisesRegex(ValueError, "reserved for the internal authority path"):
            self.store.submit_event(event)
        self.assertEqual(
            self.store._db.execute(
                "SELECT COUNT(*) FROM events WHERE event_type=?",
                (CROSS_EPISODE_REVIEW_EVENT,),
            ).fetchone()[0],
            0,
        )

    def test_record_review_duplicate_delivery_is_idempotent(self):
        pipeline = self.pipeline(FakeCrossEpisodeReviewer())
        artifact = pipeline.review_proposal("review-cross-episode-proposal")

        first = pipeline.record_review(artifact)
        second = pipeline.record_review(artifact)

        self.assertEqual(first["status"], "accepted")
        self.assertEqual(second["status"], "duplicate")
        self.assertEqual(first["event_id"], second["event_id"])
        self.assertEqual(first["sequence"], second["sequence"])
        self.assertEqual(
            self.store._db.execute(
                "SELECT COUNT(*) FROM events WHERE event_type=?",
                (CROSS_EPISODE_REVIEW_EVENT,),
            ).fetchone()[0],
            1,
        )

    def test_direct_review_event_read_rejects_rehashed_payload_tampering(self):
        pipeline = self.pipeline(FakeCrossEpisodeReviewer())
        artifact = pipeline.review_proposal("review-cross-episode-proposal")
        recorded = pipeline.record_review(artifact)
        row = self.store._db.execute(
            "SELECT occurred_at,received_at,correlation_id,event_type,source,"
            "payload_ref,payload_json FROM events e "
            "JOIN payloads p ON p.payload_ref=e.payload_ref WHERE event_id=?",
            (recorded["event_id"],),
        ).fetchone()
        payload = json.loads(row["payload_json"])
        payload["reviewed_at"] = "not-the-event-occurrence-time"
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        payload_ref = "sha256:" + hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        tampered_event = CognitiveEvent(
            event_id=recorded["event_id"],
            occurred_at=row["occurred_at"],
            correlation_id=row["correlation_id"],
            event_type=row["event_type"],
            source=row["source"],
            payload=payload,
        )
        event_digest = self.store._event_digest(
            tampered_event, payload_ref, row["received_at"]
        )

        # Simulate offline storage corruption while keeping both hashes valid.
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (payload_ref, payload_json),
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (payload_ref, event_digest, recorded["event_id"]),
        )

        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_event(recorded["event_id"])

    def test_recovery_replays_review_record_without_accepting_candidate(self):
        pipeline = self.pipeline(FakeCrossEpisodeReviewer())
        artifact = pipeline.review_proposal("review-cross-episode-proposal")
        recorded = pipeline.record_review(artifact)
        before = self.store.get_state_snapshot()["state_version"]

        recovered = self.store.recover()

        self.assertGreaterEqual(recovered["events"], 4)
        event = self.store.get_event(recorded["event_id"])
        self.assertEqual(event["event_type"], CROSS_EPISODE_REVIEW_EVENT)
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before)
        self.assertEqual(
            self.store.list_cross_episode_proposals()[0]["status"],
            "pending_shadow",
        )

    def test_review_rejects_unknown_proposal(self):
        reviewer = FakeCrossEpisodeReviewer()
        with self.assertRaises(CrossEpisodeReviewError):
            self.pipeline(reviewer).review_proposal("missing-proposal")
        self.assertEqual(reviewer.calls, [])

    def test_review_input_excludes_opaque_account_identity(self):
        reviewer = FakeCrossEpisodeReviewer()
        self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")
        serialized = repr(reviewer.calls[0])
        self.assertNotIn("account_ref", serialized)


if __name__ == "__main__":
    unittest.main()
