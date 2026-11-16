"""Stable adapter-facing contracts; no platform SDK imports belong here."""

from .observation import (
    AdapterManifest,
    Capability,
    CapabilityMode,
    ObservationAdapter,
    ObservationEvidence,
    ObservationRequest,
    ObservationResult,
    ObservationStatus,
    ObservationCoverage,
)

__all__ = [
    "AdapterManifest", "Capability", "CapabilityMode", "ObservationAdapter",
    "ObservationEvidence", "ObservationRequest", "ObservationResult",
    "ObservationStatus", "ObservationCoverage",
]
