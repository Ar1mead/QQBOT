"""Versioned, bounded JSON protocol for the adapter worker boundary.

This module defines transport envelopes only. It does not launch a process or
provide OS isolation; the host must validate every response before CSD mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from adapters.contracts.observation import (
    ContentOrigin,
    ObservationCoverage,
    ObservationEvidence,
    ObservationResult,
    ObservationStatus,
)

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 1_048_576
MAX_ID_LENGTH = 128
MAX_TARGET_LENGTH = 512
MAX_MODALITIES = 16
MAX_EVIDENCE_ITEMS = 128
MAX_WARNINGS = 64


class WorkerProtocolError(ValueError):
    """Raised when a worker message is malformed or violates protocol bounds."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorkerProtocolError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode_object(raw: bytes | str) -> dict[str, Any]:
    if isinstance(raw, bytes):
        if len(raw) > MAX_MESSAGE_BYTES:
            raise WorkerProtocolError("worker message exceeds maximum size")
        try:
            raw = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise WorkerProtocolError("worker message must be UTF-8") from exc
    elif isinstance(raw, str):
        if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise WorkerProtocolError("worker message exceeds maximum size")
    else:
        raise TypeError("worker message must be bytes or str")
    def reject_nonstandard_constant(value: str) -> None:
        raise WorkerProtocolError(f"non-standard JSON constant is not allowed: {value}")

    try:
        value = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=reject_nonstandard_constant,
        )
    except WorkerProtocolError:
        raise
    except (json.JSONDecodeError, UnicodeError, RecursionError) as exc:
        raise WorkerProtocolError("worker message is not valid JSON") from exc
    if not isinstance(value, dict):
        raise WorkerProtocolError("worker message root must be an object")
    return value


def _encode_object(value: dict[str, Any]) -> bytes:
    try:
        encoded = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WorkerProtocolError("worker message contains non-JSON data") from exc
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise WorkerProtocolError("worker message exceeds maximum size")
    return encoded


def _require_exact_keys(value: dict[str, Any], expected: set[str]) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise WorkerProtocolError(f"invalid message fields; missing={missing}, extra={extra}")


def _bounded_string(value: Any, field: str, maximum: int = MAX_ID_LENGTH) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise WorkerProtocolError(f"{field} must be a non-empty string of at most {maximum} characters")
    if any(ord(char) < 32 for char in value):
        raise WorkerProtocolError(f"{field} must not contain control characters")
    return value


@dataclass(frozen=True)
class WorkerRequest:
    request_id: str
    adapter_id: str
    adapter_version: str
    operation: str
    target_ref: str
    modalities: tuple[str, ...]
    protocol_version: int = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if type(self.protocol_version) is not int or self.protocol_version != PROTOCOL_VERSION:
            raise WorkerProtocolError("unsupported worker protocol version")
        for name in ("request_id", "adapter_id", "adapter_version", "operation"):
            _bounded_string(getattr(self, name), name)
        _bounded_string(self.target_ref, "target_ref", MAX_TARGET_LENGTH)
        if not self.modalities or len(self.modalities) > MAX_MODALITIES:
            raise WorkerProtocolError("modalities count is outside protocol bounds")
        for modality in self.modalities:
            _bounded_string(modality, "modality", 64)
        if len(set(self.modalities)) != len(self.modalities):
            raise WorkerProtocolError("modalities must not contain duplicates")


