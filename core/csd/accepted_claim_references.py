"""Resolve immutable references to claims in CSD-accepted memories.

This is a read-only resolver. It does not append proposals, revise preferences,
or dispatch activities. Cross-episode candidates remain pending/shadow until
CSD append/decision-time revalidation and preference reducers are implemented.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .cognitive import (
    DECISION_EVENT,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
)


class AcceptedClaimReferenceError(ValueError):
    """A historical claim cannot be safely referenced."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def _claim_digest(claim: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical(claim).encode("utf-8")).hexdigest()


def resolve_accepted_claim_reference(
    store: CognitiveMemoryStore,
    *,
    memory_id: str,
    claim_id: str,
    expected_state_version: int,
) -> dict[str, Any]:
    """Resolve one source-assertion claim against the accepted CSD event history."""
    if not isinstance(memory_id, str) or not memory_id.strip():
        raise AcceptedClaimReferenceError("memory_id must be non-empty text")
    if not isinstance(claim_id, str) or not claim_id.strip():
        raise AcceptedClaimReferenceError("claim_id must be non-empty text")
    if (
        not isinstance(expected_state_version, int)
        or isinstance(expected_state_version, bool)
        or expected_state_version < 0
    ):
        raise AcceptedClaimReferenceError("expected_state_version must be non-negative")

    before = store.get_state_snapshot()["state_version"]
    if before != expected_state_version:
        raise AcceptedClaimReferenceError("accepted-claim reference snapshot is stale")
    try:
        memory = store.get_memory(memory_id)
    except KeyError as exc:
        raise AcceptedClaimReferenceError("accepted memory is unavailable") from exc
    if memory.get("status") != "accepted":
        raise AcceptedClaimReferenceError("only accepted memories may be referenced")

    proposal_id = memory.get("proposal_id")
    decision_event_id = memory.get("decision_event_id")
    proposal_event_id = memory.get("proposal_event_id")
    if not all(isinstance(item, str) and item for item in (
        proposal_id, decision_event_id, proposal_event_id
    )):
        raise AcceptedClaimReferenceError("accepted memory lineage is incomplete")

    try:
        proposal = store.get_proposal(proposal_id)
        decision = store.get_event(decision_event_id)
    except (KeyError, CognitiveIntegrityError) as exc:
        raise AcceptedClaimReferenceError("accepted memory lineage is inconsistent") from exc
    if (
        proposal["status"] != "accepted"
        or proposal["decision_event_id"] != decision_event_id
        or proposal["proposal_event_id"] != proposal_event_id
        or decision["event_type"] != DECISION_EVENT
        or decision["payload"].get("outcome") != "accepted"
        or decision["payload"].get("proposal_id") != proposal_id
        or decision["payload"].get("proposal_event_id") != proposal_event_id
        or decision["payload"].get("memory_id") != memory_id
    ):
        raise AcceptedClaimReferenceError("memory, proposal and accepted decision do not match")

    claims = memory.get("claims")
    if not isinstance(claims, list):
        raise AcceptedClaimReferenceError("memory has no grounded claim projection")
    matches = [
        claim for claim in claims
        if isinstance(claim, Mapping) and claim.get("claim_id") == claim_id
    ]
    if len(matches) != 1:
        raise AcceptedClaimReferenceError("claim is missing or ambiguous in accepted memory")
    claim = matches[0]
    if claim.get("epistemic_type") != "source_assertion":
        raise AcceptedClaimReferenceError("v1 historical references require source_assertion claims")
    evidence = claim.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise AcceptedClaimReferenceError("source assertion has no evidence lineage")
    source_event_ids: list[str] = []
    for item in evidence:
        if not isinstance(item, Mapping):
            raise AcceptedClaimReferenceError("claim evidence is malformed")
        event_id = item.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise AcceptedClaimReferenceError("claim evidence event ID is invalid")
        if event_id not in source_event_ids:
            source_event_ids.append(event_id)

    after = store.get_state_snapshot()["state_version"]
    if after != before or after != expected_state_version:
        raise AcceptedClaimReferenceError("CSD state changed while resolving accepted claim")

    return {
        "memory_id": memory_id,
        "proposal_id": proposal_id,
        "decision_event_id": decision_event_id,
        "proposal_event_id": proposal_event_id,
        "claim_id": claim_id,
        "claim_digest": _claim_digest(claim),
        "source_event_ids": source_event_ids,
        "claim": dict(claim),
        "status": "accepted",
        "based_on_state_version": expected_state_version,
    }


def resolve_selected_accepted_claims(
    store: CognitiveMemoryStore,
    references: Sequence[Mapping[str, str]],
    *,
    expected_state_version: int,
) -> dict[str, dict[str, Any]]:
    """Resolve only explicitly selected memory/claim pairs into opaque reference keys."""
    if not isinstance(references, Sequence) or isinstance(references, (str, bytes)):
        raise TypeError("references must be a sequence")
    if len(references) > 64:
        raise AcceptedClaimReferenceError("at most 64 historical claims may be resolved")
    resolved: dict[str, dict[str, Any]] = {}
    identities: set[tuple[str, str]] = set()
    for index, reference in enumerate(references, start=1):
        if not isinstance(reference, Mapping) or set(reference) != {"memory_id", "claim_id"}:
            raise AcceptedClaimReferenceError("each reference must contain only memory_id and claim_id")
        identity = (reference["memory_id"], reference["claim_id"])
        if identity in identities:
            continue
        identities.add(identity)
        item = resolve_accepted_claim_reference(
            store, memory_id=identity[0], claim_id=identity[1],
            expected_state_version=expected_state_version,
        )
        resolved[f"historical-claim-{len(resolved) + 1:04d}"] = item
    return resolved
