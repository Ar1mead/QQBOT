from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
    MemoryCandidate,
    MemoryProposalPipeline,
)
from core.csd.cognitive import OBSERVATION_EVENT, PROPOSAL_EVENT


class FakeProvider:
    provider_id = "test.fake_memory_provider"
    provider_version = "0.1"

    def __init__(self, candidate=None):
        self.candidate = candidate
        self.called_in_transaction = None
        self.received_state_version = None

    def propose(self, observation, *, state_version):
        self.called_in_transaction = self.store._db.in_transaction
        self.received_state_version = state_version
        if self.candidate is None:
            return []
        return [self.candidate]


class MemoryProposalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "pipeline.sqlite3"
        self.store = CognitiveMemoryStore(self.db_path)
        self.observation = CognitiveEvent(
            event_id="evt-pipeline-observation",
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-pipeline",
            event_type=OBSERVATION_EVENT,
            source="test.observation_fixture",
            payload={
                "observation_id": "obs-pipeline",
                "observation_kind": "text_fixture",
                "content": "A fictional red kite crossed a quiet field.",
                "source_ref": "fixture://pipeline/observation",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        )
        self.store.submit_event(self.observation)

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def candidate(self, proposal_id="pipeline-proposal-1"):
        return MemoryCandidate(
            proposal_id=proposal_id,
            memory_kind="episodic_candidate",
            candidate_content="I encountered a fictional description of a red kite.",
            uncertainty_label="fixture_only",
            confidence=0.5,
        )

    def pipeline(self, provider):
        provider.store = self.store
        return MemoryProposalPipeline(self.store, provider)

    def test_pipeline_persists_candidate_without_accepting_memory(self):
        provider = FakeProvider(self.candidate())
        results = self.pipeline(provider).propose_from_observation(
            "evt-pipeline-observation"
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "accepted")
        self.assertEqual(self.store.get_memories(), [])
        proposal = self.store.get_proposal("pipeline-proposal-1")
        self.assertEqual(proposal["status"], "pending")
        self.assertEqual(
            proposal["proposal"]["evidence_event_ids"],
            ["evt-pipeline-observation"],
        )

    def test_pipeline_proposal_can_be_evaluated_by_csd_later(self):
        provider = FakeProvider(self.candidate())
        self.pipeline(provider).propose_from_observation("evt-pipeline-observation")
        self.assertEqual(self.store.get_memories(), [])
        decision = self.store.evaluate_proposal("pipeline-proposal-1")
        self.assertEqual(decision["status"], "accepted")
        self.assertEqual(len(self.store.get_memories()), 1)

    def test_pipeline_rejects_invalid_confidence_before_submission(self):
        invalid = MemoryCandidate(
            proposal_id="bad-confidence",
            memory_kind="episodic_candidate",
            candidate_content="candidate",
            uncertainty_label="uncertain",
            confidence=1.5,
        )
        provider = FakeProvider(invalid)
        before = self.store.get_state_snapshot()
        with self.assertRaises(ValueError):
            self.pipeline(provider).propose_from_observation(
                "evt-pipeline-observation"
            )
        self.assertEqual(self.store.get_state_snapshot(), before)

    def test_provider_runs_outside_sqlite_transaction(self):
        provider = FakeProvider(self.candidate())
        self.pipeline(provider).propose_from_observation("evt-pipeline-observation")
        self.assertFalse(provider.called_in_transaction)

    def test_provider_receives_current_accepted_state_version(self):
        provider = FakeProvider(self.candidate())
        self.pipeline(provider).propose_from_observation("evt-pipeline-observation")
        self.assertEqual(provider.received_state_version, 0)
        proposal = self.store.get_proposal("pipeline-proposal-1")["proposal"]
        self.assertEqual(proposal["based_on"]["state_version"], 0)

    def test_empty_provider_result_creates_no_proposal(self):
        provider = FakeProvider()
        results = self.pipeline(provider).propose_from_observation(
            "evt-pipeline-observation"
        )
        self.assertEqual(results, [])
        self.assertEqual(self.store.get_state_snapshot()["proposal_count"], 0)
        self.assertEqual(self.store.get_memories(), [])

    def test_provider_output_type_is_checked(self):
        provider = FakeProvider()
        provider.propose = lambda observation, *, state_version: ["not a candidate"]
        with self.assertRaises(TypeError):
            self.pipeline(provider).propose_from_observation(
                "evt-pipeline-observation"
            )
        self.assertEqual(self.store.get_state_snapshot()["proposal_count"], 0)

    def test_provider_failure_does_not_mutate_csd(self):
        provider = FakeProvider()
        def fail(observation, *, state_version):
            raise TimeoutError("synthetic provider timeout")
        provider.propose = fail
        before = self.store.get_state_snapshot()
        with self.assertRaises(TimeoutError):
            self.pipeline(provider).propose_from_observation(
                "evt-pipeline-observation"
            )
        self.assertEqual(self.store.get_state_snapshot(), before)

    def test_pipeline_rejects_non_observation_event(self):
        proposal_event = CognitiveEvent(
            event_id="evt-not-observation",
            occurred_at="2026-11-14T10:01:00+00:00",
            correlation_id="corr-pipeline",
            event_type=PROPOSAL_EVENT,
            source="test.fixture",
            payload={
                "proposal_id": "other",
                "memory_kind": "episodic_candidate",
                "candidate_content": "candidate",
                "evidence_event_ids": ["evt-pipeline-observation"],
                "origin": {"component": "test.fixture", "version": "0.1"},
                "uncertainty": {"label": "test", "confidence": None},
                "based_on": {"state_version": 0},
                "operation": "create",
            },
        )
        self.store.submit_event(proposal_event)
        provider = FakeProvider(self.candidate())
        with self.assertRaises(ValueError):
            self.pipeline(provider).propose_from_observation("evt-not-observation")
        self.assertIsNone(provider.called_in_transaction)

    def test_provider_is_not_given_corrupted_observation_payload(self):
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute(
            "UPDATE events SET event_digest='tampered' WHERE event_id=?",
            ("evt-pipeline-observation",),
        )
        provider = FakeProvider(self.candidate())
        with self.assertRaises(CognitiveIntegrityError):
            self.pipeline(provider).propose_from_observation(
                "evt-pipeline-observation"
            )
        self.assertIsNone(provider.called_in_transaction)
        self.assertEqual(self.store.get_state_snapshot()["proposal_count"], 0)

    def test_pipeline_stops_if_projection_is_inconsistent(self):
        prior_provider = FakeProvider(self.candidate("prior-accepted-memory"))
        self.pipeline(prior_provider).propose_from_observation(
            "evt-pipeline-observation"
        )
        self.store.evaluate_proposal("prior-accepted-memory")
        self.store._db.execute("DELETE FROM accepted_memories")

        provider = FakeProvider(self.candidate("blocked-by-recovery"))
        with self.assertRaises(CognitiveIntegrityError):
            self.pipeline(provider).propose_from_observation(
                "evt-pipeline-observation"
            )
        self.assertIsNone(provider.called_in_transaction)


if __name__ == "__main__":
    unittest.main()
