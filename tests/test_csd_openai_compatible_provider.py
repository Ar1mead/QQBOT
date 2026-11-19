from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from core.csd import CognitiveEvent, CognitiveMemoryStore, GroundedMemoryProposalPipeline
from core.csd.cognitive import OBSERVATION_EVENT

from core.csd.openai_compatible_provider import (
    CloudProposalProviderError,
    OpenAICompatibleGroundedMemoryProvider,
)


class FakeTransport:
    def __init__(self, content):
        self.content = content
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append((url, dict(headers), json.loads(body), timeout))
        if isinstance(self.content, Exception):
            raise self.content
        return json.dumps({
            "choices": [{"message": {"content": json.dumps(self.content, ensure_ascii=False)}}]
        }).encode("utf-8")


def proposal(**overrides):
    value = {
        "proposal_id": "model-proposal-1",
        "memory_kind": "episodic_candidate",
        "source_assertions": [{
            "claim_id": "source-1",
            "text": "A silver leaf rested on the windowsill. 🍃",
            "quoted_text": "A silver leaf rested on the windowsill.",
            "start": 0,
            "end": len("A silver leaf rested on the windowsill."),
        }],
        "inferences": [{
            "claim_id": "inference-1",
            "text": "The scene may be visually delicate.",
            "derived_from_claim_ids": ["source-1"],
            "reasoning_summary": "A tentative interpretation of the imagery.",
            "uncertainty_label": "tentative_inference",
            "confidence": 0.4,
        }],
    }
    value.update(overrides)
    return value


class OpenAICompatibleGroundedProviderTests(unittest.TestCase):
    def provider(self, content):
        transport = FakeTransport(content)
        provider = OpenAICompatibleGroundedMemoryProvider(
            model="test-model",
            base_url="https://example.invalid/v1",
            api_key="test-only",
            transport=transport,
        )
        return provider, transport

    def observation(self):
        return {
            "event_id": "evt-observation-1",
            "payload": {"content": "A silver leaf rested on the windowsill. 🍃"},
        }

    def test_returns_typed_grounded_candidate_and_uses_bounded_context(self):
        provider, transport = self.provider(proposal())
        result = provider.propose_grounded(self.observation(), state_version=7)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].proposal_id, "model-proposal-1")
        self.assertEqual(result[0].source_assertions[0].end, len("A silver leaf rested on the windowsill."))
        self.assertEqual(result[0].inferences[0].derived_from_claim_ids, ("source-1",))
        url, headers, body, timeout = transport.calls[0]
        self.assertEqual(url, "https://example.invalid/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer test-only")
        self.assertEqual(body["messages"][1]["content"] and json.loads(body["messages"][1]["content"])["state_version"], 7)
        self.assertLessEqual(timeout, 25)

    def test_prior_memory_context_is_forwarded_as_untrusted_reference(self):
        provider, transport = self.provider(proposal())
        observation = self.observation()
        observation["prior_memory_context"] = {
            "schema_version": 1,
            "selector_algorithm": "unicode-lexical-overlap-v1",
            "state_version": 7,
            "historical_text_is_untrusted": True,
            "memories": [{"memory_id": "m1", "proposal_id": "p1", "claims": []}],
            "truncated_memory_ids": [],
        }
        provider.propose_grounded(observation, state_version=7)
        user_payload = json.loads(transport.calls[0][2]["messages"][1]["content"])
        self.assertEqual(user_payload["prior_memory_context"]["memories"][0]["memory_id"], "m1")
        system_prompt = transport.calls[0][2]["messages"][0]["content"]
        self.assertIn("untrusted reference data", system_prompt)
        self.assertIn("current source_text exactly", system_prompt)

    def test_rejects_prior_memory_context_with_stale_state_version(self):
        provider, _ = self.provider(proposal())
        observation = self.observation()
        observation["prior_memory_context"] = {
            "schema_version": 1,
            "selector_algorithm": "unicode-lexical-overlap-v1",
            "state_version": 6,
            "historical_text_is_untrusted": True,
            "memories": [],
            "truncated_memory_ids": [],
        }
        with self.assertRaises(ValueError):
            provider.propose_grounded(observation, state_version=7)

    def test_rejects_unknown_top_level_authority_fields(self):
        value = proposal(accepted=True)
        provider, _ = self.provider(value)
        with self.assertRaises(CloudProposalProviderError):
            provider.propose_grounded(self.observation(), state_version=0)

    def test_rejects_boolean_offsets(self):
        value = proposal()
        value["source_assertions"][0]["start"] = True
        provider, _ = self.provider(value)
        with self.assertRaises(CloudProposalProviderError):
            provider.propose_grounded(self.observation(), state_version=0)

    def test_rejects_inference_without_source_assertion(self):
        value = proposal(source_assertions=[])
        provider, _ = self.provider(value)
        with self.assertRaises(CloudProposalProviderError):
            provider.propose_grounded(self.observation(), state_version=0)

    def test_rejects_invalid_confidence(self):
        value = proposal()
        value["inferences"][0]["confidence"] = 1.2
        provider, _ = self.provider(value)
        with self.assertRaises(CloudProposalProviderError):
            provider.propose_grounded(self.observation(), state_version=0)

    def test_transport_failure_is_wrapped_without_state_access(self):
        provider, _ = self.provider(TimeoutError("synthetic timeout"))
        with self.assertRaises(CloudProposalProviderError):
            provider.propose_grounded(self.observation(), state_version=0)

    def test_requires_https_endpoint_and_api_key(self):
        with self.assertRaises(ValueError):
            OpenAICompatibleGroundedMemoryProvider(
                model="test-model", base_url="http://example.invalid/v1",
                api_key="test", transport=FakeTransport(proposal()),
            )
        with self.assertRaises(ValueError):
            OpenAICompatibleGroundedMemoryProvider(
                model="test-model", base_url="https://example.invalid/v1",
                api_key="", transport=FakeTransport(proposal()),
            )

    def test_empty_assertion_result_is_a_valid_no_proposal(self):
        value = proposal(source_assertions=[], inferences=[])
        provider, transport = self.provider(value)
        result = provider.propose_grounded(self.observation(), state_version=0)
        self.assertEqual(result, [])
        self.assertEqual(len(transport.calls), 1)


