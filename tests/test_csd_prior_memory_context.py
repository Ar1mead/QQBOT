from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.csd import (
    CognitiveEvent,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
    GroundedMemoryCandidate,
    GroundedMemoryProposalPipeline,
    GroundedSourceAssertion,
)
from core.csd.cognitive import OBSERVATION_EVENT
from core.csd.prior_memory_context import (
    CONTEXT_SCHEMA_VERSION,
    PriorMemoryContextError,
    build_prior_memory_context,
)


def memory(memory_id, text, *, created_at="2026-11-18T10:00:00+00:00",
           epistemic_type="source_assertion"):
    return {
        "memory_id": memory_id,
        "proposal_id": "proposal-" + memory_id,
        "created_at": created_at,
        "memory_kind": "episodic_candidate",
        "status": "accepted",
        "content": "",
        "claims": [{
            "claim_id": "claim-" + memory_id,
            "text": text,
            "epistemic_type": epistemic_type,
            "uncertainty": {"label": "directly_quoted", "confidence": None},
            "evidence": [{
                "event_id": "evt-source-" + memory_id,
                "locator": {"kind": "text_range", "unit": "unicode_codepoint", "start": 0, "end": len(text)},
                "quoted_text": text,
            }],
        }],
        "evidence_event_ids": ["evt-source-" + memory_id],
    }


class PriorMemoryContextSelectorTests(unittest.TestCase):
    def test_empty_history_has_versioned_empty_context(self):
        result = build_prior_memory_context([], "new experience", state_version=3)
        self.assertEqual(result["schema_version"], CONTEXT_SCHEMA_VERSION)
        self.assertEqual(result["state_version"], 3)
        self.assertEqual(result["memories"], [])
        self.assertTrue(result["historical_text_is_untrusted"])

    def test_english_relevance_orders_matching_memory_before_unrelated(self):
        relevant = memory("coffee", "The user enjoys coffee in the morning.")
        unrelated = memory("ocean", "The user watched waves near the shore.")
        result = build_prior_memory_context(
            [unrelated, relevant], "coffee this morning", state_version=4
        )
        self.assertEqual(result["memories"][0]["memory_id"], "coffee")
        self.assertEqual(result["selector_algorithm"], "unicode-lexical-overlap-v1")

    def test_chinese_bigram_retrieval_finds_relevant_memory(self):
        relevant = memory("tea", "用户喜欢喝乌龙茶")
        unrelated = memory("train", "用户今天乘坐火车")
        result = build_prior_memory_context([unrelated, relevant], "我想喝乌龙茶", state_version=1)
        self.assertEqual([item["memory_id"] for item in result["memories"]], ["tea"])

    def test_ties_are_deterministic_by_timestamp_then_memory_id(self):
        a = memory("b-id", "likes coffee", created_at="2026-11-18T10:00:00+00:00")
        b = memory("a-id", "likes coffee", created_at="2026-11-18T10:00:00+00:00")
        first = build_prior_memory_context([a, b], "coffee", state_version=1)
        second = build_prior_memory_context([b, a], "coffee", state_version=1)
        self.assertEqual(
            [item["memory_id"] for item in first["memories"]],
            [item["memory_id"] for item in second["memories"]],
        )
        self.assertEqual(first["memories"][0]["memory_id"], "a-id")

    def test_more_recent_memory_wins_equal_relevance_score(self):
        older = memory("older", "likes coffee", created_at="2026-11-17T10:00:00+00:00")
        newer = memory("newer", "likes coffee", created_at="2026-11-19T10:00:00+00:00")
        result = build_prior_memory_context([older, newer], "coffee", state_version=1)
        self.assertEqual(result["memories"][0]["memory_id"], "newer")

    def test_duplicate_identical_ids_are_deduplicated_and_conflicts_rejected(self):
        item = memory("same", "likes coffee")
        result = build_prior_memory_context([item, dict(item)], "coffee", state_version=0)
        self.assertEqual(len(result["memories"]), 1)
        conflict = memory("same", "dislikes coffee")
        with self.assertRaises(PriorMemoryContextError):
            build_prior_memory_context([item, conflict], "coffee", state_version=0)

    def test_non_accepted_memory_is_rejected(self):
        item = memory("pending", "likes coffee")
        item["status"] = "pending"
        with self.assertRaises(PriorMemoryContextError):
            build_prior_memory_context([item], "coffee", state_version=0)

    def test_per_item_and_total_budgets_are_explicit_and_bounded(self):
        item = memory("long", "coffee " * 300)
        other = memory("longer", "coffee " * 300, created_at="2026-11-17T10:00:00+00:00")
        result = build_prior_memory_context(
            [item, other], "coffee", state_version=2, per_item_chars=40, total_chars=1200
        )
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
        self.assertLessEqual(len(encoded), 1200)
        self.assertTrue(result["memories"][0]["truncated"])
        self.assertIn("long", result["truncated_memory_ids"])
        self.assertLessEqual(len(result["memories"][0]["claims"][0]["text"]), 40)
        self.assertEqual(result["truncated_memory_ids"][0], "long")

    def test_context_retains_claim_type_uncertainty_and_evidence_provenance(self):
        result = build_prior_memory_context(
            [memory("grounded", "coffee after lunch")], "coffee", state_version=5
        )
        claim = result["memories"][0]["claims"][0]
        self.assertEqual(claim["epistemic_type"], "source_assertion")
        self.assertEqual(claim["uncertainty"]["label"], "directly_quoted")
        self.assertEqual(claim["evidence"][0]["event_id"], "evt-source-grounded")
        self.assertEqual(result["memories"][0]["proposal_id"], "proposal-grounded")

    def test_invalid_memory_fields_and_budgets_fail_closed(self):
        bad = memory("bad", "coffee")
        del bad["proposal_id"]
        with self.assertRaises(PriorMemoryContextError):
            build_prior_memory_context([bad], "coffee", state_version=0)
        with self.assertRaises(ValueError):
            build_prior_memory_context([], "coffee", state_version=0, max_items=True)


