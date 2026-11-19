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
)
from core.csd.accepted_claim_references import (
    AcceptedClaimReferenceError,
    build_accepted_claim_reference_context,
    resolve_accepted_claim_reference,
    resolve_selected_accepted_claims,
)
from core.csd.cognitive import OBSERVATION_EVENT


class AcceptedClaimReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CognitiveMemoryStore(Path(self.temp.name) / "references.sqlite3")
        self.text = "The user chose a quiet corner table."
        self.store.submit_event(CognitiveEvent(
            event_id="evt-reference-observation",
            occurred_at="2026-11-20T08:00:00+00:00",
            correlation_id="corr-reference",
            event_type=OBSERVATION_EVENT,
            source="test.reference_observation",
            payload={
                "observation_id": "obs-reference",
                "observation_kind": "text_fixture",
                "content": self.text,
                "source_ref": "fixture://reference",
                "observed_at": "2026-11-20T07:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

        class Provider:
            provider_id = "test.reference_provider"
            provider_version = "1"

            def propose_grounded(inner_self, observation, *, state_version):
                quote = "The user chose a quiet corner table."
                return [GroundedMemoryCandidate(
                    proposal_id="reference-proposal",
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
            "evt-reference-observation"
        )
        self.assertEqual(
            self.store.get_proposal("reference-proposal")["status"], "pending"
        )
        self.store.evaluate_proposal("reference-proposal")
        self.memory = self.store.get_memories()[0]

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_resolves_full_accepted_lineage_and_claim_digest(self):
        version = self.store.get_state_snapshot()["state_version"]
        result = resolve_accepted_claim_reference(
            self.store,
            memory_id=self.memory["memory_id"],
            claim_id="claim-quiet-table",
            expected_state_version=version,
        )
        self.assertEqual(result["proposal_id"], "reference-proposal")
        self.assertEqual(result["decision_event_id"], self.memory["decision_event_id"])
        self.assertEqual(result["source_event_ids"], ["evt-reference-observation"])
        self.assertTrue(result["claim_digest"].startswith("sha256:"))
        self.assertEqual(result["claim"]["claim_id"], "claim-quiet-table")

    def test_resolution_uses_one_sqlite_read_snapshot(self):
        version = self.store.get_state_snapshot()["state_version"]
        original_read_tx = self.store._read_tx
        entered = []

        def tracked_read_tx():
            entered.append(True)
            return original_read_tx()

        self.store._read_tx = tracked_read_tx
        try:
            resolve_accepted_claim_reference(
                self.store,
                memory_id=self.memory["memory_id"],
                claim_id="claim-quiet-table",
                expected_state_version=version,
            )
        finally:
            self.store._read_tx = original_read_tx
        self.assertEqual(len(entered), 1)

    def test_resolution_reuses_an_existing_csd_transaction(self):
        version = self.store.get_state_snapshot()["state_version"]
        with self.store._tx():
            result = resolve_accepted_claim_reference(
                self.store,
                memory_id=self.memory["memory_id"],
                claim_id="claim-quiet-table",
                expected_state_version=version,
            )
            self.assertEqual(result["status"], "accepted")

    def test_only_model_selected_pairs_become_opaque_reference_keys(self):
        version = self.store.get_state_snapshot()["state_version"]
        context = build_accepted_claim_reference_context(
            self.store,
            [
                {"memory_id": self.memory["memory_id"], "claim_id": "claim-quiet-table"},
                {"memory_id": self.memory["memory_id"], "claim_id": "claim-quiet-table"},
            ],
            expected_state_version=version,
        )
        self.assertEqual(list(context), ["historical-claim-0001"])
        result = resolve_selected_accepted_claims(
            self.store, context, ["historical-claim-0001"],
            expected_state_version=version,
        )
        self.assertEqual(list(result), ["historical-claim-0001"])
        self.assertEqual(
            result["historical-claim-0001"]["claim_id"], "claim-quiet-table"
        )
        with self.assertRaises(AcceptedClaimReferenceError):
            resolve_selected_accepted_claims(
                self.store, context, ["model-invented-memory-id"],
                expected_state_version=version,
            )

    def test_stale_snapshot_and_unknown_memory_fail_closed(self):
        version = self.store.get_state_snapshot()["state_version"]
        with self.assertRaisesRegex(AcceptedClaimReferenceError, "stale"):
            resolve_accepted_claim_reference(
                self.store,
                memory_id=self.memory["memory_id"],
                claim_id="claim-quiet-table",
                expected_state_version=version - 1,
            )
        with self.assertRaises(AcceptedClaimReferenceError):
            resolve_accepted_claim_reference(
                self.store,
                memory_id="missing-memory",
                claim_id="claim-quiet-table",
                expected_state_version=version,
            )

    def test_unknown_claim_and_malformed_reference_shape_fail_closed(self):
        version = self.store.get_state_snapshot()["state_version"]
        with self.assertRaises(AcceptedClaimReferenceError):
            resolve_accepted_claim_reference(
                self.store,
                memory_id=self.memory["memory_id"],
                claim_id="not-a-claim",
                expected_state_version=version,
            )
        with self.assertRaises(AcceptedClaimReferenceError):
            build_accepted_claim_reference_context(
                self.store,
                [{"memory_id": self.memory["memory_id"], "claim_id": "claim-quiet-table",
                  "decision_event_id": "model-invented"}],
                expected_state_version=version,
            )

    def test_repeated_claim_reference_does_not_inflate_independent_event_count(self):
        version = self.store.get_state_snapshot()["state_version"]
        context = build_accepted_claim_reference_context(
            self.store,
            [
                {"memory_id": self.memory["memory_id"], "claim_id": "claim-quiet-table"},
                {"memory_id": self.memory["memory_id"], "claim_id": "claim-quiet-table"},
            ],
            expected_state_version=version,
        )
        refs = resolve_selected_accepted_claims(
            self.store, context, ["historical-claim-0001", "historical-claim-0001"],
            expected_state_version=version,
        )
        independent_events = {
            event_id
            for item in refs.values()
            for event_id in item["source_event_ids"]
        }
        self.assertEqual(len(independent_events), 1)


if __name__ == "__main__":
    unittest.main()
