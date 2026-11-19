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
    list_cross_episode_proposals,
)
from core.csd.cross_episode_proposals import (
    CrossEpisodeProposalError,
    build_cross_episode_proposal,
)
from core.csd.cognitive import OBSERVATION_EVENT


class CrossEpisodeProposalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CognitiveMemoryStore(Path(self.temp.name) / "cross_episode.sqlite3")
        quote = "The user chose a quiet corner table."
        self.store.submit_event(CognitiveEvent(
            event_id="evt-cross-episode",
            occurred_at="2026-11-20T08:00:00+00:00",
            correlation_id="corr-cross-episode",
            event_type=OBSERVATION_EVENT,
            source="test.cross_episode",
            payload={
                "observation_id": "obs-cross-episode",
                "observation_kind": "text_fixture",
                "content": quote,
                "source_ref": "fixture://cross-episode",
                "observed_at": "2026-11-20T07:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

        class Provider:
            provider_id = "test.cross_episode_provider"
            provider_version = "1"

            def propose_grounded(inner_self, observation, *, state_version):
                return [GroundedMemoryCandidate(
                    proposal_id="cross-episode-memory-proposal",
                    memory_kind="episodic_candidate",
                    source_assertions=[GroundedSourceAssertion(
                        claim_id="claim-quiet-table",
                        text=quote,
                        quoted_text=quote,
                        start=0,
                        end=len(quote),
                    )],
                )]

        GroundedMemoryProposalPipeline(self.store, Provider()).propose_from_observation(
            "evt-cross-episode"
        )
        self.store.evaluate_proposal("cross-episode-memory-proposal")
        self.memory = self.store.get_memories()[0]
        self.version = self.store.get_state_snapshot()["state_version"]
        self.context = build_accepted_claim_reference_context(
            self.store,
            [{"memory_id": self.memory["memory_id"], "claim_id": "claim-quiet-table"}],
            expected_state_version=self.version,
        )

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def payload(self):
        return {
            "schema_version": 1,
            "based_on_state_version": self.version,
            "candidate_kind": "preference_candidate",
            "owner": "user",
            "domain": "dining_environment",
            "statement": "The user may prefer quieter dining environments.",
            "scope": "Restaurant and cafe choices when atmosphere is relevant.",
            "exclusions": ["This does not imply a preference for isolation."],
            "confidence": 0.55,
            "uncertainty": "moderate",
            "reasoning_summary": "One accepted episode provides limited evidence.",
            "alternatives": ["The choice may have been situational."],
            "limitations": ["Only one independent source event is available."],
            "support_reference_keys": ["historical-claim-0001"],
            "counter_evidence_reference_keys": [],
        }

    def test_valid_candidate_is_shadow_only_and_keeps_provenance(self):
        result = build_cross_episode_proposal(
            self.store,
            self.payload(),
            self.context,
            proposal_id="cross-episode-candidate-1",
            provider_id="test.cross_episode_model",
            provider_version="1",
            expected_state_version=self.version,
        )
        self.assertEqual(result.status, "pending_shadow")
        self.assertEqual(result.candidate.status, "shadow")
        self.assertEqual(result.candidate.owner, "user")
        self.assertEqual(result.candidate.independent_support_event_count, 1)
        self.assertEqual(
            result.candidate.supporting_references[0]["source_event_ids"],
            ["evt-cross-episode"],
        )
        appended = append_cross_episode_proposal(
            self.store, result, occurred_at="2026-11-20T08:10:00+00:00"
        )
        self.assertEqual(appended["status"], "accepted")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], self.version)
        stored = list_cross_episode_proposals(self.store)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["proposal_id"], "cross-episode-candidate-1")
        self.assertEqual(stored[0]["status"], "pending_shadow")
        self.assertNotIn("claim", stored[0]["payload"]["candidate"]["supporting_references"][0])
        self.assertEqual(
            self.store.get_proposal("cross-episode-memory-proposal")["status"],
            "accepted",
        )
        recovered = self.store.recover()
        self.assertGreaterEqual(recovered["events"], 1)
        self.assertTrue(self.store.get_state_snapshot()["projection_consistent"])
        self.assertEqual(len(list_cross_episode_proposals(self.store)), 1)

    def test_append_revalidates_claim_digest_inside_csd_transaction(self):
        result = build_cross_episode_proposal(
            self.store,
            self.payload(),
            self.context,
            proposal_id="cross-episode-tampered",
            provider_id="test.cross_episode_model",
            provider_version="1",
            expected_state_version=self.version,
        )
        reference = result.candidate.supporting_references[0]
        reference["claim_digest"] = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(ValueError, "stale/tampered"):
            append_cross_episode_proposal(
                self.store, result, occurred_at="2026-11-20T08:11:00+00:00"
            )
        self.assertEqual(list_cross_episode_proposals(self.store), [])
        self.assertEqual(self.store.get_state_snapshot()["state_version"], self.version)

    def test_append_rejects_candidate_after_authoritative_state_changes(self):
        result = build_cross_episode_proposal(
            self.store,
            self.payload(),
            self.context,
            proposal_id="cross-episode-stale",
            provider_id="test.cross_episode_model",
            provider_version="1",
            expected_state_version=self.version,
        )
        later_quote = "A later independent observation."
        self.store.submit_event(CognitiveEvent(
            event_id="evt-cross-episode-later",
            occurred_at="2026-11-20T08:12:00+00:00",
            correlation_id="corr-cross-episode-later",
            event_type=OBSERVATION_EVENT,
            source="test.cross_episode",
            payload={
                "observation_id": "obs-cross-episode-later",
                "observation_kind": "text_fixture",
                "content": later_quote,
                "source_ref": "fixture://cross-episode-later",
                "observed_at": "2026-11-20T08:11:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

        class LaterProvider:
            provider_id = "test.cross_episode_later_provider"
            provider_version = "1"

            def propose_grounded(inner_self, observation, *, state_version):
                return [GroundedMemoryCandidate(
                    proposal_id="cross-episode-later-memory-proposal",
                    memory_kind="episodic_candidate",
                    source_assertions=[GroundedSourceAssertion(
                        claim_id="claim-later-observation",
                        text=later_quote,
                        quoted_text=later_quote,
                        start=0,
                        end=len(later_quote),
                    )],
                )]

        GroundedMemoryProposalPipeline(self.store, LaterProvider()).propose_from_observation(
            "evt-cross-episode-later"
        )
        self.store.evaluate_proposal("cross-episode-later-memory-proposal")
        self.assertEqual(
            self.store.get_state_snapshot()["state_version"], self.version + 1
        )
        with self.assertRaisesRegex(ValueError, "stale"):
            append_cross_episode_proposal(
                self.store, result, occurred_at="2026-11-20T08:13:00+00:00"
            )
        self.assertEqual(list_cross_episode_proposals(self.store), [])

    def test_unknown_authority_fields_and_owner_confusion_fail_closed(self):
        payload = self.payload()
        payload["memory_id"] = self.memory["memory_id"]
        with self.assertRaises(CrossEpisodeProposalError):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )

        payload = self.payload()
        payload["owner"] = "ai"
        with self.assertRaisesRegex(CrossEpisodeProposalError, "owner"):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )

    def test_unknown_reference_key_and_stale_snapshot_fail_closed(self):
        payload = self.payload()
        payload["support_reference_keys"] = ["model-invented-key"]
        with self.assertRaises(CrossEpisodeProposalError):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )

        payload = self.payload()
        payload["based_on_state_version"] = self.version + 1
        with self.assertRaises(CrossEpisodeProposalError):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )

    def test_support_and_counter_evidence_cannot_share_a_reference(self):
        payload = self.payload()
        payload["counter_evidence_reference_keys"] = ["historical-claim-0001"]
        with self.assertRaisesRegex(CrossEpisodeProposalError, "both support"):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )

    def test_boolean_schema_version_and_unhashable_enums_fail_closed(self):
        payload = self.payload()
        payload["schema_version"] = True
        with self.assertRaises(CrossEpisodeProposalError):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )

        payload = self.payload()
        payload["candidate_kind"] = []
        with self.assertRaises(CrossEpisodeProposalError):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )

        payload = self.payload()
        payload["uncertainty"] = {}
        with self.assertRaises(CrossEpisodeProposalError):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )

    def test_candidate_kind_cannot_conflate_user_preference_and_ai_interest(self):
        payload = self.payload()
        payload["candidate_kind"] = "interest_candidate"
        with self.assertRaisesRegex(CrossEpisodeProposalError, "owner"):
            build_cross_episode_proposal(
                self.store, payload, self.context,
                proposal_id="candidate", provider_id="model", provider_version="1",
                expected_state_version=self.version,
            )


if __name__ == "__main__":
    unittest.main()
