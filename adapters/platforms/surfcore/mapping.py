"""Pure mapper for versioned, read-only SurfCore observation DTOs.

This module performs no network, filesystem, credential, or platform operations.
It is not a live SurfCore connector. It converts already-received DTOs into the
project's validated, untrusted ObservationEvidence / CSD Observation v2 path.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
import re
from typing import Any

from adapters.contracts.observation import (
    AdapterManifest,
    Capability,
    CapabilityMode,
    ContentOrigin,
    ObservationCoverage,
    ObservationEvidence,
)
from adapters.csd_mapping import observation_evidence_to_csd_event

ADAPTER_VERSION = "0.1.0"
SCHEMA_VERSION = 1
MAX_CONTENT_CHARS = 256_000
_ALLOWED_PLATFORMS = {"qq", "bilibili"}
_ALLOWED_KINDS = {
    "qq": {"qq.message.incoming", "qq.message.incoming.historical", "qq.notice"},
    "bilibili": {
        "bilibili.video.metadata",
        "bilibili.video.subtitle",
        "bilibili.video.comment",
        "bilibili.video.danmaku",
    },
}
_REQUIRED_FIELDS = {
    "schema_version", "platform", "record_id", "external_ref",
    "observation_kind", "content_origin", "modality", "content",
    "source_ref", "observed_at", "received_at", "extraction_method",
    "coverage",
}
_OPTIONAL_FIELDS = {"account_ref", "source_artifact_ref"}
_COVERAGE_FIELDS = {
    "modality", "extraction_method", "complete", "start_ms", "end_ms",
    "missing_ranges_ms", "notes",
}


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _manifest(platform: str) -> AdapterManifest:
    if platform not in _ALLOWED_PLATFORMS:
        raise ValueError("unsupported SurfCore platform")
    return AdapterManifest(
        adapter_id=f"surfcore.{platform}.readonly",
        adapter_version=ADAPTER_VERSION,
        platform=platform,
        capabilities=(
            Capability(
                name="observe:text",
                mode=CapabilityMode.OBSERVE,
                description=f"Accept normalized, read-only {platform} text observations; no account mutations.",
            ),
        ),
        observation_schema_versions=(2,),
    )


def qq_manifest() -> AdapterManifest:
    """Return the minimal QQ receive-only manifest."""
    return _manifest("qq")


def bilibili_manifest() -> AdapterManifest:
    """Return the minimal Bilibili read-only manifest."""
    return _manifest("bilibili")


def map_surfcore_record(record: Mapping[str, Any]) -> ObservationEvidence:
    """Validate one SurfCore DTO and map it to untrusted ObservationEvidence.

    DTOs are deliberately exact-key/versioned. Unknown fields fail closed so a
    future SurfCore schema cannot silently widen the trust or action surface.
    """
    if not isinstance(record, Mapping):
        raise TypeError("SurfCore record must be a mapping")
    keys = set(record)
    missing = _REQUIRED_FIELDS - keys
    unknown = keys - _REQUIRED_FIELDS - _OPTIONAL_FIELDS
    if missing:
        raise ValueError(f"SurfCore record missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"SurfCore record has unknown fields: {', '.join(sorted(unknown))}")
    if record["schema_version"] != SCHEMA_VERSION or isinstance(record["schema_version"], bool):
        raise ValueError("unsupported SurfCore observation schema_version")

    platform = _nonempty(record["platform"], "platform")
    if platform not in _ALLOWED_PLATFORMS:
        raise ValueError("unsupported SurfCore platform")
    kind = _nonempty(record["observation_kind"], "observation_kind")
    if kind not in _ALLOWED_KINDS[platform]:
        raise ValueError("observation_kind is not allowed for this platform")

    modality = _nonempty(record["modality"], "modality")
    if modality != "text":
        raise ValueError("initial SurfCore adapter slice accepts text modality only")
    content = _nonempty(record["content"], "content")
    if len(content) > MAX_CONTENT_CHARS:
        raise ValueError("content exceeds the SurfCore observation limit")

    origin = record["content_origin"]
    try:
        content_origin = ContentOrigin(origin)
    except (TypeError, ValueError) as exc:
        raise ValueError("unsupported content_origin") from exc

    coverage_data = record["coverage"]
    if not isinstance(coverage_data, Mapping):
        raise ValueError("coverage must be an object")
    if set(coverage_data) != _COVERAGE_FIELDS:
        raise ValueError("coverage fields do not match SurfCore DTO schema")
    if coverage_data["modality"] != modality:
        raise ValueError("coverage modality must match record modality")
    extraction_method = _nonempty(record["extraction_method"], "extraction_method")
    if coverage_data["extraction_method"] != extraction_method:
        raise ValueError("coverage extraction_method must match record extraction_method")
    if not isinstance(coverage_data["complete"], bool):
        raise ValueError("coverage.complete must be boolean")
    ranges = coverage_data["missing_ranges_ms"]
    notes = coverage_data["notes"]
    if not isinstance(ranges, (list, tuple)) or not isinstance(notes, (list, tuple)):
        raise ValueError("coverage ranges and notes must be arrays")
    normalized_ranges = []
    for pair in ranges:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError("each missing range must be a pair")
        normalized_ranges.append((pair[0], pair[1]))
    normalized_notes = tuple(notes)

    record_id = _nonempty(record["record_id"], "record_id")
    identity = hashlib.sha256(f"{platform}\0{record_id}".encode("utf-8")).hexdigest()
    observation_id = f"{platform}-{identity}"
    digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    coverage = ObservationCoverage(
        modality=modality,
        extraction_method=extraction_method,
        complete=coverage_data["complete"],
        start_ms=coverage_data["start_ms"],
        end_ms=coverage_data["end_ms"],
        missing_ranges_ms=tuple(normalized_ranges),
        notes=normalized_notes,
    )

    account_ref = record.get("account_ref")
    artifact_ref = record.get("source_artifact_ref")
    if account_ref is not None:
        account_ref = _nonempty(account_ref, "account_ref")
    if artifact_ref is not None:
        artifact_ref = _nonempty(artifact_ref, "source_artifact_ref")

    return ObservationEvidence(
        observation_id=observation_id,
        adapter_id=f"surfcore.{platform}.readonly",
        adapter_version=ADAPTER_VERSION,
        platform=platform,
        external_ref=_nonempty(record["external_ref"], "external_ref"),
        observation_kind=kind,
        content_origin=content_origin,
        modality=modality,
        content=content,
        source_ref=_nonempty(record["source_ref"], "source_ref"),
        observed_at=_nonempty(record["observed_at"], "observed_at"),
        received_at=_nonempty(record["received_at"], "received_at"),
        extraction_method=extraction_method,
        content_digest=digest,
        coverage=coverage,
        source_artifact_ref=artifact_ref,
        account_ref=account_ref,
        untrusted=True,
    )


def map_surfcore_record_to_csd_event(record: Mapping[str, Any]):
    """Map a validated SurfCore DTO directly to a deterministic CSD event."""
    return observation_evidence_to_csd_event(map_surfcore_record(record))
