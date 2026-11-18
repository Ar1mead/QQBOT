"""Versioned, bounded JSON protocol for the adapter worker boundary.

This module defines transport envelopes only. It does not launch a process or
provide OS isolation; the host must validate every response before CSD mapping.
"""
from __future__ import annotations

from dataclasses import dataclass
import base64
import binascii
import hashlib
import json
from typing import Any

from adapters.contracts.observation import (
    ContentOrigin,
    MAX_OBSERVATION_INPUT_BYTES,
    ObservationCoverage,
    ObservationEvidence,
    ObservationResult,
    ObservationStatus,
)

PROTOCOL_VERSION = 4
MAX_MESSAGE_BYTES = 1_048_576
MAX_INPUT_PAYLOAD_BYTES = MAX_OBSERVATION_INPUT_BYTES
MAX_ID_LENGTH = 128
MAX_TARGET_LENGTH = 512
MAX_MODALITIES = 16
MAX_EVIDENCE_ITEMS = 128
MAX_WARNINGS = 64
MAX_RESULT_METADATA_ITEMS = 16
MAX_RESULT_METADATA_KEY_LENGTH = 64
MAX_RESULT_METADATA_STRING_LENGTH = 1024


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


def _normalize_result_metadata(value: Any) -> tuple[tuple[str, str | int | bool | None], ...]:
    """Validate small, immutable scalar metadata; adapter schemas are checked by the host."""
    if not isinstance(value, (dict, tuple)):
        raise WorkerProtocolError("result_metadata must be an object or immutable key/value tuple")
    items = list(value.items()) if isinstance(value, dict) else list(value)
    if len(items) > MAX_RESULT_METADATA_ITEMS:
        raise WorkerProtocolError("result_metadata contains too many entries")
    normalized: dict[str, str | int | bool | None] = {}
    for item in items:
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise WorkerProtocolError("result_metadata entries must be key/value pairs")
        key, entry = item
        if not isinstance(key, str) or not key.strip() or len(key) > MAX_RESULT_METADATA_KEY_LENGTH:
            raise WorkerProtocolError("result_metadata keys must be bounded non-empty strings")
        if any(ord(char) < 32 for char in key):
            raise WorkerProtocolError("result_metadata keys must not contain control characters")
        if key in normalized:
            raise WorkerProtocolError("result_metadata contains duplicate keys")
        if entry is not None and type(entry) not in (str, int, bool):
            raise WorkerProtocolError("result_metadata values must be string, integer, boolean, or null")
        if isinstance(entry, str):
            if len(entry) > MAX_RESULT_METADATA_STRING_LENGTH or any(ord(char) < 32 for char in entry):
                raise WorkerProtocolError("result_metadata string value exceeds bounds")
        if type(entry) is int and not -(2**63) <= entry <= (2**63 - 1):
            raise WorkerProtocolError("result_metadata integer is outside signed 64-bit bounds")
        normalized[key] = entry
    return tuple(sorted(normalized.items(), key=lambda pair: pair[0]))


@dataclass(frozen=True)
class WorkerRequest:
    request_id: str
    adapter_id: str
    adapter_version: str
    operation: str
    target_ref: str
    modalities: tuple[str, ...]
    protocol_version: int = PROTOCOL_VERSION
    input_payload: bytes = b""

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
        if not isinstance(self.input_payload, bytes):
            raise WorkerProtocolError("input_payload must be immutable bytes")
        if len(self.input_payload) > MAX_INPUT_PAYLOAD_BYTES:
            raise WorkerProtocolError("input_payload exceeds the 512 KiB limit")


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
    result_metadata: tuple[tuple[str, str | int | bool | None], ...] = ()

    def __post_init__(self) -> None:
        normalized_metadata = _normalize_result_metadata(self.result_metadata)
        object.__setattr__(self, "result_metadata", normalized_metadata)
        if type(self.protocol_version) is not int or self.protocol_version != PROTOCOL_VERSION:
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
    payload_b64 = base64.b64encode(request.input_payload).decode("ascii")
    payload_digest = hashlib.sha256(request.input_payload).hexdigest()
    return _encode_object({
        "protocol_version": request.protocol_version,
        "message_type": "observation_request",
        "request_id": request.request_id,
        "adapter_id": request.adapter_id,
        "adapter_version": request.adapter_version,
        "operation": request.operation,
        "target_ref": request.target_ref,
        "modalities": list(request.modalities),
        "input_payload_b64": payload_b64,
        "input_payload_sha256": payload_digest,
    })


