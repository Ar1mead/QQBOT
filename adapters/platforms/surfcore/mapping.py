"""Pure mapper for versioned, read-only SurfCore observation DTOs.

The worker-safe path converts DTOs into untrusted ObservationEvidence only.
Host-only CSD event conversion is lazy and never imported by the Worker entrypoint.
This module performs no network, filesystem, credential, or platform operations.
QQ cursor advancement is proposed, never persisted here.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.csd.cognitive import CognitiveEvent

from adapters.contracts.observation import (
    AdapterManifest,
    Capability,
    CapabilityMode,
    ContentOrigin,
    ObservationCoverage,
    ObservationEvidence,
)
ADAPTER_VERSION = "0.1.0"
SCHEMA_VERSION = 1
MAX_CONTENT_CHARS = 256_000
MAX_QQ_BATCH_RECORDS = 500
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
_OPTIONAL_FIELDS = {
    "account_ref", "source_artifact_ref", "cursor",
    "conversation_kind", "conversation_ref", "sender_ref", "historical",
    "context_kind", "context_ref", "actor_ref", "actor_role", "parent_ref",
    "content_language",
}
_QQ_REQUIRED_FIELDS = {
    "account_ref", "cursor", "conversation_kind", "conversation_ref",
    "sender_ref", "historical", "actor_role",
}
_QQ_ONLY_FIELDS = {
    "cursor", "conversation_kind", "conversation_ref", "sender_ref", "historical",
}
_BILI_REQUIRED_FIELDS = {"context_kind", "context_ref", "actor_role"}
_BILI_ACTOR_ROLES = {
    "bilibili.video.metadata": "uploader",
    "bilibili.video.subtitle": "subtitle_contributor",
    "bilibili.video.comment": "comment_author",
    "bilibili.video.danmaku": "danmaku_sender",
}
_COVERAGE_FIELDS = {
    "modality", "extraction_method", "complete", "start_ms", "end_ms",
    "missing_ranges_ms", "notes",
}
_BATCH_FIELDS = {"schema_version", "stream_ref", "after_cursor", "next_cursor", "records"}


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _cursor(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
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
    if platform == "qq":
        missing_qq = _QQ_REQUIRED_FIELDS - keys
        if missing_qq:
            raise ValueError(f"QQ record missing provenance fields: {', '.join(sorted(missing_qq))}")
    elif keys & _QQ_ONLY_FIELDS:
        raise ValueError("QQ-only provenance fields are not valid for Bilibili records")
    else:
        missing_bili = _BILI_REQUIRED_FIELDS - keys
        if missing_bili:
            raise ValueError(f"Bilibili record missing provenance fields: {', '.join(sorted(missing_bili))}")
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

    record_id = _nonempty(record["record_id"], "record_id")
    account_ref = record.get("account_ref")
    artifact_ref = record.get("source_artifact_ref")
    if account_ref is not None:
        account_ref = _nonempty(account_ref, "account_ref")
    if artifact_ref is not None:
        artifact_ref = _nonempty(artifact_ref, "source_artifact_ref")
    context_kind = None
    context_ref = None
    actor_ref = None
    source_sequence = None
    historical = False
    actor_role = None
    parent_ref = None
    content_language = None
    if platform == "qq":
        cursor = _cursor(record["cursor"], "record.cursor")
        context_kind = _nonempty(record["conversation_kind"], "conversation_kind")
        if context_kind not in {"private", "group"}:
            raise ValueError("QQ conversation_kind must be private or group")
        context_ref = _nonempty(record["conversation_ref"], "conversation_ref")
        actor_ref = _nonempty(record["sender_ref"], "sender_ref")
        actor_role = _nonempty(record["actor_role"], "actor_role")
        if actor_role != "sender":
            raise ValueError("QQ actor_role must be sender")
        historical = record["historical"]
        if not isinstance(historical, bool):
            raise ValueError("QQ historical must be boolean")
        source_sequence = cursor
    else:
        context_kind = _nonempty(record["context_kind"], "context_kind")
        if context_kind != "video":
            raise ValueError("Bilibili context_kind must be video")
        context_ref = _nonempty(record["context_ref"], "context_ref")
        if context_ref != _nonempty(record["external_ref"], "external_ref"):
            raise ValueError("Bilibili context_ref must match external_ref")
        actor_role = _nonempty(record["actor_role"], "actor_role")
        expected_role = _BILI_ACTOR_ROLES[kind]
        if actor_role != expected_role:
            raise ValueError(f"Bilibili actor_role must be {expected_role}")
        actor_ref = record.get("actor_ref")
        if actor_ref is not None:
            actor_ref = _nonempty(actor_ref, "actor_ref")
        parent_ref = record.get("parent_ref")
        if parent_ref is not None:
            if kind != "bilibili.video.comment":
                raise ValueError("parent_ref is only valid for Bilibili comments")
            parent_ref = _nonempty(parent_ref, "parent_ref")
        content_language = record.get("content_language")
        if content_language is not None:
            if kind != "bilibili.video.subtitle":
                raise ValueError("content_language is only valid for Bilibili subtitles")
            content_language = _nonempty(content_language, "content_language")
            if re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", content_language) is None:
                raise ValueError("content_language must be a BCP 47 language tag")

    identity = hashlib.sha256(
        f"{platform}\0{account_ref or ''}\0{record_id}".encode("utf-8")
    ).hexdigest()
    observation_id = f"{platform}-{identity}"
    digest = "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest()
    coverage = ObservationCoverage(
        modality=modality,
        extraction_method=extraction_method,
        complete=coverage_data["complete"],
        start_ms=coverage_data["start_ms"],
        end_ms=coverage_data["end_ms"],
        missing_ranges_ms=tuple(normalized_ranges),
        notes=tuple(notes),
    )

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
        context_kind=context_kind,
        context_ref=context_ref,
        actor_ref=actor_ref,
        actor_role=actor_role,
        parent_ref=parent_ref,
        content_language=content_language,
        source_sequence=source_sequence,
        historical=historical,
        untrusted=True,
    )


def map_surfcore_record_to_csd_event(record: Mapping[str, Any]) -> "CognitiveEvent":
    """Host-only conversion of one validated DTO into a deterministic CSD event."""
    from adapters.csd_mapping import observation_evidence_to_csd_event

    return observation_evidence_to_csd_event(map_surfcore_record(record))


@dataclass(frozen=True)
class SurfCoreQQObservationBatch:
    """Worker-safe validated QQ page containing evidence, never CSD events."""

    stream_ref: str
    after_cursor: int
    proposed_cursor: int
    evidence: tuple[ObservationEvidence, ...]

    def __post_init__(self) -> None:
        _nonempty(self.stream_ref, "batch.stream_ref")
        _cursor(self.after_cursor, "batch.after_cursor")
        _cursor(self.proposed_cursor, "batch.proposed_cursor")
        if self.proposed_cursor < self.after_cursor:
            raise ValueError("proposed cursor cannot move backwards")
        if any(not isinstance(item, ObservationEvidence) for item in self.evidence):
            raise ValueError("batch evidence must contain ObservationEvidence values")


def validate_surfcore_qq_batch(batch: Mapping[str, Any]) -> SurfCoreQQObservationBatch:
    """Validate a bounded QQ cursor page and map records to untrusted evidence.

    This worker-safe function does not import or construct CSD events. The host
    must durably submit all returned evidence to CSD before persisting the
    proposed cursor.
    """
    if not isinstance(batch, Mapping):
        raise TypeError("QQ batch must be a mapping")
    if set(batch) != _BATCH_FIELDS:
        raise ValueError("QQ batch fields do not match the versioned batch schema")
    if batch["schema_version"] != SCHEMA_VERSION or isinstance(batch["schema_version"], bool):
        raise ValueError("unsupported QQ batch schema_version")

    stream_ref = _nonempty(batch["stream_ref"], "batch.stream_ref")
    after_cursor = _cursor(batch["after_cursor"], "batch.after_cursor")
    next_cursor = _cursor(batch["next_cursor"], "batch.next_cursor")
    if next_cursor < after_cursor:
        raise ValueError("batch next_cursor cannot move backwards")
    records = batch["records"]
    if not isinstance(records, (list, tuple)):
        raise ValueError("batch records must be an array")
    if len(records) > MAX_QQ_BATCH_RECORDS:
        raise ValueError("QQ batch exceeds the record limit")

    prior_cursor = after_cursor
    seen_ids: set[str] = set()
    evidence: list[ObservationEvidence] = []
    for record in records:
        if not isinstance(record, Mapping) or record.get("platform") != "qq":
            raise ValueError("QQ batch may contain only QQ records")
        current_cursor = _cursor(record.get("cursor"), "record.cursor")
        if current_cursor <= prior_cursor:
            raise ValueError("QQ record cursors must be strictly increasing after the checkpoint")
        if current_cursor > next_cursor:
            raise ValueError("QQ record cursor exceeds batch next_cursor")
        record_id = _nonempty(record.get("record_id"), "record.record_id")
        if record_id in seen_ids:
            raise ValueError("QQ batch contains a duplicate record_id")
        seen_ids.add(record_id)
        prior_cursor = current_cursor
        if record.get("account_ref") != stream_ref:
            raise ValueError("QQ record account_ref must match batch stream_ref")
        evidence.append(map_surfcore_record(record))

    return SurfCoreQQObservationBatch(
        stream_ref=stream_ref,
        after_cursor=after_cursor,
        proposed_cursor=next_cursor,
        evidence=tuple(evidence),
    )


@dataclass(frozen=True)
class SurfCoreQQBatch:
    """Host-side CSD event batch; cursor persists only after durable CSD writes."""

    stream_ref: str
    after_cursor: int
    proposed_cursor: int
    events: tuple["CognitiveEvent", ...]

    def __post_init__(self) -> None:
        _nonempty(self.stream_ref, "batch.stream_ref")
        _cursor(self.after_cursor, "batch.after_cursor")
        _cursor(self.proposed_cursor, "batch.proposed_cursor")
        if self.proposed_cursor < self.after_cursor:
            raise ValueError("proposed cursor cannot move backwards")
        from core.csd.cognitive import CognitiveEvent

        if any(not isinstance(event, CognitiveEvent) for event in self.events):
            raise ValueError("batch events must be CognitiveEvent values")


def map_surfcore_qq_batch(batch: Mapping[str, Any]) -> SurfCoreQQBatch:
    """Host-only compatibility mapper from a validated QQ page to CSD events."""
    from adapters.csd_mapping import observation_evidence_to_csd_event

    mapped = validate_surfcore_qq_batch(batch)
    return SurfCoreQQBatch(
        stream_ref=mapped.stream_ref,
        after_cursor=mapped.after_cursor,
        proposed_cursor=mapped.proposed_cursor,
        events=tuple(observation_evidence_to_csd_event(item) for item in mapped.evidence),
    )