@dataclass(frozen=True)
class WorkerResponse:
    request_id: str
    adapter_id: str
    adapter_version: str
    status: str
    evidence: tuple[dict[str, Any], ...] = ()
    warnings: tuple[str, ...] = ()
    error_code: str | None = None
    protocol_version: int = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if self.protocol_version != PROTOCOL_VERSION:
            raise WorkerProtocolError("unsupported worker protocol version")
        for name in ("request_id", "adapter_id", "adapter_version"):
            _bounded_string(getattr(self, name), name)
        if not isinstance(self.status, str) or self.status not in {"complete", "partial", "unavailable", "failed"}:
            raise WorkerProtocolError("unsupported worker response status")
        if len(self.evidence) > MAX_EVIDENCE_ITEMS:
            raise WorkerProtocolError("evidence count exceeds protocol bounds")
        if len(self.warnings) > MAX_WARNINGS:
            raise WorkerProtocolError("warning count exceeds protocol bounds")
        if any(not isinstance(item, dict) for item in self.evidence):
            raise WorkerProtocolError("evidence items must be JSON objects")
        for warning in self.warnings:
            _bounded_string(warning, "warning", 1024)
        if self.error_code is not None:
            _bounded_string(self.error_code, "error_code", 128)
        if self.status == "complete" and (not self.evidence or self.error_code is not None):
            raise WorkerProtocolError("complete response requires evidence and no error_code")
        if self.status == "partial" and not self.evidence:
            raise WorkerProtocolError("partial response requires evidence")
        if self.status == "unavailable" and self.evidence:
            raise WorkerProtocolError("unavailable response cannot contain evidence")
        if self.status == "failed" and (self.evidence or self.error_code is None):
            raise WorkerProtocolError("failed response requires error_code and no evidence")


def encode_request(request: WorkerRequest) -> bytes:
    if not isinstance(request, WorkerRequest):
        raise TypeError("request must be a WorkerRequest")
    return _encode_object({
        "protocol_version": request.protocol_version,
        "message_type": "observation_request",
        "request_id": request.request_id,
        "adapter_id": request.adapter_id,
        "adapter_version": request.adapter_version,
        "operation": request.operation,
        "target_ref": request.target_ref,
        "modalities": list(request.modalities),
    })


def decode_request(raw: bytes | str) -> WorkerRequest:
    value = _decode_object(raw)
    _require_exact_keys(value, {
        "protocol_version", "message_type", "request_id", "adapter_id",
        "adapter_version", "operation", "target_ref", "modalities",
    })
    if value["message_type"] != "observation_request":
        raise WorkerProtocolError("unexpected worker message type")
    if type(value["protocol_version"]) is not int or value["protocol_version"] != PROTOCOL_VERSION:
        raise WorkerProtocolError("unsupported worker protocol version")
    modalities = value["modalities"]
    if not isinstance(modalities, list) or any(not isinstance(item, str) for item in modalities):
        raise WorkerProtocolError("modalities must be a JSON string array")
    return WorkerRequest(
        request_id=value["request_id"],
        adapter_id=value["adapter_id"],
        adapter_version=value["adapter_version"],
        operation=value["operation"],
        target_ref=value["target_ref"],
        modalities=tuple(modalities),
        protocol_version=value["protocol_version"],
    )


def encode_response(response: WorkerResponse) -> bytes:
    if not isinstance(response, WorkerResponse):
        raise TypeError("response must be a WorkerResponse")
    return _encode_object({
        "protocol_version": response.protocol_version,
        "message_type": "observation_response",
        "request_id": response.request_id,
        "adapter_id": response.adapter_id,
        "adapter_version": response.adapter_version,
        "status": response.status,
        "evidence": list(response.evidence),
        "warnings": list(response.warnings),
        "error_code": response.error_code,
    })


def decode_response(raw: bytes | str) -> WorkerResponse:
    value = _decode_object(raw)
    _require_exact_keys(value, {
        "protocol_version", "message_type", "request_id", "adapter_id",
        "adapter_version", "status", "evidence", "warnings", "error_code",
    })
    if value["message_type"] != "observation_response":
        raise WorkerProtocolError("unexpected worker message type")
    if type(value["protocol_version"]) is not int or value["protocol_version"] != PROTOCOL_VERSION:
        raise WorkerProtocolError("unsupported worker protocol version")
    if not isinstance(value["evidence"], list) or not isinstance(value["warnings"], list):
        raise WorkerProtocolError("evidence and warnings must be JSON arrays")
    return WorkerResponse(
        request_id=value["request_id"],
        adapter_id=value["adapter_id"],
        adapter_version=value["adapter_version"],
        status=value["status"],
        evidence=tuple(value["evidence"]),
        warnings=tuple(value["warnings"]),
        error_code=value["error_code"],
        protocol_version=value["protocol_version"],
    )


