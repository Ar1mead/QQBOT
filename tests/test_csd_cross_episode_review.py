from __future__ import annotations

from pathlib import Path
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

    def test_provider_failure_does_not_change_csd(self):
        reviewer = FakeCrossEpisodeReviewer(failure=TimeoutError("offline"))
        before = self.store.get_state_snapshot()["state_version"]
        with self.assertRaises(TimeoutError):
            self.pipeline(reviewer).review_proposal("review-cross-episode-proposal")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before)

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
