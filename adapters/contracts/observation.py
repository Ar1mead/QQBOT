"""Platform-neutral observation contracts.

Observations are untrusted evidence, not instructions and not accepted memories.
This module deliberately has no network, filesystem, runtime, or platform SDK code.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from enum import Enum
import re
from typing import Protocol


MAX_OBSERVATION_INPUT_BYTES = 512 * 1024


class CapabilityMode(str, Enum):
    OBSERVE = "observe"
    PRESENT = "present"
    SIDE_EFFECT = "side_effect"


class ObservationStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class ContentOrigin(str, Enum):
    """Where normalized evidence text came from; neither value implies truth."""

    SOURCE_PROVIDED = "source_provided"
    ADAPTER_EXTRACTED = "adapter_extracted"


def _nonempty(value: str, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")


def _aware_timestamp(value: str, field: str) -> None:
    _nonempty(value, field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")


@dataclass(frozen=True)
class Capability:
    name: str
    mode: CapabilityMode
    description: str
    required_scopes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.name, "capability.name")
        _nonempty(self.description, "capability.description")
        if not isinstance(self.mode, CapabilityMode):
            raise ValueError("capability.mode must be a CapabilityMode")
        if any(not isinstance(scope, str) or not scope.strip() for scope in self.required_scopes):
            raise ValueError("capability.required_scopes must contain non-empty strings")


@dataclass(frozen=True)
class AdapterManifest:
    adapter_id: str
    adapter_version: str
    platform: str
    capabilities: tuple[Capability, ...]
    observation_schema_versions: tuple[int, ...] = (2,)

    def __post_init__(self) -> None:
        _nonempty(self.adapter_id, "manifest.adapter_id")
        _nonempty(self.adapter_version, "manifest.adapter_version")
        _nonempty(self.platform, "manifest.platform")
        names = [capability.name for capability in self.capabilities]
        if len(names) != len(set(names)):
            raise ValueError("manifest capability names must be unique")
        if not self.capabilities:
            raise ValueError("manifest must declare at least one capability")
        if (
            not self.observation_schema_versions
            or any(not isinstance(version, int) or isinstance(version, bool) or version < 1
                   for version in self.observation_schema_versions)
        ):
            raise ValueError("observation schema versions must be non-empty positive integers")
        if len(self.observation_schema_versions) != len(set(self.observation_schema_versions)):
            raise ValueError("observation schema versions must not contain duplicates")

    @property
    def observation_only(self) -> bool:
        return all(capability.mode is CapabilityMode.OBSERVE for capability in self.capabilities)


@dataclass(frozen=True)
class ObservationRequest:
    request_id: str
    target_ref: str
    modalities: tuple[str, ...]

    def __post_init__(self) -> None:
        _nonempty(self.request_id, "request.request_id")
        _nonempty(self.target_ref, "request.target_ref")
        if not self.modalities:
            raise ValueError("request.modalities must not be empty")
        if any(not isinstance(item, str) or not item.strip() for item in self.modalities):
            raise ValueError("request.modalities must contain non-empty strings")
        if len(self.modalities) != len(set(self.modalities)):
            raise ValueError("request.modalities must not contain duplicates")


@dataclass(frozen=True)
class ObservationCoverage:
    modality: str
    extraction_method: str
    complete: bool
    start_ms: int | None = None
    end_ms: int | None = None
    missing_ranges_ms: tuple[tuple[int, int], ...] = ()
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty(self.modality, "coverage.modality")
        _nonempty(self.extraction_method, "coverage.extraction_method")
        if not isinstance(self.complete, bool):
            raise ValueError("coverage.complete must be boolean")
        for name, value in (("start_ms", self.start_ms), ("end_ms", self.end_ms)):
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 0):
                raise ValueError(f"coverage.{name} must be a non-negative integer or None")
        if self.start_ms is not None and self.end_ms is not None and self.end_ms < self.start_ms:
            raise ValueError("coverage.end_ms must be >= coverage.start_ms")
        prior_end: int | None = None
        for start, end in self.missing_ranges_ms:
            if (not isinstance(start, int) or isinstance(start, bool) or start < 0
                    or not isinstance(end, int) or isinstance(end, bool) or end < start):
                raise ValueError("coverage missing ranges must be non-negative ordered integer pairs")
            if prior_end is not None and start < prior_end:
                raise ValueError("coverage missing ranges must be sorted and non-overlapping")
            if self.start_ms is not None and start < self.start_ms:
                raise ValueError("coverage missing range starts before covered interval")
            if self.end_ms is not None and end > self.end_ms:
                raise ValueError("coverage missing range ends after covered interval")
            prior_end = end
        if self.complete and self.missing_ranges_ms:
            raise ValueError("complete coverage cannot declare missing ranges")
        if any(not isinstance(note, str) or not note.strip() for note in self.notes):
            raise ValueError("coverage.notes must contain non-empty strings")


@dataclass(frozen=True)
class ObservationEvidence:
    observation_id: str
    adapter_id: str
    adapter_version: str
    platform: str
    external_ref: str
    observation_kind: str
    content_origin: ContentOrigin
    modality: str
    content: str
    source_ref: str
    observed_at: str
    received_at: str
    extraction_method: str
    content_digest: str
    coverage: ObservationCoverage
    source_artifact_ref: str | None = None
    account_ref: str | None = None
    context_kind: str | None = None
    context_ref: str | None = None
    actor_ref: str | None = None
    actor_role: str | None = None
    parent_ref: str | None = None
    content_language: str | None = None
    source_sequence: int | None = None
    historical: bool = False
    untrusted: bool = True

    def __post_init__(self) -> None:
        for field in (
            "observation_id", "adapter_id", "adapter_version", "platform",
            "external_ref", "observation_kind", "modality", "content",
            "source_ref", "extraction_method",
        ):
            _nonempty(getattr(self, field), f"evidence.{field}")
        if not isinstance(self.content_origin, ContentOrigin):
            raise ValueError("evidence.content_origin must be a ContentOrigin")
        _aware_timestamp(self.observed_at, "evidence.observed_at")
        _aware_timestamp(self.received_at, "evidence.received_at")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.content_digest):
            raise ValueError("evidence.content_digest must be sha256:<64 lowercase hex chars>")
        expected_digest = "sha256:" + hashlib.sha256(
            self.content.encode("utf-8")
        ).hexdigest()
        if self.content_digest != expected_digest:
            raise ValueError("evidence.content_digest does not match the UTF-8 bytes of content")
        if self.coverage.modality != self.modality:
            raise ValueError("evidence modality must match coverage modality")
        if self.coverage.extraction_method != self.extraction_method:
            raise ValueError("evidence extraction_method must match coverage extraction_method")
        if self.source_artifact_ref is not None:
            _nonempty(self.source_artifact_ref, "evidence.source_artifact_ref")
        if self.account_ref is not None:
            _nonempty(self.account_ref, "evidence.account_ref")
        if (self.context_kind is None) != (self.context_ref is None):
            raise ValueError("evidence.context_kind and context_ref must be provided together")
        if self.context_kind is not None:
            _nonempty(self.context_kind, "evidence.context_kind")
            _nonempty(self.context_ref, "evidence.context_ref")
        if self.actor_ref is not None:
            _nonempty(self.actor_ref, "evidence.actor_ref")
        if self.actor_role is not None:
            _nonempty(self.actor_role, "evidence.actor_role")
        if self.parent_ref is not None:
            _nonempty(self.parent_ref, "evidence.parent_ref")
        if self.content_language is not None:
            _nonempty(self.content_language, "evidence.content_language")
            if not re.fullmatch(r"[A-Za-z]{2,8}(?:-[A-Za-z0-9]{1,8})*", self.content_language):
                raise ValueError("evidence.content_language must be a BCP 47 language tag")
        if self.source_sequence is not None and (
            not isinstance(self.source_sequence, int)
            or isinstance(self.source_sequence, bool)
            or self.source_sequence < 0
        ):
            raise ValueError("evidence.source_sequence must be a non-negative integer or None")
        if not isinstance(self.historical, bool):
            raise ValueError("evidence.historical must be boolean")
        if self.untrusted is not True:
            raise ValueError("external observation evidence must remain untrusted")


@dataclass(frozen=True)
class ObservationResult:
    status: ObservationStatus
    evidence: tuple[ObservationEvidence, ...] = ()
    warnings: tuple[str, ...] = ()
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ObservationStatus):
            raise ValueError("result.status must be an ObservationStatus")
        if any(not isinstance(item, ObservationEvidence) for item in self.evidence):
            raise ValueError("result.evidence must contain ObservationEvidence values")
        if any(not isinstance(item, str) or not item.strip() for item in self.warnings):
            raise ValueError("result.warnings must contain non-empty strings")
        if self.status is ObservationStatus.COMPLETE:
            if not self.evidence or any(not item.coverage.complete for item in self.evidence):
                raise ValueError("complete result requires evidence with complete coverage")
            if self.error_code is not None:
                raise ValueError("complete result cannot contain an error_code")
        elif self.status is ObservationStatus.PARTIAL:
            if not self.evidence:
                raise ValueError("partial result requires at least one evidence item")
        elif self.status is ObservationStatus.UNAVAILABLE:
            if self.evidence:
                raise ValueError("unavailable result cannot contain evidence")
        elif self.status is ObservationStatus.FAILED:
            _nonempty(self.error_code or "", "result.error_code")
            if self.evidence:
                raise ValueError("failed result cannot contain evidence; use partial when evidence exists")


class ObservationAdapter(Protocol):
    @property
    def manifest(self) -> AdapterManifest: ...

    def observe(self, request: ObservationRequest) -> ObservationResult: ...
