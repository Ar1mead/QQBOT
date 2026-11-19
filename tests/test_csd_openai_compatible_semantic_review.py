from __future__ import annotations

import json
import unittest

from core.csd import SemanticReviewCandidate
from core.csd.openai_compatible_provider import (
    CloudSemanticReviewProviderError,
    OpenAICompatibleSemanticReviewProvider,
)


def response(content: str) -> bytes:
    return json.dumps({
        "choices": [{"message": {"content": content}}],
    }).encode("utf-8")


def review_payload(**overrides):
    value = {
        "outcome": "supported",
        "reasoning_summary": "The source claim gives direct support, but does not prove a universal preference.",
        "supporting_claim_ids": ["source-1"],
        "alternative_explanations": ["The statement may describe a one-time choice."],
        "limitations": ["Only one observation is available."],
    }
    value.update(overrides)
    return json.dumps(value, ensure_ascii=False)


class CapturingTransport:
    def __init__(self, raw):
        self.raw = raw
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, headers, json.loads(body.decode("utf-8")), timeout))
        if isinstance(self.raw, Exception):
            raise self.raw
        return self.raw


class OpenAICompatibleSemanticReviewProviderTests(unittest.TestCase):
    def setUp(self):
        self.proposal = {
            "proposal_id": "proposal-1",
            "claims": [],
        }
        self.inference = {
            "claim_id": "inference-1",
            "text": "The user may prefer quiet places.",
            "epistemic_type": "inference",
            "derived_from_claim_ids": ["source-1"],
            "reasoning_summary": "The user explicitly said the place was peaceful.",
            "uncertainty": {"label": "tentative", "confidence": 0.45},
        }
        self.support = [{
            "claim_id": "source-1",
            "text": "I liked how quiet it was.",
            "epistemic_type": "source_assertion",
            "evidence": [{
                "event_id": "evt-1",
                "quoted_text": "I liked how quiet it was.",
            }],
        }]

    def provider(self, raw):
        transport = CapturingTransport(raw)
        provider = OpenAICompatibleSemanticReviewProvider(
            model="test-model",
            base_url="https://api.example.test/v1",
            api_key="test-key",
            transport=transport,
        )
        return provider, transport

    def test_returns_typed_review_and_sends_bounded_proposal_context(self):
        provider, transport = self.provider(response(review_payload()))
        result = provider.review_inference(
            self.proposal, self.inference, self.support
        )
        self.assertIsInstance(result, SemanticReviewCandidate)
        self.assertEqual(result.outcome, "supported")
        self.assertEqual(result.supporting_claim_ids, ["source-1"])
        url, headers, body, timeout = transport.calls[0]
        self.assertEqual(url, "https://api.example.test/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertEqual(body["temperature"], 0.0)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertIn("not a truth oracle", body["messages"][0]["content"])
        user_payload = json.loads(body["messages"][1]["content"])
        self.assertEqual(user_payload["inference_claim"]["claim_id"], "inference-1")
        self.assertEqual(user_payload["direct_source_claims"][0]["claim_id"], "source-1")
        self.assertEqual(timeout, 25.0)
        self.assertFalse(hasattr(provider, "store"))

    def test_accepts_non_supported_outcomes_without_inventing_support(self):
        for outcome in ("uncertain", "unsupported", "insufficient_context"):
            with self.subTest(outcome=outcome):
                payload = review_payload(outcome=outcome, supporting_claim_ids=[])
                provider, _ = self.provider(response(payload))
                result = provider.review_inference(
                    self.proposal, self.inference, self.support
                )
                self.assertEqual(result.outcome, outcome)
                self.assertEqual(result.supporting_claim_ids, [])

    def test_rejects_unknown_supporting_claim_id(self):
        provider, _ = self.provider(response(review_payload(
            supporting_claim_ids=["source-2"]
        )))
        with self.assertRaises(CloudSemanticReviewProviderError):
            provider.review_inference(self.proposal, self.inference, self.support)

    def test_rejects_supported_review_without_support(self):
        provider, _ = self.provider(response(review_payload(
            supporting_claim_ids=[]
        )))
        with self.assertRaises(CloudSemanticReviewProviderError):
            provider.review_inference(self.proposal, self.inference, self.support)

    def test_rejects_extra_fields_and_duplicate_json_keys(self):
        extra = json.loads(review_payload())
        extra["accepted"] = True
        provider, _ = self.provider(response(json.dumps(extra)))
        with self.assertRaises(CloudSemanticReviewProviderError):
            provider.review_inference(self.proposal, self.inference, self.support)

        duplicate = '{"outcome":"supported","outcome":"unsupported"}'
        provider, _ = self.provider(response(duplicate))
        with self.assertRaises(CloudSemanticReviewProviderError):
            provider.review_inference(self.proposal, self.inference, self.support)

    def test_rejects_non_source_support_and_non_inference_claim(self):
        bad_support = [dict(self.support[0], epistemic_type="inference")]
        provider, _ = self.provider(response(review_payload()))
        with self.assertRaises(ValueError):
            provider.review_inference(self.proposal, self.inference, bad_support)

        bad_inference = dict(self.inference, epistemic_type="source_assertion")
        with self.assertRaises(ValueError):
            provider.review_inference(self.proposal, bad_inference, self.support)

    def test_rejects_oversized_input_and_response(self):
        provider, _ = self.provider(response(review_payload()))
        huge_proposal = {"proposal_id": "p", "large": "x" * 25000}
        with self.assertRaisesRegex(ValueError, "input exceeds"):
            provider.review_inference(huge_proposal, self.inference, self.support)

        oversized = CapturingTransport(b"x" * 262145)
        provider = OpenAICompatibleSemanticReviewProvider(
            model="test-model", api_key="test-key", transport=oversized
        )
        with self.assertRaises(CloudSemanticReviewProviderError):
            provider.review_inference(self.proposal, self.inference, self.support)

    def test_wraps_transport_timeout_without_leaking_secrets(self):
        provider, _ = self.provider(TimeoutError("secret transport detail"))
        with self.assertRaises(CloudSemanticReviewProviderError) as raised:
            provider.review_inference(self.proposal, self.inference, self.support)
        self.assertNotIn("secret", str(raised.exception))

    def test_rejects_invalid_endpoint_and_missing_credentials(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleSemanticReviewProvider(
                model="test-model", base_url="http://insecure.example/v1",
                api_key="test-key",
            )
        with self.assertRaises(ValueError):
            OpenAICompatibleSemanticReviewProvider(
                model="test-model", base_url="https://api.example.test/v1",
                api_key=" ",
            )


if __name__ == "__main__":
    unittest.main()
