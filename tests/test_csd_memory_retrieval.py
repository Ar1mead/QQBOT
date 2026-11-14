from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveMemoryStore,
)
from core.csd.cognitive import (
    GROUNDED_PROPOSAL_EVENT,
    OBSERVATION_EVENT,
    PROPOSAL_EVENT,
)


class MemoryRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "retrieval.sqlite3"
        self.store = CognitiveMemoryStore(self.db_path)
        self.source_text = "A silver leaf rested on the windowsill. A blue cup sat nearby."
        self.store.submit_event(CognitiveEvent(
            event_id="evt-retrieval-observation",
            occurred_at="2026-11-14T10:00:00+00:00",
            correlation_id="corr-retrieval",
            event_type=OBSERVATION_EVENT,
            source="test.retrieval_fixture",
            payload={
                "observation_id": "obs-retrieval",
                "observation_kind": "text_fixture",
                "content": self.source_text,
                "source_ref": "fixture://retrieval/source",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def add_grounded(self, proposal_id, quote, *, memory_kind="episodic_candidate",
                     inference_text=None):
        start = self.source_text.index(quote)
        claims = [{
            "claim_id": f"{proposal_id}-source",
            "text": quote,
            "epistemic_type": "source_assertion",
            "evidence": [{
                "event_id": "evt-retrieval-observation",
                "locator": {
                    "kind": "text_range",
                    "unit": "unicode_codepoint",
                    "start": start,
                    "end": start + len(quote),
                },
                "quoted_text": quote,
            }],
            "uncertainty": {"label": "directly_quoted", "confidence": None},
        }]
        if inference_text:
            claims.append({
                "claim_id": f"{proposal_id}-inference",
                "text": inference_text,
                "epistemic_type": "inference",
                "derived_from_claim_ids": [f"{proposal_id}-source"],
                "reasoning_summary": "Synthetic test-only interpretation.",
                "uncertainty": {"label": "tentative_inference", "confidence": 0.3},
            })
        event = CognitiveEvent(
            event_id=f"evt-{proposal_id}",
            occurred_at="2026-11-14T10:01:00+00:00",
            correlation_id="corr-retrieval",
            event_type=GROUNDED_PROPOSAL_EVENT,
            source="test.retrieval_fixture",
            payload={
                "proposal_id": proposal_id,
                "memory_kind": memory_kind,
                "claims": claims,
                "origin": {"component": "test.retrieval_fixture", "version": "0.1"},
                "based_on": {"state_version": self.store.get_state_snapshot()["state_version"]},
                "operation": "create",
            },
        )
        self.store.submit_event(event)
        result = self.store.evaluate_proposal(proposal_id)
        self.assertEqual(result["status"], "accepted")

    def add_legacy(self, proposal_id, content):
        event = CognitiveEvent(
            event_id=f"evt-{proposal_id}",
            occurred_at="2026-11-14T10:02:00+00:00",
            correlation_id="corr-retrieval",
            event_type=PROPOSAL_EVENT,
            source="test.legacy_retrieval_fixture",
            payload={
                "proposal_id": proposal_id,
                "memory_kind": "legacy_note",
                "candidate_content": content,
                "evidence_event_ids": ["evt-retrieval-observation"],
                "origin": {"component": "test.legacy_retrieval_fixture", "version": "0.1"},
                "uncertainty": {"label": "legacy_test", "confidence": None},
                "based_on": {"state_version": self.store.get_state_snapshot()["state_version"]},
                "operation": "create",
            },
        )
        self.store.submit_event(event)
        result = self.store.evaluate_proposal(proposal_id)
        self.assertEqual(result["status"], "accepted")

    def seed(self):
        self.add_grounded(
            "memory-silver-leaf",
            "A silver leaf rested on the windowsill.",
            memory_kind="episodic_candidate",
            inference_text="The scene may feel quiet.",
        )
        self.add_grounded(
            "memory-blue-cup",
            "A blue cup sat nearby.",
            memory_kind="object_observation",
        )
        self.add_legacy("memory-legacy", "A legacy note about an antique map.")

    def test_retrieval_returns_accepted_memories_only(self):
        self.add_grounded("accepted-one", "A silver leaf rested on the windowsill.")
        self.store.submit_event(CognitiveEvent(
            event_id="evt-pending",
            occurred_at="2026-11-14T10:03:00+00:00",
            correlation_id="corr-retrieval",
            event_type=GROUNDED_PROPOSAL_EVENT,
            source="test.retrieval_fixture",
            payload={
                "proposal_id": "pending-only",
                "memory_kind": "episodic_candidate",
                "claims": [{
                    "claim_id": "pending-claim",
                    "text": "A blue cup sat nearby.",
                    "epistemic_type": "source_assertion",
                    "evidence": [{
                        "event_id": "evt-retrieval-observation",
                        "locator": {"kind": "text_range", "unit": "unicode_codepoint",
                                    "start": self.source_text.index("A blue cup sat nearby."),
                                    "end": self.source_text.index("A blue cup sat nearby.") + len("A blue cup sat nearby.")},
                        "quoted_text": "A blue cup sat nearby.",
                    }],
                    "uncertainty": {"label": "directly_quoted", "confidence": None},
                }],
                "origin": {"component": "test.retrieval_fixture", "version": "0.1"},
                "based_on": {"state_version": 1},
                "operation": "create",
            },
        ))
        memories = self.store.get_memories()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0]["proposal_id"], "accepted-one")

    def test_case_insensitive_substring_query_matches_claim_text(self):
        self.seed()
        results = self.store.get_memories(query="SILVER LEAF")
        self.assertEqual(
            {item["proposal_id"] for item in results},
            {"memory-silver-leaf"},
        )

    def test_query_matches_legacy_memory_content(self):
        self.seed()
        results = self.store.get_memories(query="legacy note")
        self.assertEqual([item["proposal_id"] for item in results], ["memory-legacy"])

    def test_epistemic_type_filter_distinguishes_source_and_inference(self):
        self.seed()
        sources = self.store.get_memories(epistemic_type="source_assertion")
        inferences = self.store.get_memories(epistemic_type="inference")
        self.assertEqual(
            {item["proposal_id"] for item in sources},
            {"memory-silver-leaf", "memory-blue-cup"},
        )
        self.assertEqual(
            {item["proposal_id"] for item in inferences},
            {"memory-silver-leaf"},
        )

    def test_evidence_event_filter_returns_memories_linked_to_source(self):
        self.seed()
        results = self.store.get_memories(evidence_event_id="evt-retrieval-observation")
        self.assertEqual(len(results), 3)

    def test_memory_kind_filter(self):
        self.seed()
        results = self.store.get_memories(memory_kind="object_observation")
        self.assertEqual([item["proposal_id"] for item in results], ["memory-blue-cup"])

    def test_limit_and_offset_have_stable_order(self):
        self.seed()
        all_items = self.store.get_memories()
        first = self.store.get_memories(limit=1)
        second = self.store.get_memories(limit=1, offset=1)
        self.assertEqual(first, all_items[:1])
        self.assertEqual(second, all_items[1:2])

    def test_get_memory_returns_one_full_provenance_record(self):
        self.seed()
        expected = next(m for m in self.store.get_memories() if m["proposal_id"] == "memory-silver-leaf")
        self.assertEqual(self.store.get_memory(expected["memory_id"]), expected)
        with self.assertRaises(KeyError):
            self.store.get_memory("not-a-memory")

    def test_retrieval_does_not_mutate_authoritative_state(self):
        self.seed()
        before_state = self.store.get_state_snapshot()
        before_events = self.store.get_state_snapshot()["event_count"]
        self.store.get_memories(query="silver")
        self.store.get_memories(epistemic_type="inference")
        self.store.get_memory(self.store.get_memories()[0]["memory_id"])
        self.assertEqual(self.store.get_state_snapshot(), before_state)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before_events)

    def test_invalid_filter_arguments_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.get_memories(query=" ")
        with self.assertRaises(ValueError):
            self.store.get_memories(epistemic_type="objective_fact")
        with self.assertRaises(ValueError):
            self.store.get_memories(limit=True)
        with self.assertRaises(ValueError):
            self.store.get_memories(offset=-1)


if __name__ == "__main__":
    unittest.main()