def decode_request(raw: bytes | str) -> WorkerRequest:
    value = _decode_object(raw)
    _require_exact_keys(value, {
        "protocol_version", "message_type", "request_id", "adapter_id",
        "adapter_version", "operation", "target_ref", "modalities",
        "input_payload_b64", "input_payload_sha256",
    })
    if value["message_type"] != "observation_request":
        raise WorkerProtocolError("unexpected worker message type")
    if type(value["protocol_version"]) is not int or value["protocol_version"] != PROTOCOL_VERSION:
        raise WorkerProtocolError("unsupported worker protocol version")
    modalities = value["modalities"]
    if not isinstance(modalities, list) or any(not isinstance(item, str) for item in modalities):
        raise WorkerProtocolError("modalities must be a JSON string array")
    payload_b64 = value["input_payload_b64"]
    payload_digest = value["input_payload_sha256"]
    if not isinstance(payload_b64, str):
        raise WorkerProtocolError("input_payload_b64 must be a base64 string")
    if (
        not isinstance(payload_digest, str)
        or len(payload_digest) != 64
        or any(char not in "0123456789abcdef" for char in payload_digest)
    ):
        raise WorkerProtocolError("input_payload_sha256 must be 64 lowercase hexadecimal characters")
    try:
        input_payload = base64.b64decode(payload_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise WorkerProtocolError("input_payload_b64 is not valid base64") from exc
    if base64.b64encode(input_payload).decode("ascii") != payload_b64:
        raise WorkerProtocolError("input_payload_b64 is not canonical base64")
    if len(input_payload) > MAX_INPUT_PAYLOAD_BYTES:
        raise WorkerProtocolError("input_payload exceeds the 512 KiB limit")
    actual_digest = hashlib.sha256(input_payload).hexdigest()
    if actual_digest != payload_digest:
        raise WorkerProtocolError("input_payload_sha256 does not match payload bytes")
    return WorkerRequest(
        request_id=value["request_id"],
        adapter_id=value["adapter_id"],
        adapter_version=value["adapter_version"],
        operation=value["operation"],
        target_ref=value["target_ref"],
        modalities=tuple(modalities),
        protocol_version=value["protocol_version"],
        input_payload=input_payload,
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
        "result_metadata": dict(response.result_metadata),
    })


def decode_response(raw: bytes | str) -> WorkerResponse:
    value = _decode_object(raw)
    _require_exact_keys(value, {
        "protocol_version", "message_type", "request_id", "adapter_id",
        "adapter_version", "status", "evidence", "warnings", "error_code",
        "result_metadata",
    })
    if value["message_type"] != "observation_response":
        raise WorkerProtocolError("unexpected worker message type")
    if type(value["protocol_version"]) is not int or value["protocol_version"] != PROTOCOL_VERSION:
        raise WorkerProtocolError("unsupported worker protocol version")
    if not isinstance(value["evidence"], list) or not isinstance(value["warnings"], list):
        raise WorkerProtocolError("evidence and warnings must be JSON arrays")
    if not isinstance(value["result_metadata"], dict):
        raise WorkerProtocolError("result_metadata must be a JSON object")
    metadata = _normalize_result_metadata(value["result_metadata"])
    return WorkerResponse(
        request_id=value["request_id"],
        adapter_id=value["adapter_id"],
        adapter_version=value["adapter_version"],
        status=value["status"],
        evidence=tuple(value["evidence"]),
        warnings=tuple(value["warnings"]),
        error_code=value["error_code"],
        protocol_version=value["protocol_version"],
        result_metadata=metadata,
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

def observation_evidence_to_wire(evidence: ObservationEvidence) -> dict[str, Any]:
    """Serialize a validated evidence object to the exact protocol-v4 wire schema."""
    if not isinstance(evidence, ObservationEvidence):
        raise TypeError("evidence must be an ObservationEvidence")
    coverage = evidence.coverage
    return {
        "observation_id": evidence.observation_id,
        "adapter_id": evidence.adapter_id,
        "adapter_version": evidence.adapter_version,
        "platform": evidence.platform,
        "external_ref": evidence.external_ref,
        "observation_kind": evidence.observation_kind,
        "content_origin": evidence.content_origin.value,
        "modality": evidence.modality,
        "content": evidence.content,
        "source_ref": evidence.source_ref,
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
            "missing_ranges_ms": [list(pair) for pair in coverage.missing_ranges_ms],
            "notes": list(coverage.notes),
        },
        "source_artifact_ref": evidence.source_artifact_ref,
        "account_ref": evidence.account_ref,
        "context_kind": evidence.context_kind,
        "context_ref": evidence.context_ref,
        "actor_ref": evidence.actor_ref,
        "actor_role": evidence.actor_role,
        "parent_ref": evidence.parent_ref,
        "content_language": evidence.content_language,
        "source_sequence": evidence.source_sequence,
        "historical": evidence.historical,
        "untrusted": evidence.untrusted,
    }


def response_to_observation_result(response: WorkerResponse, request: WorkerRequest) -> ObservationResult:
    """Reconstruct and validate worker evidence before it can enter CSD."""
    validate_response_for_request(response, request)
    evidence_items = []
    evidence_keys = {
        "observation_id", "adapter_id", "adapter_version", "platform",
        "external_ref", "observation_kind", "content_origin", "modality",
        "content", "source_ref", "observed_at", "received_at",
        "extraction_method", "content_digest", "coverage",
        "source_artifact_ref", "account_ref", "context_kind", "context_ref",
        "actor_ref", "actor_role", "parent_ref", "content_language",
        "source_sequence", "historical", "untrusted",
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
            if (
                raw_evidence["adapter_id"] != request.adapter_id
                or raw_evidence["adapter_version"] != request.adapter_version
            ):
                raise WorkerProtocolError("evidence identity does not match the pinned request")
            if raw_evidence["modality"] not in request.modalities:
                raise WorkerProtocolError("evidence modality was not requested")
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
                context_kind=raw_evidence["context_kind"],
                context_ref=raw_evidence["context_ref"],
                actor_ref=raw_evidence["actor_ref"],
                actor_role=raw_evidence["actor_role"],
                parent_ref=raw_evidence["parent_ref"],
                content_language=raw_evidence["content_language"],
                source_sequence=raw_evidence["source_sequence"],
                historical=raw_evidence["historical"],
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