class CloudProviderCsdIntegrationTests(unittest.TestCase):
    def test_cloud_provider_only_creates_pending_proposal_until_csd_evaluates(self):
        with tempfile.TemporaryDirectory() as directory:
            store = CognitiveMemoryStore(Path(directory) / "cloud-provider.sqlite3")
            try:
                source_text = "A silver leaf rested on the windowsill. 🍃"
                store.submit_event(CognitiveEvent(
                    event_id="evt-cloud-provider-integration",
                    occurred_at="2026-11-19T10:00:00+00:00",
                    correlation_id="corr-cloud-provider-integration",
                    event_type=OBSERVATION_EVENT,
                    source="test.synthetic_observation",
                    payload={
                        "observation_id": "obs-cloud-provider-integration",
                        "observation_kind": "text_fixture",
                        "content": source_text,
                        "source_ref": "fixture://cloud-provider/integration",
                        "observed_at": "2026-11-19T09:59:00+00:00",
                        "coverage": {"modality": "text", "complete_for_fixture": True},
                    },
                ))
                candidate = {
                    "proposal_id": "cloud-provider-integration-proposal",
                    "memory_kind": "episodic_candidate",
                    "source_assertions": [{
                        "claim_id": "source-1",
                        "text": source_text,
                        "quoted_text": source_text,
                        "start": 0,
                        "end": len(source_text),
                    }],
                    "inferences": [],
                }
                transport = FakeTransport(candidate)
                provider = OpenAICompatibleGroundedMemoryProvider(
                    model="test-model",
                    base_url="https://example.invalid/v1",
                    api_key="test-only",
                    transport=transport,
                )
                submitted = GroundedMemoryProposalPipeline(store, provider).propose_from_observation(
                    "evt-cloud-provider-integration"
                )
                self.assertEqual(submitted[0]["status"], "accepted")
                self.assertEqual(store.get_proposal("cloud-provider-integration-proposal")["status"], "pending")
                self.assertEqual(store.get_memories(), [])

                decision = store.evaluate_proposal("cloud-provider-integration-proposal")
                self.assertEqual(decision["status"], "accepted")
                memories = store.get_memories()
                self.assertEqual(len(memories), 1)
                self.assertEqual(
                    memories[0]["evidence_event_ids"],
                    ["evt-cloud-provider-integration"],
                )
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
