"""Provider-neutral generation of untrusted cognitive memory proposals.

Providers may use an LLM or another analysis engine, but their output is only
candidate data. This pipeline never evaluates or commits accepted memory state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
import uuid

from .cognitive import (
    OBSERVATION_EVENT,
    CognitiveEvent,
    CognitiveMemoryStore,
)


@dataclass(frozen=True)
class MemoryCandidate:
    """Untrusted candidate returned by a cognitive analysis provider."""

    proposal_id: str
    memory_kind: str
    candidate_content: str
    uncertainty_label: str
    confidence: float | None = None


class MemoryProposalProvider(Protocol):
    """Replaceable provider contract; implementation may call a model API."""

    provider_id: str
    provider_version: str

    def propose(
        self,
        observation: Mapping[str, Any],
        *,
        state_version: int,
    ) -> Sequence[MemoryCandidate]:
        """Return zero or more candidate memories; never mutate CSD state."""


class MemoryProposalPipeline:
    """Turns provider output into candidate events without accepting memory."""

    def __init__(
        self,
        store: CognitiveMemoryStore,
        provider: MemoryProposalProvider,
    ) -> None:
        self.store = store
        self.provider = provider
        if not isinstance(provider.provider_id, str) or not provider.provider_id.strip():
            raise ValueError("provider_id must be a non-empty string")
        if not isinstance(provider.provider_version, str) or not provider.provider_version.strip():
            raise ValueError("provider_version must be a non-empty string")

    def propose_from_observation(self, observation_event_id: str) -> list[dict[str, Any]]:
        """Generate and persist candidates; deliberately does not evaluate them."""
        observation_event = self.store.get_event(observation_event_id)
        if observation_event["event_type"] != OBSERVATION_EVENT:
            raise ValueError("proposal generation requires an observation event")

        state_version = int(self.store.get_state_snapshot()["state_version"])
        candidates = self.provider.propose(
            observation_event,
            state_version=state_version,
        )
        if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
            raise TypeError("provider must return a sequence of MemoryCandidate values")

        results: list[dict[str, Any]] = []
        seen_proposal_ids: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, MemoryCandidate):
                raise TypeError("provider returned a value that is not MemoryCandidate")
            for field_name, value in (
                ("proposal_id", candidate.proposal_id),
                ("memory_kind", candidate.memory_kind),
                ("candidate_content", candidate.candidate_content),
                ("uncertainty_label", candidate.uncertainty_label),
            ):
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{field_name} must be a non-empty string")
            if candidate.proposal_id in seen_proposal_ids:
                raise ValueError("provider returned duplicate proposal IDs in one batch")
            seen_proposal_ids.add(candidate.proposal_id)
            if candidate.confidence is not None and (
                not isinstance(candidate.confidence, (int, float))
                or isinstance(candidate.confidence, bool)
                or not 0.0 <= float(candidate.confidence) <= 1.0
            ):
                raise ValueError("confidence must be null or between 0 and 1")

            event = CognitiveEvent(
                event_id=f"evt-proposal-{uuid.uuid4()}",
                occurred_at=datetime.now(timezone.utc).isoformat(),
                correlation_id=observation_event["correlation_id"],
                event_type="cognition.memory_candidate_proposed.v1",
                source=f"cognition.proposal_pipeline:{self.provider.provider_id}",
                payload={
                    "proposal_id": candidate.proposal_id,
                    "memory_kind": candidate.memory_kind,
                    "candidate_content": candidate.candidate_content,
                    "evidence_event_ids": [observation_event_id],
                    "origin": {
                        "component": self.provider.provider_id,
                        "version": self.provider.provider_version,
                    },
                    "uncertainty": {
                        "label": candidate.uncertainty_label,
                        "confidence": candidate.confidence,
                    },
                    "based_on": {"state_version": state_version},
                    "operation": "create",
                },
            )
            results.append(self.store.submit_event(event))

        return results