def validate_response_for_request(response: WorkerResponse, request: WorkerRequest) -> None:
    """Bind a decoded response to the exact request and pinned adapter identity."""
    if not isinstance(response, WorkerResponse) or not isinstance(request, WorkerRequest):
        raise TypeError("response and request must use worker protocol types")
    if response.request_id != request.request_id:
        raise WorkerProtocolError("worker response request_id does not match request")
    if (
        response.adapter_id != request.adapter_id
        or response.adapter_version != request.adapter_version
    ):
        raise WorkerProtocolError("worker response adapter identity does not match request")

def response_to_observation_result(response: WorkerResponse, request: WorkerRequest) -> ObservationResult:
    """Reconstruct and validate worker evidence before it can enter CSD."""
    validate_response_for_request(response, request)
    evidence_items = []
    evidence_keys = {
        "observation_id", "adapter_id", "adapter_version", "platform",
        "external_ref", "observation_kind", "content_origin", "modality",
        "content", "source_ref", "observed_at", "received_at",
        "extraction_method", "content_digest", "coverage",
        "source_artifact_ref", "account_ref", "untrusted",
    }
    coverage_keys = {
        "modality", "extraction_method", "complete", "start_ms", "end_ms",
        "missing_ranges_ms", "notes",
    }
    for raw_evidence in response.evidence:
        _require_exact_keys(raw_evidence, evidence_keys)
        raw_coverage = raw_evidence["coverage"]
        if not isinstance(raw_coverage, dict):
            raise WorkerProtocolError("evidence coverage must be an object")
        _require_exact_keys(raw_coverage, coverage_keys)
        missing_ranges = raw_coverage["missing_ranges_ms"]
        notes = raw_coverage["notes"]
        if not isinstance(missing_ranges, list) or not isinstance(notes, list):
            raise WorkerProtocolError("coverage ranges and notes must be arrays")
        if any(not isinstance(item, list) or len(item) != 2 for item in missing_ranges):
            raise WorkerProtocolError("coverage missing ranges must be two-item arrays")
        try:
            coverage = ObservationCoverage(
                modality=raw_coverage["modality"],
                extraction_method=raw_coverage["extraction_method"],
                complete=raw_coverage["complete"],
                start_ms=raw_coverage["start_ms"],
                end_ms=raw_coverage["end_ms"],
                missing_ranges_ms=tuple(tuple(item) for item in missing_ranges),
                notes=tuple(notes),
            )
            evidence_items.append(ObservationEvidence(
                observation_id=raw_evidence["observation_id"],
                adapter_id=raw_evidence["adapter_id"],
                adapter_version=raw_evidence["adapter_version"],
                platform=raw_evidence["platform"],
                external_ref=raw_evidence["external_ref"],
                observation_kind=raw_evidence["observation_kind"],
                content_origin=ContentOrigin(raw_evidence["content_origin"]),
                modality=raw_evidence["modality"],
                content=raw_evidence["content"],
                source_ref=raw_evidence["source_ref"],
                observed_at=raw_evidence["observed_at"],
                received_at=raw_evidence["received_at"],
                extraction_method=raw_evidence["extraction_method"],
                content_digest=raw_evidence["content_digest"],
                coverage=coverage,
                source_artifact_ref=raw_evidence["source_artifact_ref"],
                account_ref=raw_evidence["account_ref"],
                untrusted=raw_evidence["untrusted"],
            ))
        except (TypeError, ValueError, KeyError) as exc:
            raise WorkerProtocolError(f"invalid observation evidence: {exc}") from exc
    try:
        return ObservationResult(
            status=ObservationStatus(response.status),
            evidence=tuple(evidence_items),
            warnings=response.warnings,
            error_code=response.error_code,
        )
    except (TypeError, ValueError) as exc:
        raise WorkerProtocolError(f"invalid observation result: {exc}") from exc
