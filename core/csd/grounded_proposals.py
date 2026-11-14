"""Provider-neutral pipeline for grounded text-evidence memory proposals.

The provider supplies claim candidates and text offsets only. The pipeline binds
all source evidence to the observation event it was asked to analyze, adds
provider/state provenance, and submits a pending v2 event. CSD alone evaluates
and accepts the proposal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
import uuid

from .cognitive import (
    GROUNDED_PROPOSAL_EVENT,
    OBSERVATION_EVENT,
    CognitiveEvent,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
)


@dataclass(frozen=True)
class GroundedSourceAssertion:
    claim_id: str
    text: str
    quoted_text: str
    start: int
    end: int


@dataclass(frozen=True)
class GroundedInference:
    claim_id: str
    text: str
    derived_from_claim_ids: Sequence[str]
    reasoning_summary: str
    uncertainty_label: str = "tentative_inference"
    confidence: float | None = None


@dataclass(frozen=True)
class GroundedMemoryCandidate:
    proposal_id: str
    memory_kind: str
    source_assertions: Sequence[GroundedSourceAssertion]
    inferences: Sequence[GroundedInference] = ()


class GroundedMemoryProposalProvider(Protocol):
    """Replaceable model/service contract for grounded claim candidates."""

    provider_id: str
    provider_version: str

    def propose_grounded(
        self,
        observation: Mapping[str, Any],
        *,
        state_version: int,
    ) -> Sequence[GroundedMemoryCandidate]:
        """Return candidate claims and source-text offsets; do not mutate CSD."""


class GroundedMemoryProposalPipeline:
    """Builds v2 pending proposals; it never evaluates or accepts them."""

    def __init__(
        self,
        store: CognitiveMemoryStore,
        provider: GroundedMemoryProposalProvider,
    ) -> None:
        self.store = store
        self.provider = provider
        if not isinstance(provider.provider_id, str) or not provider.provider_id.strip():
            raise ValueError("provider_id must be a non-empty string")
        if not isinstance(provider.provider_version, str) or not provider.provider_version.strip():
            raise ValueError("provider_version must be a non-empty string")
        if not callable(getattr(provider, "propose_grounded", None)):
            raise TypeError("provider must implement propose_grounded")

    @staticmethod
    def _candidate_payload(
        candidate: GroundedMemoryCandidate,
        *,
        observation_event_id: str,
        provider_id: str,
        provider_version: str,
        state_version: int,
    ) -> dict[str, Any]:
        if not isinstance(candidate, GroundedMemoryCandidate):
            raise TypeError("provider must return GroundedMemoryCandidate values")
        for name, value in (
            ("proposal_id", candidate.proposal_id),
            ("memory_kind", candidate.memory_kind),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(candidate.source_assertions, Sequence) or not candidate.source_assertions:
            raise ValueError("candidate must contain at least one source assertion")

        claims: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for assertion in candidate.source_assertions:
            if not isinstance(assertion, GroundedSourceAssertion):
                raise TypeError("source_assertions must contain GroundedSourceAssertion values")
            for name, value in (
                ("claim_id", assertion.claim_id),
                ("text", assertion.text),
                ("quoted_text", assertion.quoted_text),
            ):
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"source assertion {name} must be non-empty")
            if assertion.claim_id in seen_ids:
                raise ValueError(f"duplicate claim_id: {assertion.claim_id}")
            seen_ids.add(assertion.claim_id)
            for name, value in (("start", assertion.start), ("end", assertion.end)):
                if not isinstance(value, int) or isinstance(value, bool):
                    raise ValueError(f"source assertion {name} must be an integer")
            claims.append({
                "claim_id": assertion.claim_id,
                "text": assertion.text,
                "epistemic_type": "source_assertion",
                "evidence": [{
                    "event_id": observation_event_id,
                    "locator": {
                        "kind": "text_range",
                        "unit": "unicode_codepoint",
                        "start": assertion.start,
                        "end": assertion.end,
                    },
                    "quoted_text": assertion.quoted_text,
                }],
                "uncertainty": {"label": "directly_quoted", "confidence": None},
            })

        for inference in candidate.inferences:
            if not isinstance(inference, GroundedInference):
                raise TypeError("inferences must contain GroundedInference values")
            for name, value in (
                ("claim_id", inference.claim_id),
                ("text", inference.text),
                ("reasoning_summary", inference.reasoning_summary),
                ("uncertainty_label", inference.uncertainty_label),
            ):
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"inference {name} must be non-empty")
            if inference.claim_id in seen_ids:
                raise ValueError(f"duplicate claim_id: {inference.claim_id}")
            seen_ids.add(inference.claim_id)
            if not isinstance(inference.derived_from_claim_ids, Sequence) or isinstance(
                inference.derived_from_claim_ids, (str, bytes)
            ):
                raise TypeError("derived_from_claim_ids must be a sequence of claim IDs")
            if inference.confidence is not None and (
                not isinstance(inference.confidence, (int, float))
                or isinstance(inference.confidence, bool)
                or not 0.0 <= float(inference.confidence) <= 1.0
            ):
                raise ValueError("inference confidence must be null or between 0 and 1")
            claims.append({
                "claim_id": inference.claim_id,
                "text": inference.text,
                "epistemic_type": "inference",
                "derived_from_claim_ids": list(inference.derived_from_claim_ids),
                "reasoning_summary": inference.reasoning_summary,
                "uncertainty": {
                    "label": inference.uncertainty_label,
                    "confidence": inference.confidence,
                },
            })

        return {
            "proposal_id": candidate.proposal_id,
            "memory_kind": candidate.memory_kind,
            "claims": claims,
            "origin": {"component": provider_id, "version": provider_version},
            "based_on": {"state_version": state_version},
            "operation": "create",
        }

    def propose_from_observation(self, observation_event_id: str) -> list[dict[str, Any]]:
        """Call provider outside transactions and persist at most one pending v2 proposal."""
        observation = self.store.get_event(observation_event_id)
        if observation["event_type"] != OBSERVATION_EVENT:
            raise ValueError("grounded proposal generation requires an observation event")
        coverage = observation["payload"].get("coverage")
        if not isinstance(coverage, Mapping) or coverage.get("modality") != "text":
            raise ValueError("grounded memory v2 provider requires a text observation")

        state = self.store.get_state_snapshot()
        if not state["projection_consistent"]:
            raise CognitiveIntegrityError(
                "accepted-memory projection is out of sync; run Recovery before proposal generation"
            )
        state_version = int(state["state_version"])

        candidates = self.provider.propose_grounded(
            observation,
            state_version=state_version,
        )
        if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
            raise TypeError("provider must return a sequence of GroundedMemoryCandidate values")
        if len(candidates) > 1:
            raise ValueError("grounded v2 pipeline currently accepts at most one candidate per call")
        if not candidates:
            return []

        payload = self._candidate_payload(
            candidates[0],
            observation_event_id=observation_event_id,
            provider_id=self.provider.provider_id,
            provider_version=self.provider.provider_version,
            state_version=state_version,
        )
        # Validate schema before appending; source-span truth is checked later
        # by CSD's evaluator, which preserves invalid candidates as rejected events.
        self.store._validate_grounded_proposal(payload)
        event = CognitiveEvent(
            event_id=f"evt-grounded-proposal-{uuid.uuid4()}",
            occurred_at=datetime.now(timezone.utc).isoformat(),
            correlation_id=observation["correlation_id"],
            event_type=GROUNDED_PROPOSAL_EVENT,
            source=f"cognition.grounded-proposal-pipeline:{self.provider.provider_id}",
            payload=payload,
        )
        return [self.store.submit_event(event)]
