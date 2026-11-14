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
)
from core.csd.cognitive import OBSERVATION_EVENT


class FakeGroundedProvider:
    provider_id = "test.fake_grounded_provider"
    provider_version = "0.2"

    def __init__(self, candidates=()):
        self.candidates = candidates
        self.called_in_transaction = None
        self.received_state_version = None

    def propose_grounded(self, observation, *, state_version):
        self.called_in_transaction = self.store._db.in_transaction
        self.received_state_version = state_version
        return self.candidates


class GroundedMemoryProposalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "grounded-pipeline.sqlite3"
        self.store = CognitiveMemoryStore(self.db_path)
        self.source_text = "A silver leaf rested on the windowsill. 🍃"
        self.store.submit_event(CognitiveEvent(
            event_id="evt-pipeline-grounded-observation",
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-grounded-pipeline",
            event_type=OBSERVATION_EVENT,
            source="test.observation_fixture",
            payload={
                "observation_id": "obs-grounded-pipeline",
                "observation_kind": "text_fixture",
                "content": self.source_text,
                "source_ref": "fixture://grounded-pipeline/observation",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def candidate(self, proposal_id="grounded-pipeline-proposal", *, quote=None,
                  text=None, start=None, end=None, inferences=()):
        quote = quote or "A silver leaf rested on the windowsill."
        if start is None:
            start = self.source_text.index(quote)
        if end is None:
            end = start + len(quote)
        assertion = GroundedSourceAssertion(
            claim_id="claim-source-1",
            text=text if text is not None else quote,
            quoted_text=quote,
            start=start,
            end=end,
        )
        return GroundedMemoryCandidate(
            proposal_id=proposal_id,
            memory_kind="episodic_candidate",
            source_assertions=[assertion],
            inferences=inferences,
        )

    def pipeline(self, provider):
        provider.store = self.store
        return GroundedMemoryProposalPipeline(self.store, provider)

    def test_pipeline_creates_pending_v2_event_not_accepted_memory(self):
        provider = FakeGroundedProvider([self.candidate()])
        result = self.pipeline(provider).propose_from_observation(
            "evt-pipeline-grounded-observation"
        )
        self.assertEqual(result[0]["status"], "accepted")
        proposal = self.store.get_proposal("grounded-pipeline-proposal")
        self.assertEqual(proposal["status"], "pending")
        self.assertEqual(self.store.get_memories(), [])
        self.assertEqual(
            proposal["proposal"]["claims"][0]["evidence"][0]["event_id"],
            "evt-pipeline-grounded-observation",
        )

    def test_pipeline_binds_observation_and_state_version_itself(self):
        provider = FakeGroundedProvider([self.candidate()])
        self.pipeline(provider).propose_from_observation(
            "evt-pipeline-grounded-observation"
        )
        proposal = self.store.get_proposal("grounded-pipeline-proposal")["proposal"]
        self.assertEqual(proposal["based_on"]["state_version"], 0)
        self.assertEqual(proposal["origin"]["component"], provider.provider_id)
        self.assertEqual(proposal["origin"]["version"], provider.provider_version)
        self.assertFalse(provider.called_in_transaction)

    def test_provider_candidate_is_accepted_only_after_separate_csd_evaluation(self):
        provider = FakeGroundedProvider([self.candidate(inferences=[
            GroundedInference(
                claim_id="claim-inference-1",
                text="The scene may feel delicate.",
                derived_from_claim_ids=["claim-source-1"],
                reasoning_summary="A tentative stylistic reading.",
                confidence=0.38,
            )
        ])])
        self.pipeline(provider).propose_from_observation(
            "evt-pipeline-grounded-observation"
        )
        self.assertEqual(self.store.get_memories(), [])
        decision = self.store.evaluate_proposal("grounded-pipeline-proposal")
        self.assertEqual(decision["status"], "accepted")
        claims = self.store.get_memories()[0]["claims"]
        self.assertEqual([c["epistemic_type"] for c in claims],
                         ["source_assertion", "inference"])

    def test_provider_runs_outside_write_transaction(self):
        provider = FakeGroundedProvider([self.candidate()])
        self.pipeline(provider).propose_from_observation(
            "evt-pipeline-grounded-observation"
        )
        self.assertFalse(provider.called_in_transaction)

    def test_provider_failure_leaves_csd_unchanged(self):
        provider = FakeGroundedProvider()
        def fail(observation, *, state_version):
            raise TimeoutError("synthetic provider timeout")
        provider.propose_grounded = fail
        before = self.store.get_state_snapshot()
        with self.assertRaises(TimeoutError):
            self.pipeline(provider).propose_from_observation(
                "evt-pipeline-grounded-observation"
            )
        self.assertEqual(self.store.get_state_snapshot(), before)

    def test_empty_provider_result_creates_no_proposal(self):
        provider = FakeGroundedProvider()
        result = self.pipeline(provider).propose_from_observation(
            "evt-pipeline-grounded-observation"
        )
        self.assertEqual(result, [])
        self.assertEqual(self.store.get_state_snapshot()["proposal_count"], 0)

    def test_provider_output_is_limited_to_one_candidate_per_call(self):
        provider = FakeGroundedProvider([
            self.candidate("candidate-1"),
            self.candidate("candidate-2"),
        ])
        before = self.store.get_state_snapshot()
        with self.assertRaises(ValueError):
            self.pipeline(provider).propose_from_observation(
                "evt-pipeline-grounded-observation"
            )
        self.assertEqual(self.store.get_state_snapshot(), before)

    def test_wrong_quote_is_saved_pending_then_rejected_by_csd(self):
        invalid = self.candidate(
            quote="A red feather rested on the windowsill.",
            start=0,
            end=len("A red feather rested on the windowsill."),
        )
        provider = FakeGroundedProvider([invalid])
        self.pipeline(provider).propose_from_observation(
            "evt-pipeline-grounded-observation"
        )
        result = self.store.evaluate_proposal("grounded-pipeline-proposal")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.get_memories(), [])

    def test_non_observation_input_never_calls_provider(self):
        provider = FakeGroundedProvider([self.candidate()])
        proposal = CognitiveEvent(
            event_id="evt-pipeline-not-observation",
            occurred_at="2026-11-14T10:01:00+00:00",
            correlation_id="corr-grounded-pipeline",
            event_type="cognition.grounded_memory_candidate_proposed.v1",
            source="test.fixture",
            payload={
                "proposal_id": "unrelated",
                "memory_kind": "episodic_candidate",
                "claims": [{
                    "claim_id": "c",
                    "text": "unused",
                    "epistemic_type": "source_assertion",
                    "evidence": [{
                        "event_id": "evt-pipeline-grounded-observation",
                        "locator": {"kind": "text_range", "unit": "unicode_codepoint", "start": 0, "end": 1},
                        "quoted_text": "A",
                    }],
                    "uncertainty": {"label": "directly_quoted", "confidence": None},
                }],
                "origin": {"component": "test.fixture", "version": "0.1"},
                "based_on": {"state_version": 0},
                "operation": "create",
            },
        )
        self.store.submit_event(proposal)
        with self.assertRaises(ValueError):
            self.pipeline(provider).propose_from_observation("evt-pipeline-not-observation")
        self.assertIsNone(provider.called_in_transaction)

    def test_bad_provider_offset_type_is_rejected_before_event_submission(self):
        bad = GroundedMemoryCandidate(
            proposal_id="bad-offset",
            memory_kind="episodic_candidate",
            source_assertions=[GroundedSourceAssertion(
                claim_id="claim-source-1",
                text="x",
                quoted_text="x",
                start=True,
                end=1,
            )],
        )
        provider = FakeGroundedProvider([bad])
        before = self.store.get_state_snapshot()
        with self.assertRaises(ValueError):
            self.pipeline(provider).propose_from_observation(
                "evt-pipeline-grounded-observation"
            )
        self.assertEqual(self.store.get_state_snapshot(), before)


if __name__ == "__main__":
    unittest.main()
