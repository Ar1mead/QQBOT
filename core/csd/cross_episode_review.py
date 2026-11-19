"""Read-only semantic review for pending cross-episode CSD candidates.

The provider sees bounded, historically re-resolved source evidence. Its output
is an ephemeral opinion only: this module writes no CSD events and grants no
authority to change preferences, self-model state, Life Engine ranking, or ASM.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Protocol, Sequence

from .accepted_claim_references import (
    AcceptedClaimReferenceError,
    resolve_accepted_claim_reference,
)
from .cognitive import (
    OBSERVATION_EVENT,
    OBSERVATION_EVENT_V2,
    CROSS_EPISODE_PROPOSAL_EVENT,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
)
from .cross_episode_proposals import list_cross_episode_proposals


MAX_REVIEW_TEXT = 2000
MAX_REVIEW_LIST_ITEMS = 8
MAX_REVIEW_REFERENCES = 32
MAX_SOURCE_CONTENT_CHARS = 20_000
MAX_TOTAL_SOURCE_CONTENT_CHARS = 100_000
MAX_REVIEWER_ID = 200
MAX_REVIEWER_VERSION = 200

REVIEW_OUTCOMES = frozenset({
    "supported", "uncertain", "unsupported", "conflicting",
    "insufficient_context",
})
SCOPE_ASSESSMENTS = frozenset({"fits", "too_broad", "too_narrow", "unclear"})
RISK_FLAGS = frozenset({
    "sensitive_inference", "causal_overreach", "temporal_instability",
    "source_ambiguity", "support_counter_imbalance",
})


class CrossEpisodeReviewError(ValueError):
    """A pending candidate or its evidence cannot be reviewed safely."""


@dataclass(frozen=True)
class CrossEpisodeReviewCandidate:
    outcome: str
    confidence: float
    reasoning_summary: str
    supporting_reference_keys: Sequence[str]
    counter_evidence_reference_keys: Sequence[str]
    scope_assessment: str
    alternative_explanations: Sequence[str] = ()
    limitations: Sequence[str] = ()
    risk_flags: Sequence[str] = ()
    requires_human_review: bool = False


@dataclass(frozen=True)
class CrossEpisodeReviewArtifact:
    proposal_id: str
    proposal_event_id: str
    proposal_sequence: int
    proposal_digest: str
    based_on_state_version: int
    reviewer_id: str
    reviewer_version: str
    candidate: CrossEpisodeReviewCandidate


class CrossEpisodeReviewProvider(Protocol):
    """Replaceable reviewer. Implementations receive no CSD or action tools."""

    reviewer_id: str
    reviewer_version: str

    def review_cross_episode(
        self, review_input: Mapping[str, Any]
    ) -> CrossEpisodeReviewCandidate:
        """Return an opinion over the exact bounded evidence snapshot."""


def _canonical(value: Any) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    )


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _bounded_text(value: Any, field: str, *, required: bool = True) -> str:
    if not isinstance(value, str):
        raise CrossEpisodeReviewError(f"{field} must be text")
    if required and not value.strip():
        raise CrossEpisodeReviewError(f"{field} must not be empty")
    if len(value) > MAX_REVIEW_TEXT:
        raise CrossEpisodeReviewError(f"{field} exceeds the text limit")
    return value


def _bounded_list(value: Any, field: str, *, max_items: int) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise CrossEpisodeReviewError(f"{field} must be a bounded sequence")
    items = list(value)
    if len(items) > max_items:
        raise CrossEpisodeReviewError(f"{field} exceeds the item limit")
    for item in items:
        _bounded_text(item, field)
    if len(set(items)) != len(items):
        raise CrossEpisodeReviewError(f"{field} contains duplicates")
    return items


def _resolve_reference_bundle(
    store: CognitiveMemoryStore,
    items: Any,
    *,
    state_version: int,
    proposal_sequence: int,
    label: str,
) -> list[dict[str, Any]]:
    if not isinstance(items, list) or len(items) > MAX_REVIEW_REFERENCES:
        raise CrossEpisodeReviewError(f"{label} must be a bounded list")
    resolved_items: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for item in items:
        expected_fields = {
            "memory_id", "proposal_id", "decision_event_id", "proposal_event_id",
            "claim_id", "claim_digest", "source_event_ids", "status",
            "based_on_state_version",
        }
        if not isinstance(item, Mapping) or set(item) != expected_fields:
            raise CrossEpisodeReviewError(f"{label} contains an invalid persisted reference")
        memory_id, claim_id = item.get("memory_id"), item.get("claim_id")
        if not isinstance(memory_id, str) or not memory_id.strip():
            raise CrossEpisodeReviewError(f"{label} contains an invalid memory ID")
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise CrossEpisodeReviewError(f"{label} contains an invalid claim ID")
        identity = (memory_id, claim_id)
        if identity in identities:
            raise CrossEpisodeReviewError(f"{label} repeats a historical claim")
        identities.add(identity)
        try:
            resolved = resolve_accepted_claim_reference(
                store, memory_id=memory_id, claim_id=claim_id,
                expected_state_version=state_version,
                through_sequence=proposal_sequence,
            )
        except (AcceptedClaimReferenceError, KeyError, CognitiveIntegrityError) as exc:
            raise CrossEpisodeReviewError(
                f"{label} could not be re-resolved at the candidate's historical boundary"
            ) from exc
        canonical = {
            "memory_id": resolved["memory_id"],
            "proposal_id": resolved["proposal_id"],
            "decision_event_id": resolved["decision_event_id"],
            "proposal_event_id": resolved["proposal_event_id"],
            "claim_id": resolved["claim_id"],
            "claim_digest": resolved["claim_digest"],
            "source_event_ids": list(resolved["source_event_ids"]),
            "status": resolved["status"],
            "based_on_state_version": resolved["based_on_state_version"],
        }
        if dict(item) != canonical:
            raise CrossEpisodeReviewError(f"{label} lineage or claim digest is stale/tampered")
        if not canonical["source_event_ids"]:
            raise CrossEpisodeReviewError(f"{label} has no source observations")
        resolved_items.append(resolved)
    return resolved_items


def _source_evidence(
    store: CognitiveMemoryStore,
    support: Sequence[Mapping[str, Any]],
    counter: Sequence[Mapping[str, Any]],
    *,
    proposal_sequence: int,
) -> tuple[dict[str, Any], ...]:
    claim_rows: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}
    total_chars = 0

    for label, references in (("support", support), ("counter_evidence", counter)):
        for reference_index, reference in enumerate(references, start=1):
            claim = reference["claim"]
            evidence = claim.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                raise CrossEpisodeReviewError("historical claim has no evidence spans")
            expected_ids = set(reference["source_event_ids"])
            seen_ids: set[str] = set()
            for span in evidence:
                if not isinstance(span, Mapping) or set(span) != {"event_id", "locator", "quoted_text"}:
                    raise CrossEpisodeReviewError("historical claim evidence span is malformed")
                event_id = span.get("event_id")
                if not isinstance(event_id, str) or event_id not in expected_ids:
                    raise CrossEpisodeReviewError("evidence span is not in the resolved source lineage")
                seen_ids.add(event_id)
                try:
                    event = store.get_event(event_id)
                except (KeyError, CognitiveIntegrityError) as exc:
                    raise CrossEpisodeReviewError("source observation is unavailable or corrupt") from exc
                if (
                    event["event_type"] not in {OBSERVATION_EVENT, OBSERVATION_EVENT_V2}
                    or event["sequence"] >= proposal_sequence
                ):
                    raise CrossEpisodeReviewError("source observation is not before the candidate event")
                payload = event["payload"]
                content = payload.get("content")
                if not isinstance(content, str) or not content:
                    raise CrossEpisodeReviewError("source observation has no text content")
                if len(content) > MAX_SOURCE_CONTENT_CHARS:
                    raise CrossEpisodeReviewError("source observation exceeds the per-source size limit")
                if event_id not in sources:
                    total_chars += len(content)
                    if total_chars > MAX_TOTAL_SOURCE_CONTENT_CHARS:
                        raise CrossEpisodeReviewError("review evidence exceeds the total source size limit")
                    # Deliberately exclude account references and other opaque identity metadata.
                    provenance_fields = (
                        "observation_id", "adapter_id", "adapter_version", "platform",
                        "external_ref", "observation_kind", "content_origin", "modality",
                        "source_ref", "source_artifact_ref", "observed_at", "received_at",
                        "extraction_method", "content_digest", "untrusted",
                    )
                    provenance = {
                        key: payload[key] for key in provenance_fields if key in payload
                    }
                    if event["event_type"] == OBSERVATION_EVENT:
                        provenance = {
                            "observation_kind": payload.get("observation_kind"),
                            "source_ref": payload.get("source_ref"),
                            "observed_at": payload.get("observed_at"),
                            "coverage": payload.get("coverage"),
                        }
                    sources[event_id] = {
                        "event_id": event_id,
                        "event_type": event["event_type"],
                        "sequence": event["sequence"],
                        "occurred_at": event["occurred_at"],
                        "source": event["source"],
                        "provenance": provenance,
                        "content": content,
                    }
                locator = span.get("locator")
                quote = span.get("quoted_text")
                if (
                    not isinstance(locator, Mapping)
                    or set(locator) != {"kind", "unit", "start", "end"}
                    or locator.get("kind") != "text_range"
                    or locator.get("unit") != "unicode_codepoint"
                    or not isinstance(locator.get("start"), int)
                    or isinstance(locator.get("start"), bool)
                    or not isinstance(locator.get("end"), int)
                    or isinstance(locator.get("end"), bool)
                    or not isinstance(quote, str)
                ):
                    raise CrossEpisodeReviewError("source evidence locator is invalid")
                start, end = locator["start"], locator["end"]
                if start < 0 or end <= start or end > len(content) or content[start:end] != quote:
                    raise CrossEpisodeReviewError("quoted evidence does not match immutable source content")
                claim_rows.append({
                    "reference_key": f"{label}-{reference_index:02d}",
                    "claim_id": claim["claim_id"],
                    "claim_text": claim["text"],
                    "claim_digest": reference["claim_digest"],
                    "evidence_event_id": event_id,
                    "quoted_text": quote,
                    "start": start,
                    "end": end,
                })
            if seen_ids != expected_ids:
                raise CrossEpisodeReviewError("source event lineage and claim evidence do not match")

    return tuple({
        "claims": tuple(claim_rows),
        "sources": tuple(sources[key] for key in sorted(sources, key=lambda k: sources[k]["sequence"])),
    }[key] for key in ("claims", "sources"))


class CrossEpisodeReviewPipeline:
    """Review one pending-shadow candidate without persisting or applying the result."""

    def __init__(self, store: CognitiveMemoryStore, provider: CrossEpisodeReviewProvider):
        self.store = store
        self.provider = provider
        for field in ("reviewer_id", "reviewer_version"):
            value = getattr(provider, field, None)
            if not isinstance(value, str) or not value.strip() or len(value) > MAX_REVIEWER_ID:
                raise ValueError(f"{field} must be non-empty bounded text")
        if not callable(getattr(provider, "review_cross_episode", None)):
            raise TypeError("provider must implement review_cross_episode")

    @staticmethod
    def _validate_candidate(
        candidate: CrossEpisodeReviewCandidate,
        *,
        support_keys: set[str],
        counter_keys: set[str],
    ) -> None:
        if not isinstance(candidate, CrossEpisodeReviewCandidate):
            raise TypeError("review provider must return CrossEpisodeReviewCandidate")
        if not isinstance(candidate.outcome, str) or candidate.outcome not in REVIEW_OUTCOMES:
            raise CrossEpisodeReviewError("review outcome is unsupported")
        confidence = candidate.confidence
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise CrossEpisodeReviewError("review confidence must be finite and between 0 and 1")
        try:
            confidence = float(confidence)
        except (OverflowError, ValueError) as exc:
            raise CrossEpisodeReviewError("review confidence must be finite and between 0 and 1") from exc
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise CrossEpisodeReviewError("review confidence must be finite and between 0 and 1")
        _bounded_text(candidate.reasoning_summary, "reasoning_summary")
        if (
            not isinstance(candidate.scope_assessment, str)
            or candidate.scope_assessment not in SCOPE_ASSESSMENTS
        ):
            raise CrossEpisodeReviewError("scope assessment is unsupported")
        support = _bounded_list(
            candidate.supporting_reference_keys, "supporting_reference_keys",
            max_items=MAX_REVIEW_REFERENCES,
        )
        counter = _bounded_list(
            candidate.counter_evidence_reference_keys, "counter_evidence_reference_keys",
            max_items=MAX_REVIEW_REFERENCES,
        )
        if not set(support).issubset(support_keys):
            raise CrossEpisodeReviewError("review selected an unknown supporting reference key")
        if not set(counter).issubset(counter_keys):
            raise CrossEpisodeReviewError("review selected an unknown counter-evidence reference key")
        if set(support) & set(counter):
            raise CrossEpisodeReviewError("a reference cannot be both support and counter-evidence")
        if candidate.outcome == "supported" and not support:
            raise CrossEpisodeReviewError("supported review requires selected supporting evidence")
        if candidate.outcome == "conflicting" and (not support or not counter):
            raise CrossEpisodeReviewError("conflicting review requires support and counter-evidence")
        _bounded_list(candidate.alternative_explanations, "alternative_explanations", max_items=MAX_REVIEW_LIST_ITEMS)
        _bounded_list(candidate.limitations, "limitations", max_items=MAX_REVIEW_LIST_ITEMS)
        flags = _bounded_list(candidate.risk_flags, "risk_flags", max_items=len(RISK_FLAGS))
        if not set(flags).issubset(RISK_FLAGS):
            raise CrossEpisodeReviewError("review contains an unsupported risk flag")
        if not isinstance(candidate.requires_human_review, bool):
            raise CrossEpisodeReviewError("requires_human_review must be boolean")

    def review_proposal(self, proposal_id: str) -> CrossEpisodeReviewArtifact:
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id must be non-empty text")
        if len(proposal_id) > MAX_REVIEWER_ID:
            raise ValueError("proposal_id exceeds the identity limit")

        # Resolve the candidate, historical claim references and source events in
        # one stable read snapshot. The provider call happens only after it closes.
        with self.store._read_tx():
            matches = [
                item for item in list_cross_episode_proposals(self.store)
                if item["proposal_id"] == proposal_id
            ]
            if len(matches) != 1:
                raise CrossEpisodeReviewError("pending cross-episode proposal is missing or ambiguous")
            row = matches[0]
            event = self.store.get_event(row["event_id"])
            if event["event_type"] != CROSS_EPISODE_PROPOSAL_EVENT:
                raise CrossEpisodeReviewError("target event is not a cross-episode proposal")
            payload = event["payload"]
            if row["status"] != "pending_shadow" or payload.get("proposal_id") != proposal_id:
                raise CrossEpisodeReviewError("only pending-shadow proposals may be reviewed")
            candidate = payload.get("candidate")
            if not isinstance(candidate, Mapping):
                raise CrossEpisodeReviewError("cross-episode candidate payload is malformed")
            state_version = payload.get("based_on_state_version")
            if (
                not isinstance(state_version, int) or isinstance(state_version, bool)
                or state_version < 0
            ):
                raise CrossEpisodeReviewError("candidate state version is invalid")
            support = _resolve_reference_bundle(
                self.store, candidate.get("supporting_references"),
                state_version=state_version, proposal_sequence=event["sequence"],
                label="supporting_references",
            )
            counter = _resolve_reference_bundle(
                self.store, candidate.get("counter_evidence_references"),
                state_version=state_version, proposal_sequence=event["sequence"],
                label="counter_evidence_references",
            )
            support_ids = {(item["memory_id"], item["claim_id"]) for item in support}
            counter_ids = {(item["memory_id"], item["claim_id"]) for item in counter}
            if support_ids & counter_ids:
                raise CrossEpisodeReviewError("support and counter-evidence overlap")
            evidence = _source_evidence(
                self.store, support, counter, proposal_sequence=event["sequence"]
            )
            review_input = {
                "contract_version": 2,
                "proposal": {
                    "proposal_id": proposal_id,
                    "candidate_kind": candidate.get("candidate_kind"),
                    "owner": candidate.get("owner"),
                    "domain": candidate.get("domain"),
                    "statement": candidate.get("statement"),
                    "scope": candidate.get("scope"),
                    "exclusions": candidate.get("exclusions"),
                    "confidence": candidate.get("confidence"),
                    "uncertainty": candidate.get("uncertainty"),
                    "reasoning_summary": candidate.get("reasoning_summary"),
                    "alternatives": candidate.get("alternatives"),
                    "limitations": candidate.get("limitations"),
                    "independent_support_event_count": candidate.get("independent_support_event_count"),
                },
                "based_on_state_version": state_version,
                "proposal_event_id": event["event_id"],
                "proposal_sequence": event["sequence"],
                "supporting_references": [
                    {"reference_key": f"support-{i:02d}", "claim": item["claim"],
                     "claim_digest": item["claim_digest"]}
                    for i, item in enumerate(support, start=1)
                ],
                "counter_evidence_references": [
                    {"reference_key": f"counter_evidence-{i:02d}", "claim": item["claim"],
                     "claim_digest": item["claim_digest"]}
                    for i, item in enumerate(counter, start=1)
                ],
                "source_evidence": evidence[1],
                "evidence_spans": evidence[0],
            }
            serialized = _canonical(review_input)
            if len(serialized.encode("utf-8")) > MAX_TOTAL_SOURCE_CONTENT_CHARS * 4:
                raise CrossEpisodeReviewError("complete review input exceeds the byte limit")
            proposal_digest = _digest(_canonical(payload))

        # Provider is untrusted and receives no store handle or mutation API.
        result = self.provider.review_cross_episode(review_input)
        support_keys = {f"support-{i:02d}" for i in range(1, len(support) + 1)}
        counter_keys = {f"counter_evidence-{i:02d}" for i in range(1, len(counter) + 1)}
        self._validate_candidate(
            result, support_keys=support_keys, counter_keys=counter_keys
        )
        # Freeze provider-supplied sequences before exposing the artifact.
        normalized = CrossEpisodeReviewCandidate(
            outcome=result.outcome,
            confidence=float(result.confidence),
            reasoning_summary=result.reasoning_summary,
            supporting_reference_keys=tuple(result.supporting_reference_keys),
            counter_evidence_reference_keys=tuple(result.counter_evidence_reference_keys),
            scope_assessment=result.scope_assessment,
            alternative_explanations=tuple(result.alternative_explanations),
            limitations=tuple(result.limitations),
            risk_flags=tuple(result.risk_flags),
            requires_human_review=result.requires_human_review,
        )
        return CrossEpisodeReviewArtifact(
            proposal_id=proposal_id,
            proposal_event_id=event["event_id"],
            proposal_sequence=event["sequence"],
            proposal_digest=proposal_digest,
            based_on_state_version=state_version,
            reviewer_id=self.provider.reviewer_id,
            reviewer_version=self.provider.reviewer_version,
            candidate=normalized,
        )
