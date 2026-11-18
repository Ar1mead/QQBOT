"""Core-controlled registry and dispatcher for observation adapters.

This is an application-level policy boundary, not a process sandbox. Adapter
implementations registered here must already be trusted code loaded by the host.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from adapters.contracts.observation import (
    AdapterManifest,
    ObservationAdapter,
    ObservationRequest,
    ObservationResult,
)
from adapters.policy import require_observation_only


class AdapterRegistrationError(ValueError):
    """Raised when an adapter cannot be safely registered."""


class AdapterDispatchDenied(PermissionError):
    """Raised when a request exceeds an adapter's declared observation scope."""


class AdapterContractViolation(RuntimeError):
    """Raised when an adapter returns evidence outside its registered identity/scope."""


@dataclass
class ObservationAdapterRegistry:
    """Explicit allowlist of host-loaded adapters; no discovery or auto-import."""

    _adapters: dict[str, tuple[AdapterManifest, ObservationAdapter]] = field(default_factory=dict)

    def register(self, adapter: ObservationAdapter) -> None:
        manifest = getattr(adapter, "manifest", None)
        observe = getattr(adapter, "observe", None)
        if not isinstance(manifest, AdapterManifest) or not callable(observe):
            raise AdapterRegistrationError(
                "adapter must expose an AdapterManifest and callable observe(request)"
            )
        try:
            require_observation_only(manifest)
        except (TypeError, PermissionError) as exc:
            raise AdapterRegistrationError(str(exc)) from exc
        if manifest.adapter_id in self._adapters:
            raise AdapterRegistrationError(
                f"adapter_id is already registered: {manifest.adapter_id}"
            )
        self._adapters[manifest.adapter_id] = (manifest, adapter)

    def registered_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))

    def observe(self, adapter_id: str, request: ObservationRequest) -> ObservationResult:
        registered = self._adapters.get(adapter_id)
        if registered is None:
            raise AdapterDispatchDenied(f"adapter is not registered: {adapter_id}")

        manifest, adapter = registered
        declared_modalities = {
            capability.name.removeprefix("observe:")
            for capability in manifest.capabilities
            if capability.name.startswith("observe:")
        }
        if not set(request.modalities).issubset(declared_modalities):
            denied = sorted(set(request.modalities) - declared_modalities)
            raise AdapterDispatchDenied(
                "requested modalities are not declared by the adapter: "
                + ", ".join(denied)
            )

        result = adapter.observe(request)
        if not isinstance(result, ObservationResult):
            raise AdapterContractViolation("adapter must return an ObservationResult")
        for evidence in result.evidence:
            if (
                evidence.adapter_id != manifest.adapter_id
                or evidence.adapter_version != manifest.adapter_version
                or evidence.platform != manifest.platform
            ):
                raise AdapterContractViolation(
                    "observation evidence identity does not match registered manifest"
                )
            if evidence.modality not in request.modalities:
                raise AdapterContractViolation(
                    "adapter returned an evidence modality not requested by the caller"
                )
            if evidence.untrusted is not True:
                raise AdapterContractViolation(
                    "external observation evidence must remain untrusted"
                )
        return result
