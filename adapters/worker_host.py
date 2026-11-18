"""Host-side orchestration for adapters executed by an injected worker backend.

No subprocess or sandbox is created here. A production backend must enforce the
OS isolation policy described in docs/design/adapter-worker-isolation.md.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from adapters.contracts.observation import (
    AdapterManifest,
    ObservationAdapter,
    ObservationRequest,
    ObservationResult,
)
from adapters.worker_protocol import (
    MAX_MESSAGE_BYTES,
    WorkerProtocolError,
    WorkerRequest,
    decode_response,
    encode_request,
    response_to_observation_result,
)


DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_TIMEOUT_SECONDS = 120.0


class WorkerExecutionError(RuntimeError):
    """Raised when the injected worker backend fails or violates its contract."""


class WorkerExecutor(Protocol):
    """Trusted host-owned backend that must enforce OS isolation before use.

    Implementations must enforce the timeout by terminating the worker and
    must stop reading output once max_response_bytes is exceeded. WorkerHost
    rechecks returned bytes, but cannot undo memory already allocated by a
    backend that ignores this streaming limit.
    """

    def execute(
        self,
        request_payload: bytes,
        *,
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> bytes: ...


@dataclass(frozen=True)
class WorkerHostResult:
    """Validated observation plus bounded adapter-specific scalar metadata."""

    observation: ObservationResult
    result_metadata: tuple[tuple[str, str | int | bool | None], ...] = ()


@dataclass(frozen=True)
class WorkerHost:
    executor: WorkerExecutor
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_response_bytes: int = MAX_MESSAGE_BYTES

    def __post_init__(self) -> None:
        if self.executor is None:
            raise ValueError("a reviewed worker executor is required; no in-process fallback is allowed")
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or isinstance(self.timeout_seconds, bool)
            or not 0 < self.timeout_seconds <= MAX_TIMEOUT_SECONDS
        ):
            raise ValueError("timeout_seconds must be greater than 0 and at most 120")
        if (
            not isinstance(self.max_response_bytes, int)
            or isinstance(self.max_response_bytes, bool)
            or not 1 <= self.max_response_bytes <= MAX_MESSAGE_BYTES
        ):
            raise ValueError("max_response_bytes is outside the protocol limit")

    def observe_with_metadata(
        self,
        *,
        adapter_id: str,
        adapter_version: str,
        operation: str,
        request: ObservationRequest,
    ) -> WorkerHostResult:
        worker_request = WorkerRequest(
            request_id=request.request_id,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            operation=operation,
            target_ref=request.target_ref,
            modalities=request.modalities,
            input_payload=request.input_payload,
        )
        payload = encode_request(worker_request)
        try:
            raw_response = self.executor.execute(
                payload,
                timeout_seconds=float(self.timeout_seconds),
                max_response_bytes=self.max_response_bytes,
            )
        except TimeoutError as exc:
            raise WorkerExecutionError("worker execution timed out") from exc
        except Exception as exc:
            raise WorkerExecutionError("worker backend execution failed") from exc
        if not isinstance(raw_response, bytes):
            raise WorkerExecutionError("worker backend must return raw bytes")
        if len(raw_response) > self.max_response_bytes:
            raise WorkerExecutionError("worker response exceeds host-configured size limit")
        try:
            response = decode_response(raw_response)
            result = response_to_observation_result(response, worker_request)
        except WorkerProtocolError as exc:
            raise WorkerExecutionError(f"worker response rejected: {exc}") from exc
        return WorkerHostResult(result, response.result_metadata)

    def observe(
        self,
        *,
        adapter_id: str,
        adapter_version: str,
        operation: str,
        request: ObservationRequest,
    ) -> ObservationResult:
        return self.observe_with_metadata(
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            operation=operation,
            request=request,
        ).observation


@dataclass
class WorkerBackedObservationAdapter:
    """ObservationAdapter bridge to a host-injected worker executor.

    The executor is a trusted host component, not plugin-provided code. Until a
    real OS-isolated executor is implemented and verified on the target OS,
    this bridge must not be used to run third-party adapter code.
    """

    manifest: AdapterManifest
    host: WorkerHost
    operation: str = "observe"

    def __post_init__(self) -> None:
        if not isinstance(self.manifest, AdapterManifest):
            raise TypeError("manifest must be an AdapterManifest")
        if not isinstance(self.host, WorkerHost):
            raise TypeError("host must be a WorkerHost")
        if not isinstance(self.operation, str) or not self.operation.strip():
            raise ValueError("operation must be a non-empty string")

    def observe(self, request: ObservationRequest) -> ObservationResult:
        if not isinstance(request, ObservationRequest):
            raise TypeError("request must be an ObservationRequest")
        result = self.host.observe(
            adapter_id=self.manifest.adapter_id,
            adapter_version=self.manifest.adapter_version,
            operation=self.operation,
            request=request,
        )
        for evidence in result.evidence:
            if evidence.platform != self.manifest.platform:
                raise WorkerExecutionError("worker evidence platform does not match registered manifest")
            if evidence.external_ref != request.target_ref:
                raise WorkerExecutionError("worker evidence target does not match observation request")
        return result