class CapturingProvider:
    provider_id = "test.context_capture"
    provider_version = "1"

    def __init__(self, candidate=None):
        self.candidate = candidate
        self.observation = None
        self.state_version = None

    def propose_grounded(self, observation, *, state_version):
        self.observation = observation
        self.state_version = state_version
        return [] if self.candidate is None else [self.candidate]


class PriorMemoryPipelineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CognitiveMemoryStore(Path(self.temp.name) / "context.sqlite3")
        self._add_observation(
            "evt-context-first", "用户喜欢喝咖啡。", "corr-context-first",
            "2026-11-18T10:00:00+00:00",
        )

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def _add_observation(self, event_id, content, correlation_id, occurred_at):
        self.store.submit_event(CognitiveEvent(
            event_id=event_id,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            event_type=OBSERVATION_EVENT,
            source="test.context_observation",
            payload={
                "observation_id": "obs-" + event_id,
                "observation_kind": "text_fixture",
                "content": content,
                "source_ref": "fixture://" + event_id,
                "observed_at": occurred_at,
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

    def test_pipeline_passes_only_accepted_retrieved_history_and_keeps_proposal_pending(self):
        quote = "用户喜欢喝咖啡。"
        candidate = GroundedMemoryCandidate(
            proposal_id="context-memory-proposal",
            memory_kind="episodic_candidate",
            source_assertions=[GroundedSourceAssertion(
                claim_id="context-claim",
                text=quote,
                quoted_text=quote,
                start=0,
                end=len(quote),
            )],
        )
        first = CapturingProvider(candidate)
        GroundedMemoryProposalPipeline(self.store, first).propose_from_observation("evt-context-first")
        self.assertEqual(
            self.store.get_proposal("context-memory-proposal")["status"], "pending"
        )
        self.assertEqual(self.store.get_memories(), [])
        self.store.evaluate_proposal("context-memory-proposal")

        self._add_observation(
            "evt-context-second", "今天又想喝咖啡。", "corr-context-second",
            "2026-11-19T10:00:00+00:00",
        )
        second = CapturingProvider()
        GroundedMemoryProposalPipeline(self.store, second).propose_from_observation("evt-context-second")
        context = second.observation["prior_memory_context"]
        self.assertEqual(context["schema_version"], 1)
        self.assertEqual(context["state_version"], second.state_version)
        self.assertEqual(context["memories"][0]["proposal_id"], "context-memory-proposal")
        self.assertTrue(context["historical_text_is_untrusted"])
        self.assertEqual(self.store.get_state_snapshot()["accepted_memory_count"], 1)

    def test_state_version_change_during_context_selection_aborts_before_provider(self):
        provider = CapturingProvider()
        original_snapshot = self.store.get_state_snapshot
        calls = 0

        def racing_snapshot():
            nonlocal calls
            result = original_snapshot()
            calls += 1
            if calls == 2:
                result = dict(result)
                result["state_version"] += 1
            return result

        with patch.object(self.store, "get_state_snapshot", side_effect=racing_snapshot):
            with self.assertRaisesRegex(CognitiveIntegrityError, "state changed"):
                GroundedMemoryProposalPipeline(self.store, provider).propose_from_observation(
                    "evt-context-first"
                )
        self.assertIsNone(provider.observation)


if __name__ == "__main__":
    unittest.main()
