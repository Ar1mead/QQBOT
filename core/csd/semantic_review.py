"""Provider-neutral, pending-only semantic review pipeline for grounded memories.

The reviewer returns an attributed analysis of an inference claim. This pipeline
binds it to immutable proposal/claim digests and writes review events only.
It never evaluates or accepts a memory proposal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Protocol, Sequence
import uuid

from .cognitive import (
    GROUNDED_PROPOSAL_EVENT,
    SEMANTIC_REVIEW_CONTRACT_VERSION,
    SEMANTIC_REVIEW_EVENT,
    MAX_SEMANTIC_REVIEW_TEXT,
    MAX_SEMANTIC_REVIEW_LIST_ITEMS,
    MAX_SEMANTIC_REVIEW_SUPPORT_IDS,
    CognitiveEvent,
    CognitiveMemoryStore,
)


ALLOWED_REVIEW_OUTCOMES = {
    "supported",
    "uncertain",
    "unsupported",
    "insufficient_context",
}


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SemanticReviewCandidate:
    outcome: str
    reasoning_summary: str
    supporting_claim_ids: Sequence[str] = ()
    alternative_explanations: Sequence[str] = ()
    limitations: Sequence[str] = ()


class SemanticReviewProvider(Protocol):
    """Replaceable reviewer interface. Implementations must not hold CSD tools."""

    reviewer_id: str
    reviewer_version: str

    def review_inference(
        self,
        proposal: Mapping[str, Any],
        inference_claim: Mapping[str, Any],
        supporting_claims: Sequence[Mapping[str, Any]],
    ) -> SemanticReviewCandidate:
        """Return one opinion for one inference claim; do not mutate CSD."""


class SemanticReviewPipeline:
    """Binds reviewer opinions to exact immutable claims and submits review events."""

    def __init__(
        self,
        store: CognitiveMemoryStore,
        provider: SemanticReviewProvider,
    ) -> None:
        self.store = store
        self.provider = provider
        if not isinstance(provider.reviewer_id, str) or not provider.reviewer_id.strip():
            raise ValueError("reviewer_id must be a non-empty string")
        if not isinstance(provider.reviewer_version, str) or not provider.reviewer_version.strip():
            raise ValueError("reviewer_version must be a non-empty string")
        if not callable(getattr(provider, "review_inference", None)):
            raise TypeError("provider must implement review_inference")

    @staticmethod
    def _validate_candidate(
        candidate: SemanticReviewCandidate,
        *,
        allowed_supporting_claim_ids: set[str],
    ) -> None:
        if not isinstance(candidate, SemanticReviewCandidate):
            raise TypeError("review provider must return SemanticReviewCandidate")
        if candidate.outcome not in ALLOWED_REVIEW_OUTCOMES:
            raise ValueError("unsupported semantic review outcome")
        if (
            not isinstance(candidate.reasoning_summary, str)
            or not candidate.reasoning_summary.strip()
            or len(candidate.reasoning_summary) > MAX_SEMANTIC_REVIEW_TEXT
        ):
            raise ValueError("reasoning_summary must be non-empty and within the text limit")

        def validate_list(
            value: Sequence[str], name: str, *, max_items: int
        ) -> list[str]:
            if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
                raise TypeError(f"{name} must be a sequence of strings")
            result = list(value)
            if (
                len(result) > max_items
                or any(
                    not isinstance(item, str)
                    or not item.strip()
                    or len(item) > MAX_SEMANTIC_REVIEW_TEXT
                    for item in result
                )
            ):
                raise ValueError(f"{name} must be a bounded list of non-empty strings")
            if len(set(result)) != len(result):
                raise ValueError(f"{name} must not contain duplicates")
            return result

        support_ids = validate_list(
            candidate.supporting_claim_ids,
            "supporting_claim_ids",
            max_items=MAX_SEMANTIC_REVIEW_SUPPORT_IDS,
        )
        validate_list(
            candidate.alternative_explanations,
            "alternative_explanations",
            max_items=MAX_SEMANTIC_REVIEW_LIST_ITEMS,
        )
        validate_list(
            candidate.limitations,
            "limitations",
            max_items=MAX_SEMANTIC_REVIEW_LIST_ITEMS,
        )
        if not set(support_ids).issubset(allowed_supporting_claim_ids):
            raise ValueError("supporting_claim_ids must refer to direct source claims")
        if candidate.outcome == "supported" and not support_ids:
            raise ValueError("supported review requires at least one supporting source claim")

    def review_proposal(self, proposal_id: str) -> list[dict[str, Any]]:
        """Review all inference claims, persist review events, and leave CSD evaluation separate."""
        if not isinstance(proposal_id, str) or not proposal_id.strip():
            raise ValueError("proposal_id must be a non-empty string")

        stored = self.store.get_proposal(proposal_id)
        if stored["status"] != "pending":
            raise ValueError("semantic review can only target a pending proposal")
        proposal_event = self.store.get_event(stored["proposal_event_id"])
        if proposal_event["event_type"] != GROUNDED_PROPOSAL_EVENT:
            raise ValueError("semantic review applies only to grounded v2 proposals")

        proposal = stored["proposal"]
        claims = proposal["claims"]
        claims_by_id = {claim["claim_id"]: claim for claim in claims}
        inference_claims = [
            claim for claim in claims if claim.get("epistemic_type") == "inference"
        ]
        if not inference_claims:
            return []

        proposal_digest = stored["proposal_digest"]
        pending_reviews: list[dict[str, Any]] = []

        # All provider calls complete before any event is submitted. A provider
        # failure therefore cannot leave a partially generated batch in CSD.
        for claim in inference_claims:
            supporting_claim_ids = list(claim["derived_from_claim_ids"])
            supporting_claims = [claims_by_id[item] for item in supporting_claim_ids]
            candidate = self.provider.review_inference(
                proposal,
                claim,
                supporting_claims,
            )
            self._validate_candidate(
                candidate,
                allowed_supporting_claim_ids=set(supporting_claim_ids),
            )
            pending_reviews.append({
                "claim_id": claim["claim_id"],
                "claim_digest": _digest(_canonical(claim)),
                "candidate": candidate,
            })

        events: list[tuple[CognitiveEvent, dict[str, Any]]] = []
        for item in pending_reviews:
            candidate = item["candidate"]
            payload = {
                "review_id": str(uuid.uuid4()),
                "proposal_id": proposal_id,
                "proposal_event_id": stored["proposal_event_id"],
                "proposal_digest": proposal_digest,
                "claim_id": item["claim_id"],
                "claim_digest": item["claim_digest"],
                "reviewer": {
                    "component": self.provider.reviewer_id,
                    "version": self.provider.reviewer_version,
                },
                "contract_version": SEMANTIC_REVIEW_CONTRACT_VERSION,
                "outcome": candidate.outcome,
                "reasoning_summary": candidate.reasoning_summary,
                "supporting_claim_ids": list(candidate.supporting_claim_ids),
                "alternative_explanations": list(candidate.alternative_explanations),
                "limitations": list(candidate.limitations),
            }
            event = CognitiveEvent(
                event_id=f"evt-semantic-review-{uuid.uuid4()}",
                occurred_at=datetime.now(timezone.utc).isoformat(),
                correlation_id=proposal_event["correlation_id"],
                event_type=SEMANTIC_REVIEW_EVENT,
                source=f"semantic-review.pipeline:{self.provider.reviewer_id}",
                payload=payload,
            )
            events.append((event, payload))

        results: list[dict[str, Any]] = []
        for event, _ in events:
            results.append(self.store.submit_event(event))
        return results
