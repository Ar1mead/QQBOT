"""Fixed, offline worker entrypoint with an explicit dispatch allowlist.

The dispatch key is supplied by the trusted host from the verified runtime
bundle manifest. No module paths, eval, shell commands, or network clients are
accepted from the request.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Mapping
from typing import Any

# Python is launched with -I -S -B. Isolated mode deliberately omits the script
# directory from sys.path, so add only this verified, staged application root.
_WORKER_FILE_DIR = os.path.dirname(os.path.realpath(__file__))
# In the source tree this module lives in adapters/; in the staged runtime it
# is copied to app/worker_entrypoint.py beside the adapters/ package.
_WORKER_APP_ROOT = (
    os.path.dirname(_WORKER_FILE_DIR)
    if os.path.basename(_WORKER_FILE_DIR).casefold() == "adapters"
    else _WORKER_FILE_DIR
)
sys.path.insert(0, _WORKER_APP_ROOT)

from adapters.platforms.surfcore.mapping import map_surfcore_qq_batch, map_surfcore_record
from adapters.worker_protocol import (
    MAX_MESSAGE_BYTES,
    WorkerProtocolError,
    WorkerRequest,
    WorkerResponse,
    decode_request,
    encode_response,
    observation_evidence_to_wire,
    validate_response_for_request,
)


class WorkerDispatchError(ValueError):
    """Raised when a fixed adapter operation rejects its bounded input."""


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WorkerDispatchError("duplicate JSON key in adapter payload")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise WorkerDispatchError(f"non-standard JSON constant is not allowed: {value}")


def _decode_payload(payload: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        )
    except WorkerDispatchError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise WorkerDispatchError("adapter input payload must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise WorkerDispatchError("adapter input payload root must be an object")
    return value


def _dispatch_surfcore_qq_batch(request: WorkerRequest) -> WorkerResponse:
    if (
        request.adapter_id != "surfcore.qq.readonly"
        or request.adapter_version != "0.1.0"
        or request.operation != "observe_batch"
    ):
        raise WorkerDispatchError("request does not match the pinned SurfCore QQ binding")
    if request.modalities != ("text",):
        raise WorkerDispatchError("SurfCore QQ batch supports text modality only")

    batch = _decode_payload(request.input_payload)
    mapped_batch = map_surfcore_qq_batch(batch)
    if request.target_ref != mapped_batch.stream_ref:
        raise WorkerDispatchError("request target_ref does not match the QQ stream_ref")

    evidence = tuple(
        observation_evidence_to_wire(map_surfcore_record(record))
        for record in batch["records"]
    )
    return WorkerResponse(
        request_id=request.request_id,
        adapter_id=request.adapter_id,
        adapter_version=request.adapter_version,
        status="complete" if evidence else "unavailable",
        evidence=evidence,
        result_metadata=(
            ("stream_ref", mapped_batch.stream_ref),
            ("after_cursor", mapped_batch.after_cursor),
            ("proposed_cursor", mapped_batch.proposed_cursor),
        ),
    )


# This table is deliberately static. Never replace it with importlib, entry-point
# discovery, a module path from the manifest, or a request-controlled callable.
DISPATCH_TABLE: dict[str, Callable[[WorkerRequest], WorkerResponse]] = {
    "surfcore_qq_batch": _dispatch_surfcore_qq_batch,
}


def process_one_request(request_bytes: bytes, dispatch_key: str) -> bytes:
    """Decode one request, invoke one pinned handler, and encode one response."""
    if not isinstance(request_bytes, bytes) or not 1 <= len(request_bytes) <= MAX_MESSAGE_BYTES:
        raise WorkerProtocolError("worker request is outside the protocol message limit")
    if not isinstance(dispatch_key, str) or dispatch_key not in DISPATCH_TABLE:
        raise WorkerProtocolError("worker dispatch key is not allowlisted")

    request = decode_request(request_bytes)
    handler = DISPATCH_TABLE[dispatch_key]
    try:
        response = handler(request)
    except (WorkerDispatchError, TypeError, ValueError) as exc:
        response = WorkerResponse(
            request_id=request.request_id,
            adapter_id=request.adapter_id,
            adapter_version=request.adapter_version,
            status="failed",
            error_code="invalid_adapter_input",
        )
    validate_response_for_request(response, request)
    encoded = encode_response(response)
    if len(encoded) > MAX_MESSAGE_BYTES:
        raise WorkerProtocolError("worker response exceeds the protocol message limit")
    return encoded


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] != "--dispatch-key":
        sys.stderr.write("worker requires one host-selected --dispatch-key\n")
        return 64
    raw = sys.stdin.buffer.read(MAX_MESSAGE_BYTES + 1)
    if not raw or len(raw) > MAX_MESSAGE_BYTES:
        sys.stderr.write("worker request is empty or exceeds the protocol limit\n")
        return 65
    try:
        response = process_one_request(raw, sys.argv[2])
    except Exception:
        sys.stderr.write("worker request rejected\n")
        return 66
    sys.stdout.buffer.write(response)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
