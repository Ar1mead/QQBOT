from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveMemoryStore,
    GroundedInference,
    GroundedMemoryCandidate,
    GroundedMemoryProposalPipeline,
    GroundedSourceAssertion,
    SemanticReviewCandidate,
    SemanticReviewPipeline,
)
from core.csd.cognitive import OBSERVATION_EVENT


class FakeGroundedProvider:
    provider_id = "test.grounded_provider"
    provider_version = "0.2"

    def __init__(self, candidate):
        self.candidate = candidate

    def propose_grounded(self, observation, *, state_version):
        return [self.candidate]


class FakeSemanticReviewProvider:
    reviewer_id = "test.semantic_reviewer"
    reviewer_version = "0.1"

    def __init__(self, *, outcome="supported", fail_on_claim=None,
                 supporting_override=None):
        self.outcome = outcome
        self.fail_on_claim = fail_on_claim
        self.supporting_override = supporting_override
        self.called_in_transaction = []
        self.calls = []

    def review_inference(self, proposal, inference_claim, supporting_claims):
        self.called_in_transaction.append(self.store._db.in_transaction)
        self.calls.append(inference_claim["claim_id"])
        if inference_claim["claim_id"] == self.fail_on_claim:
            raise TimeoutError("synthetic semantic reviewer failure")
        support_ids = (
            self.supporting_override
            if self.supporting_override is not None
            else [claim["claim_id"] for claim in supporting_claims]
        )
        return SemanticReviewCandidate(
            outcome=self.outcome,
            reasoning_summary="Synthetic reviewer opinion; not a truth oracle.",
            supporting_claim_ids=support_ids,
            alternative_explanations=["Another interpretation may fit."],
            limitations=["Only one text observation was supplied."],
        )


class SemanticReviewPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "semantic-pipeline.sqlite3"
        self.store = CognitiveMemoryStore(self.db_path)
        self.source_text = "A silver leaf rested on the windowsill. A blue cup sat nearby."
        self.store.submit_event(CognitiveEvent(
            event_id="evt-semantic-pipeline-source",
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-semantic-pipeline",
            event_type=OBSERVATION_EVENT,
            source="test.observation",
            payload={
                "observation_id": "obs-semantic-pipeline",
                "observation_kind": "text_fixture",
                "content": self.source_text,
                "source_ref": "fixture://semantic-pipeline/source",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def grounded_candidate(self, proposal_id="semantic-pipeline-proposal",
                           inference_ids=("claim-inference-1",)):
        quote = "A silver leaf rested on the windowsill."
        start = self.source_text.index(quote)
        source = GroundedSourceAssertion(
            claim_id="claim-source-1",
            text=quote,
            quoted_text=quote,
            start=start,
            end=start + len(quote),
        )
        inferences = [
            GroundedInference(
                claim_id=claim_id,
                text=f"Interpretation {claim_id} is tentative.",
                derived_from_claim_ids=["claim-source-1"],
                reasoning_summary="A tentative inference based on the source sentence.",
                confidence=0.4,
            )
            for claim_id in inference_ids
        ]
        return GroundedMemoryCandidate(
            proposal_id=proposal_id,
            memory_kind="episodic_candidate",
            source_assertions=[source],
            inferences=inferences,
        )

    def create_pending(self, candidate=None, proposal_id="semantic-pipeline-proposal"):
        candidate = candidate or self.grounded_candidate(proposal_id)
        proposer = FakeGroundedProvider(candidate)
        result = GroundedMemoryProposalPipeline(self.store, proposer).propose_from_observation(
            "evt-semantic-pipeline-source"
        )
        self.assertEqual(result[0]["status"], "accepted")
        self.assertEqual(self.store.get_proposal(proposal_id)["status"], "pending")
        return self.store.get_proposal(proposal_id)

    def pipeline(self, provider):
        provider.store = self.store
        return SemanticReviewPipeline(self.store, provider)

    def test_provider_reviews_inference_but_does_not_accept_proposal(self):
        self.create_pending()
        provider = FakeSemanticReviewProvider()
        results = self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "accepted")
        self.assertEqual(self.store.get_proposal("semantic-pipeline-proposal")["status"], "pending")
        self.assertEqual(self.store.get_memories(), [])
        self.assertFalse(any(provider.called_in_transaction))

    def test_pipeline_binds_proposal_and_claim_digests(self):
        stored = self.create_pending()
        provider = FakeSemanticReviewProvider()
        self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        review = self.store.get_semantic_reviews("semantic-pipeline-proposal")[0]["payload"]
        self.assertEqual(review["proposal_digest"], stored["proposal_digest"])
        self.assertEqual(review["proposal_event_id"], stored["proposal_event_id"])
        claim = next(
            c for c in stored["proposal"]["claims"]
            if c["claim_id"] == "claim-inference-1"
        )
        self.assertTrue(review["claim_digest"].startswith("sha256:"))
        self.assertEqual(review["reviewer"]["component"], provider.reviewer_id)
        self.assertEqual(review["reviewer"]["version"], provider.reviewer_version)

    def test_pipeline_reviews_each_inference_claim(self):
        self.create_pending(self.grounded_candidate(inference_ids=(
            "claim-inference-1", "claim-inference-2"
        )))
        provider = FakeSemanticReviewProvider()
        results = self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(len(results), 2)
        self.assertEqual(set(provider.calls), {"claim-inference-1", "claim-inference-2"})
        reviews = self.store.get_semantic_reviews("semantic-pipeline-proposal")
        self.assertEqual({item["payload"]["claim_id"] for item in reviews},
                         {"claim-inference-1", "claim-inference-2"})

    def test_pipeline_does_not_call_provider_for_proposal_without_inferences(self):
        self.create_pending(self.grounded_candidate(inference_ids=()))
        provider = FakeSemanticReviewProvider()
        results = self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(results, [])
        self.assertEqual(provider.calls, [])
        self.assertEqual(self.store.get_semantic_reviews("semantic-pipeline-proposal"), [])

    def test_provider_failure_before_submission_leaves_no_partial_review_batch(self):
        self.create_pending(self.grounded_candidate(inference_ids=(
            "claim-inference-1", "claim-inference-2"
        )))
        provider = FakeSemanticReviewProvider(fail_on_claim="claim-inference-2")
        with self.assertRaises(TimeoutError):
            self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(self.store.get_semantic_reviews("semantic-pipeline-proposal"), [])
        self.assertEqual(self.store.get_proposal("semantic-pipeline-proposal")["status"], "pending")

    def test_invalid_provider_support_reference_creates_no_review_event(self):
        self.create_pending()
        provider = FakeSemanticReviewProvider(supporting_override=["not-a-source-claim"])
        with self.assertRaises(ValueError):
            self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(self.store.get_semantic_reviews("semantic-pipeline-proposal"), [])

    def test_provider_calls_run_outside_csd_write_transaction(self):
        self.create_pending()
        provider = FakeSemanticReviewProvider()
        self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(len(provider.called_in_transaction), 1)
        self.assertFalse(any(provider.called_in_transaction))

    def test_review_pipeline_never_evaluates_proposal(self):
        self.create_pending()
        provider = FakeSemanticReviewProvider()
        pipeline = self.pipeline(provider)

        def forbidden(*args, **kwargs):
            raise AssertionError("review pipeline must not call CSD proposal evaluation")

        self.store.evaluate_proposal = forbidden
        result = pipeline.review_proposal("semantic-pipeline-proposal")
        self.assertEqual(len(result), 1)
        self.assertEqual(self.store.get_proposal("semantic-pipeline-proposal")["status"], "pending")

    def test_review_pipeline_rejects_non_pending_proposal(self):
        self.create_pending()
        provider = FakeSemanticReviewProvider()
        self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(
            self.store.evaluate_proposal("semantic-pipeline-proposal")["status"],
            "accepted",
        )
        late_provider = FakeSemanticReviewProvider()
        with self.assertRaises(ValueError):
            self.pipeline(late_provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(late_provider.calls, [])

    def test_invalid_provider_candidate_type_is_rejected_without_event(self):
        self.create_pending()
        provider = FakeSemanticReviewProvider()
        provider.review_inference = lambda *args, **kwargs: {"outcome": "supported"}
        with self.assertRaises(TypeError):
            self.pipeline(provider).review_proposal("semantic-pipeline-proposal")
        self.assertEqual(self.store.get_semantic_reviews("semantic-pipeline-proposal"), [])


if __name__ == "__main__":
    unittest.main()
