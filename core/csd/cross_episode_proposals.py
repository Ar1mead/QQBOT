"""Typed cross-episode candidates with CSD-owned pending-only persistence.

This module validates model-authored synthesis against accepted-claim
references. Persistence creates immutable pending-shadow events only; it does
not accept preferences, mutate self-model state, rank activities, or access ASM.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .accepted_claim_references import (
    AcceptedClaimReferenceError,
    resolve_accepted_claim_reference,
    resolve_selected_accepted_claims,
)
from .cognitive import (
    CROSS_EPISODE_PROPOSAL_EVENT,
    CognitiveEvent,
    CognitiveMemoryStore,
)


SCHEMA_VERSION = 1
MAX_TEXT = 2000
MAX_REFERENCES = 32
MAX_LIST_ITEMS = 8
USER_PREFERENCE_DOMAINS = frozenset({
    "communication_style", "creative_preferences", "dining_environment",
    "environment_preferences", "interaction_preferences", "media_preferences",
    "workflow_preferences",
})
AI_INTEREST_DOMAINS = frozenset({
    "creative_topics", "learning_topics", "research_topics", "technical_topics",
})


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
    schema_version = model_payload.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != SCHEMA_VERSION
    ):
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
    if not isinstance(kind, str) or kind not in {"preference_candidate", "interest_candidate"}:
        raise CrossEpisodeProposalError("candidate_kind is not supported in v1")
    expected_owner = "user" if kind == "preference_candidate" else "ai"
    if owner != expected_owner:
        raise CrossEpisodeProposalError("candidate owner does not match candidate kind")
    domain = _text(model_payload.get("domain"), "domain")
    allowed_domains = (
        USER_PREFERENCE_DOMAINS if kind == "preference_candidate"
        else AI_INTEREST_DOMAINS
    )
    if domain not in allowed_domains:
        raise CrossEpisodeProposalError(
            "candidate domain is not an allowed non-sensitive domain for its owner"
        )
    confidence = model_payload.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise CrossEpisodeProposalError("confidence must be a finite number from 0 to 1")
    try:
        confidence_value = float(confidence)
    except (OverflowError, ValueError) as exc:
        raise CrossEpisodeProposalError("confidence must be a finite number from 0 to 1") from exc
    if not math.isfinite(confidence_value) or not 0.0 <= confidence_value <= 1.0:
        raise CrossEpisodeProposalError("confidence must be a finite number from 0 to 1")
    uncertainty = model_payload.get("uncertainty")
    if not isinstance(uncertainty, str) or uncertainty not in {"low", "moderate", "high"}:
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
        domain=domain,
        statement=_text(model_payload.get("statement"), "statement"),
        scope=_text(model_payload.get("scope"), "scope"),
        exclusions=_text_list(model_payload.get("exclusions"), "exclusions"),
        confidence=confidence_value,
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


_PERSISTED_REFERENCE_FIELDS = (
    "memory_id", "proposal_id", "decision_event_id", "proposal_event_id",
    "claim_id", "claim_digest", "source_event_ids", "status",
    "based_on_state_version",
)


def _persisted_reference(reference: Mapping[str, Any]) -> dict[str, Any]:
    """Drop copied claim text; persist only canonical lineage and its digest."""
    return {
        "memory_id": reference["memory_id"],
        "proposal_id": reference["proposal_id"],
        "decision_event_id": reference["decision_event_id"],
        "proposal_event_id": reference["proposal_event_id"],
        "claim_id": reference["claim_id"],
        "claim_digest": reference["claim_digest"],
        "source_event_ids": list(reference["source_event_ids"]),
        "status": reference["status"],
        "based_on_state_version": reference["based_on_state_version"],
    }


def _proposal_event_payload(proposal: CrossEpisodeProposal) -> dict[str, Any]:
    candidate = proposal.candidate
    return {
        "proposal_id": proposal.proposal_id,
        "schema_version": proposal.schema_version,
        "provider_id": proposal.provider_id,
        "provider_version": proposal.provider_version,
        "based_on_state_version": proposal.based_on_state_version,
        "candidate": {
            "candidate_kind": candidate.candidate_kind,
            "owner": candidate.owner,
            "domain": candidate.domain,
            "statement": candidate.statement,
            "scope": candidate.scope,
            "exclusions": list(candidate.exclusions),
            "confidence": candidate.confidence,
            "uncertainty": candidate.uncertainty,
            "reasoning_summary": candidate.reasoning_summary,
            "alternatives": list(candidate.alternatives),
            "limitations": list(candidate.limitations),
            "supporting_references": [
                _persisted_reference(item) for item in candidate.supporting_references
            ],
            "counter_evidence_references": [
                _persisted_reference(item) for item in candidate.counter_evidence_references
            ],
            "independent_support_event_count": candidate.independent_support_event_count,
        },
    }


def append_cross_episode_proposal(
    store: CognitiveMemoryStore,
    proposal: CrossEpisodeProposal,
    *,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    """Persist a pending-only candidate; CSD revalidates every reference in-transaction."""
    if not isinstance(proposal, CrossEpisodeProposal):
        raise TypeError("proposal must be a CrossEpisodeProposal")
    if proposal.status != "pending_shadow" or proposal.candidate.status != "shadow":
        raise CrossEpisodeProposalError("only pending shadow proposals may be persisted")
    proposal_id = _text(proposal.proposal_id, "proposal_id")
    provider_id = _text(proposal.provider_id, "provider_id")
    timestamp = occurred_at or datetime.now(timezone.utc).isoformat()
    event = CognitiveEvent(
        event_id=f"csd-cross-episode-proposal:{proposal_id}",
        occurred_at=timestamp,
        correlation_id=f"cross-episode-proposal:{proposal_id}",
        event_type=CROSS_EPISODE_PROPOSAL_EVENT,
        source=f"cross-episode.pipeline:{provider_id}",
        payload=_proposal_event_payload(proposal),
    )
    return store.submit_event(event)


def validate_cross_episode_proposal_event(
    store: CognitiveMemoryStore,
    event: CognitiveEvent,
    *,
    sequence: int,
) -> None:
    """Validate a pending event against the exact CSD history before its sequence."""
    payload = event.payload
    allowed_payload = {
        "proposal_id", "schema_version", "provider_id", "provider_version",
        "based_on_state_version", "candidate",
    }
    if not isinstance(payload, Mapping) or set(payload) != allowed_payload:
        raise ValueError("cross-episode event contains missing or unsupported fields")
    proposal_id = _text(payload.get("proposal_id"), "proposal_id")
    provider_id = _text(payload.get("provider_id"), "provider_id")
    provider_version = _text(payload.get("provider_version"), "provider_version")
    if (
        payload.get("proposal_id") != proposal_id
        or payload.get("provider_id") != provider_id
        or payload.get("provider_version") != provider_version
    ):
        raise ValueError("cross-episode identity fields must be canonical text")
    schema_version = payload.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != SCHEMA_VERSION
    ):
        raise ValueError("unsupported cross-episode event schema version")
    state_version = payload.get("based_on_state_version")
    if (
        not isinstance(state_version, int)
        or isinstance(state_version, bool)
        or state_version < 0
    ):
        raise ValueError("based_on_state_version must be a non-negative integer")
    if (
        event.event_id != f"csd-cross-episode-proposal:{proposal_id}"
        or event.correlation_id != f"cross-episode-proposal:{proposal_id}"
        or event.source != f"cross-episode.pipeline:{provider_id}"
    ):
        raise ValueError("cross-episode event identity/source mismatch")

    candidate = payload.get("candidate")
    candidate_fields = {
        "candidate_kind", "owner", "domain", "statement", "scope", "exclusions",
        "confidence", "uncertainty", "reasoning_summary", "alternatives",
        "limitations", "supporting_references", "counter_evidence_references",
        "independent_support_event_count",
    }
    if not isinstance(candidate, Mapping) or set(candidate) != candidate_fields:
        raise ValueError("cross-episode candidate contains missing or unsupported fields")
    kind = candidate.get("candidate_kind")
    owner = candidate.get("owner")
    if not isinstance(kind, str) or kind not in {
        "preference_candidate", "interest_candidate"
    }:
        raise ValueError("cross-episode candidate kind is unsupported")
    if owner != ("user" if kind == "preference_candidate" else "ai"):
        raise ValueError("cross-episode candidate owner does not match its kind")
    domain = _text(candidate.get("domain"), "candidate.domain")
    if candidate.get("domain") != domain:
        raise ValueError("candidate.domain must be canonical text")
    allowed_domains = (
        USER_PREFERENCE_DOMAINS if kind == "preference_candidate"
        else AI_INTEREST_DOMAINS
    )
    if domain not in allowed_domains:
        raise ValueError("cross-episode candidate domain is not allowed for its owner")
    for field in ("statement", "scope", "reasoning_summary"):
        value = candidate.get(field)
        if _text(value, f"candidate.{field}") != value:
            raise ValueError(f"candidate.{field} must be canonical text")
    for field in ("exclusions", "alternatives", "limitations"):
        value = candidate.get(field)
        if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
            raise ValueError(f"candidate.{field} must be a bounded list")
        normalized = [_text(item, f"candidate.{field}") for item in value]
        if normalized != value:
            raise ValueError(f"candidate.{field} must contain canonical text")
        if len(set(normalized)) != len(normalized):
            raise ValueError(f"candidate.{field} must not contain duplicates")
    confidence = candidate.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        raise ValueError("candidate confidence must be finite and between 0 and 1")
    try:
        confidence_value = float(confidence)
    except (OverflowError, ValueError) as exc:
        raise ValueError("candidate confidence must be finite and between 0 and 1") from exc
    if not math.isfinite(confidence_value) or not 0.0 <= confidence_value <= 1.0:
        raise ValueError("candidate confidence must be finite and between 0 and 1")
    uncertainty = candidate.get("uncertainty")
    if not isinstance(uncertainty, str) or uncertainty not in {"low", "moderate", "high"}:
        raise ValueError("candidate uncertainty is unsupported")

    supports = candidate.get("supporting_references")
    counters = candidate.get("counter_evidence_references")
    if not isinstance(supports, list) or not 1 <= len(supports) <= MAX_REFERENCES:
        raise ValueError("supporting references must contain 1 to 32 items")
    if not isinstance(counters, list) or len(counters) > MAX_REFERENCES:
        raise ValueError("counter-evidence references must be a bounded list")
    if len(supports) + len(counters) > 64:
        raise ValueError("cross-episode event exceeds the total reference limit")

    resolved_by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    def validate_bundle(items: list[Any]) -> list[dict[str, Any]]:
        validated: list[dict[str, Any]] = []
        for item in items:
            if not isinstance(item, Mapping) or set(item) != set(_PERSISTED_REFERENCE_FIELDS):
                raise ValueError("persisted historical reference has an invalid schema")
            memory_id = _text(item.get("memory_id"), "reference.memory_id")
            claim_id = _text(item.get("claim_id"), "reference.claim_id")
            identity = (memory_id, claim_id)
            if identity in resolved_by_identity:
                raise ValueError("cross-episode event repeats a historical claim reference")
            if item.get("status") != "accepted":
                raise ValueError("cross-episode references must identify accepted memories")
            reference_version = item.get("based_on_state_version")
            if (
                not isinstance(reference_version, int)
                or isinstance(reference_version, bool)
                or reference_version != state_version
            ):
                raise ValueError("historical reference state version does not match proposal")
            source_ids = item.get("source_event_ids")
            if (
                not isinstance(source_ids, list)
                or not source_ids
                or len(source_ids) > MAX_REFERENCES
                or any(not isinstance(value, str) or not value.strip() for value in source_ids)
                or len(set(source_ids)) != len(source_ids)
            ):
                raise ValueError("historical reference source event IDs are invalid")
            digest = item.get("claim_digest")
            if (
                not isinstance(digest, str)
                or not digest.startswith("sha256:")
                or len(digest) != 71
            ):
                raise ValueError("historical reference claim digest is invalid")
            resolved = resolve_accepted_claim_reference(
                store,
                memory_id=memory_id,
                claim_id=claim_id,
                expected_state_version=state_version,
                through_sequence=sequence,
            )
            canonical = _persisted_reference(resolved)
            if dict(item) != canonical:
                raise ValueError("historical reference lineage or claim digest is stale/tampered")
            resolved_by_identity[identity] = canonical
            validated.append(canonical)
        return validated

    validated_supports = validate_bundle(supports)
    validated_counters = validate_bundle(counters)
    support_identities = {(item["memory_id"], item["claim_id"]) for item in validated_supports}
    counter_identities = {(item["memory_id"], item["claim_id"]) for item in validated_counters}
    if support_identities & counter_identities:
        raise ValueError("a historical claim cannot be both support and counter-evidence")
    independent_events = {
        event_id
        for reference in validated_supports
        for event_id in reference["source_event_ids"]
    }
    declared_count = candidate.get("independent_support_event_count")
    if (
        not isinstance(declared_count, int)
        or isinstance(declared_count, bool)
        or declared_count != len(independent_events)
    ):
        raise ValueError("independent support event count does not match validated evidence")


def list_cross_episode_proposals(
    store: CognitiveMemoryStore,
) -> list[dict[str, Any]]:
    """Read pending-only cross-episode proposals from the immutable event log."""
    def read_all() -> list[dict[str, Any]]:
        rows = store._db.execute(
            "SELECT event_id FROM events WHERE event_type=? ORDER BY sequence",
            (CROSS_EPISODE_PROPOSAL_EVENT,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            event = store.get_event(row["event_id"])
            result.append({
                "sequence": event["sequence"],
                "event_id": event["event_id"],
                "proposal_id": event["payload"]["proposal_id"],
                "status": "pending_shadow",
                "payload": event["payload"],
            })
        return result
    if store._db.in_transaction:
        return read_all()
    with store._read_tx():
        return read_all()
