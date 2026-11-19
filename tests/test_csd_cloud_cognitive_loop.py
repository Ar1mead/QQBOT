from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveMemoryStore,
    OpenAICompatibleGroundedMemoryProvider,
    OpenAICompatibleSemanticReviewProvider,
    SemanticReviewPipeline,
    GroundedMemoryProposalPipeline,
)
from core.csd.cognitive import OBSERVATION_EVENT


def chat_response(value):
    return json.dumps({
        "choices": [{"message": {"content": json.dumps(value, ensure_ascii=False)}}],
    }).encode("utf-8")


class OpenAICompatibleCognitiveLoopIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = CognitiveMemoryStore(Path(self.temp.name) / "cloud-loop.sqlite3")
        self.text = "我喜欢安静的咖啡馆。"
        self.store.submit_event(CognitiveEvent(
            event_id="evt-cloud-loop-observation",
            occurred_at="2026-11-19T09:00:00+00:00",
            correlation_id="corr-cloud-loop",
            event_type=OBSERVATION_EVENT,
            source="test.cloud_loop",
            payload={
                "observation_id": "obs-cloud-loop",
                "observation_kind": "text_fixture",
                "content": self.text,
                "source_ref": "fixture://cloud-loop/observation",
                "observed_at": "2026-11-19T08:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        ))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_cloud_grounded_provider_and_cloud_reviewer_complete_pending_to_csd_acceptance(self):
        grounded_result = {
            "proposal_id": "cloud-loop-proposal",
            "memory_kind": "episodic_candidate",
            "source_assertions": [{
                "claim_id": "claim-quiet-cafe",
                "text": self.text,
                "quoted_text": self.text,
                "start": 0,
                "end": len(self.text),
            }],
            "inferences": [{
                "claim_id": "claim-quiet-preference-hypothesis",
                "text": "用户可能偏好安静的咖啡馆。",
                "derived_from_claim_ids": ["claim-quiet-cafe"],
                "reasoning_summary": "The user explicitly expressed liking the quiet environment.",
                "uncertainty_label": "tentative_interpretation",
                "confidence": 0.42,
            }],
        }
        reviewer_result = {
            "outcome": "supported",
            "reasoning_summary": "The explicit statement supports a tentative, context-limited interpretation.",
            "supporting_claim_ids": ["claim-quiet-cafe"],
            "alternative_explanations": ["This may be a preference for this specific visit only."],
            "limitations": ["One observation cannot establish a stable long-term preference."],
        }
        grounded_calls = []
        review_calls = []

        def grounded_transport(url, headers, body, timeout):
            grounded_calls.append(json.loads(body.decode("utf-8")))
            return chat_response(grounded_result)

        def review_transport(url, headers, body, timeout):
            review_calls.append(json.loads(body.decode("utf-8")))
            return chat_response(reviewer_result)

        grounded = OpenAICompatibleGroundedMemoryProvider(
            model="test-grounded",
            base_url="https://api.example.test/v1",
            api_key="test-key",
            transport=grounded_transport,
        )
        proposal_result = GroundedMemoryProposalPipeline(
            self.store, grounded
        ).propose_from_observation("evt-cloud-loop-observation")
        self.assertEqual(proposal_result[0]["status"], "accepted")
        self.assertEqual(
            self.store.get_proposal("cloud-loop-proposal")["status"], "pending"
        )
        self.assertEqual(self.store.get_memories(), [])

        first_decision = self.store.evaluate_proposal("cloud-loop-proposal")
        self.assertEqual(first_decision["status"], "awaiting_review")

        reviewer = OpenAICompatibleSemanticReviewProvider(
            model="test-reviewer",
            base_url="https://api.example.test/v1",
            api_key="test-key",
            transport=review_transport,
        )
        review_events = SemanticReviewPipeline(
            self.store, reviewer
        ).review_proposal("cloud-loop-proposal")
        self.assertEqual(len(review_events), 1)

        final_decision = self.store.evaluate_proposal("cloud-loop-proposal")
        self.assertEqual(final_decision["status"], "accepted")
        memories = self.store.get_memories()
        self.assertEqual(len(memories), 1)
        self.assertEqual(
            [claim["epistemic_type"] for claim in memories[0]["claims"]],
            ["source_assertion", "inference"],
        )
        self.assertEqual(memories[0]["semantic_review_status"], "supported")
        self.assertEqual(len(grounded_calls), 1)
        self.assertEqual(len(review_calls), 1)
        self.assertIn(
            "not a truth oracle",
            review_calls[0]["messages"][0]["content"],
        )
        reviewed_payload = json.loads(review_calls[0]["messages"][1]["content"])
        self.assertEqual(
            reviewed_payload["inference_claim"]["claim_id"],
            "claim-quiet-preference-hypothesis",
        )


if __name__ == "__main__":
    unittest.main()
