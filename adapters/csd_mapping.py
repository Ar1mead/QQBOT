"""One-way mapping from the platform-neutral adapter contract into CSD.

The core never imports this module. It preserves adapter provenance in a v2
observation event; it does not mark external content as trusted or as memory.
"""
from __future__ import annotations

from adapters.contracts.observation import ObservationEvidence
from core.csd.cognitive import CognitiveEvent, OBSERVATION_EVENT_V2


def observation_evidence_to_csd_event(evidence: ObservationEvidence) -> CognitiveEvent:
    """Convert one validated adapter evidence item into a deterministic CSD event.

    The receipt timestamp is used as the event-envelope occurrence time. The
    platform/source observation time remains separately preserved in payload.
    Repeated delivery of the same adapter/observation identity yields the same
    event ID and immutable payload, allowing CSD idempotency to handle retries.
    """
    if not isinstance(evidence, ObservationEvidence):
        raise TypeError("evidence must be an ObservationEvidence value")

    event_id = f"observation:{evidence.adapter_id}:{evidence.observation_id}"
    coverage = evidence.coverage
    payload = {
        "observation_id": evidence.observation_id,
        "adapter_id": evidence.adapter_id,
        "adapter_version": evidence.adapter_version,
        "platform": evidence.platform,
        "account_ref": evidence.account_ref,
        "context_kind": evidence.context_kind,
        "context_ref": evidence.context_ref,
        "actor_ref": evidence.actor_ref,
        "source_sequence": evidence.source_sequence,
        "historical": evidence.historical,
        "external_ref": evidence.external_ref,
        "observation_kind": evidence.observation_kind,
        "content_origin": evidence.content_origin.value,
        "modality": evidence.modality,
        "content": evidence.content,
        "source_ref": evidence.source_ref,
        "source_artifact_ref": evidence.source_artifact_ref,
        "observed_at": evidence.observed_at,
        "received_at": evidence.received_at,
        "extraction_method": evidence.extraction_method,
        "content_digest": evidence.content_digest,
        "coverage": {
            "modality": coverage.modality,
            "extraction_method": coverage.extraction_method,
            "complete": coverage.complete,
            "start_ms": coverage.start_ms,
            "end_ms": coverage.end_ms,
            "missing_ranges_ms": [list(item) for item in coverage.missing_ranges_ms],
            "notes": list(coverage.notes),
        },
        "untrusted": evidence.untrusted,
    }
    return CognitiveEvent(
        event_id=event_id,
        occurred_at=evidence.received_at,
        correlation_id=event_id,
        event_type=OBSERVATION_EVENT_V2,
        source=f"observation-adapter:{evidence.adapter_id}",
        payload=payload,
    )
