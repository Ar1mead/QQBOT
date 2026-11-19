"""Typed, shadow-only cross-episode interpretation candidates.

This module validates model-authored synthesis against pipeline-resolved
accepted-claim references. It deliberately has no persistence, CSD mutation,
preference reducer, Life Engine, or ASM access.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .accepted_claim_references import (
    AcceptedClaimReferenceError,
    resolve_selected_accepted_claims,
)
from .cognitive import CognitiveMemoryStore


SCHEMA_VERSION = 1
MAX_TEXT = 2000
MAX_REFERENCES = 32
MAX_LIST_ITEMS = 8


class CrossEpisodeProposalError(ValueError):
    """A cross-episode interpretation candidate is malformed or ungrounded."""


@dataclass(frozen=True)
class CrossEpisodeInterpretationCandidate:
    candidate_kind: str
    owner: str
    domain: str
    statement: str
    scope: str
    exclusions: tuple[str, ...]
    confidence: float
    uncertainty: str
    reasoning_summary: str
    alternatives: tuple[str, ...]
    limitations: tuple[str, ...]
    supporting_references: tuple[Mapping[str, Any], ...]
    counter_evidence_references: tuple[Mapping[str, Any], ...]
    independent_support_event_count: int
    based_on_state_version: int
    status: str = "shadow"


@dataclass(frozen=True)
class CrossEpisodeProposal:
    proposal_id: str
    schema_version: int
    provider_id: str
    provider_version: str
    based_on_state_version: int
    candidate: CrossEpisodeInterpretationCandidate
    status: str = "pending_shadow"


def _text(value: Any, field: str, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise CrossEpisodeProposalError(f"{field} must be text")
    value = value.strip()
    if required and not value:
        raise CrossEpisodeProposalError(f"{field} must not be empty")
    if len(value) > MAX_TEXT:
        raise CrossEpisodeProposalError(f"{field} exceeds the text limit")
    return value


def _text_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
        raise CrossEpisodeProposalError(f"{field} must be a bounded list")
    items = tuple(_text(item, field) for item in value)
    if len(set(items)) != len(items):
        raise CrossEpisodeProposalError(f"{field} must not contain duplicates")
    return items


def _keys(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or len(value) > MAX_REFERENCES:
        raise CrossEpisodeProposalError(f"{field} must contain 1 to {MAX_REFERENCES} keys")
    keys = tuple(_text(item, field) for item in value)
    if len(set(keys)) != len(keys):
        raise CrossEpisodeProposalError(f"{field} contains duplicate keys")
    return keys


def build_cross_episode_proposal(
    store: CognitiveMemoryStore,
    model_payload: Mapping[str, Any],
    reference_context: Mapping[str, Mapping[str, Any]],
    *,
    proposal_id: str,
    provider_id: str,
    provider_version: str,
    expected_state_version: int,
) -> CrossEpisodeProposal:
    """Validate a model's opaque-key synthesis into a non-persistent shadow proposal."""
    if not isinstance(model_payload, Mapping):
        raise CrossEpisodeProposalError("model payload must be an object")
    allowed = {
        "schema_version", "based_on_state_version", "candidate_kind", "owner",
        "domain", "statement", "scope", "exclusions", "confidence",
        "uncertainty", "reasoning_summary", "alternatives", "limitations",
        "support_reference_keys", "counter_evidence_reference_keys",
    }
    if set(model_payload) != allowed:
        raise CrossEpisodeProposalError("model payload contains missing or unsupported fields")
    if model_payload.get("schema_version") != SCHEMA_VERSION:
        raise CrossEpisodeProposalError("unsupported cross-episode schema version")
    supplied_version = model_payload.get("based_on_state_version")
    if (
        not isinstance(supplied_version, int)
        or isinstance(supplied_version, bool)
        or supplied_version != expected_state_version
    ):
        raise CrossEpisodeProposalError("model payload state version does not match pipeline snapshot")
    if (
        not isinstance(expected_state_version, int)
        or isinstance(expected_state_version, bool)
        or expected_state_version < 0
    ):
        raise CrossEpisodeProposalError("expected_state_version must be non-negative")
    kind = model_payload.get("candidate_kind")
    owner = model_payload.get("owner")
    if kind not in {"preference_candidate", "interest_candidate"}:
        raise CrossEpisodeProposalError("candidate_kind is not supported in v1")
    expected_owner = "user" if kind == "preference_candidate" else "ai"
    if owner != expected_owner:
        raise CrossEpisodeProposalError("candidate owner does not match candidate kind")
    confidence = model_payload.get("confidence")
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(float(confidence))
        or not 0.0 <= float(confidence) <= 1.0
    ):
        raise CrossEpisodeProposalError("confidence must be a finite number from 0 to 1")
    uncertainty = model_payload.get("uncertainty")
    if uncertainty not in {"low", "moderate", "high"}:
        raise CrossEpisodeProposalError("uncertainty must be low, moderate, or high")

    support_keys = _keys(model_payload.get("support_reference_keys"), "support_reference_keys")
    counter_keys = model_payload.get("counter_evidence_reference_keys")
    if not isinstance(counter_keys, list) or len(counter_keys) > MAX_REFERENCES:
        raise CrossEpisodeProposalError("counter_evidence_reference_keys must be a bounded list")
    counter_keys = tuple(_text(item, "counter_evidence_reference_keys") for item in counter_keys)
    if len(set(counter_keys)) != len(counter_keys):
        raise CrossEpisodeProposalError("counter-evidence keys must not contain duplicates")
    if set(support_keys) & set(counter_keys):
        raise CrossEpisodeProposalError("a reference cannot be both support and counter-evidence")

    selected_keys = (*support_keys, *counter_keys)
    try:
        resolved = resolve_selected_accepted_claims(
            store,
            reference_context,
            selected_keys,
            expected_state_version=expected_state_version,
        )
    except (AcceptedClaimReferenceError, KeyError, TypeError, ValueError) as exc:
        raise CrossEpisodeProposalError(f"historical reference validation failed: {exc}") from exc
    if len(resolved) != len(set(selected_keys)):
        raise CrossEpisodeProposalError("historical reference selection was not fully resolved")

    supporting = tuple(resolved[key] for key in support_keys)
    counter = tuple(resolved[key] for key in counter_keys)
    independent_support_events = {
        event_id
        for reference in supporting
        for event_id in reference["source_event_ids"]
    }
    if not independent_support_events:
        raise CrossEpisodeProposalError("supporting references contain no source events")

    candidate = CrossEpisodeInterpretationCandidate(
        candidate_kind=kind,
        owner=owner,
        domain=_text(model_payload.get("domain"), "domain"),
        statement=_text(model_payload.get("statement"), "statement"),
        scope=_text(model_payload.get("scope"), "scope"),
        exclusions=_text_list(model_payload.get("exclusions"), "exclusions"),
        confidence=float(confidence),
        uncertainty=uncertainty,
        reasoning_summary=_text(model_payload.get("reasoning_summary"), "reasoning_summary"),
        alternatives=_text_list(model_payload.get("alternatives"), "alternatives"),
        limitations=_text_list(model_payload.get("limitations"), "limitations"),
        supporting_references=supporting,
        counter_evidence_references=counter,
        independent_support_event_count=len(independent_support_events),
        based_on_state_version=expected_state_version,
    )
    return CrossEpisodeProposal(
        proposal_id=_text(proposal_id, "proposal_id"),
        schema_version=SCHEMA_VERSION,
        provider_id=_text(provider_id, "provider_id"),
        provider_version=_text(provider_version, "provider_version"),
        based_on_state_version=expected_state_version,
        candidate=candidate,
    )
