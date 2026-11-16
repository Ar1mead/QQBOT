"""Deterministic in-memory observation adapter for contract tests.

This helper has no network, filesystem, runtime, or account integration.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from adapters.contracts.observation import (
    AdapterManifest,
    ObservationRequest,
    ObservationResult,
)


@dataclass
class FakeObservationAdapter:
    manifest: AdapterManifest
    result: ObservationResult
    requests: list[ObservationRequest] = field(default_factory=list)

    def observe(self, request: ObservationRequest) -> ObservationResult:
        self.requests.append(request)
        return self.result
