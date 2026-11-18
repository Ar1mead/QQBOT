"""Runtime policy gates for adapter capability declarations.

The first platform integration stage permits observation only. Presentation and
external side effects require a future, separately reviewed policy path.
"""
from __future__ import annotations

from adapters.contracts.observation import AdapterManifest, CapabilityMode


def require_observation_only(manifest: AdapterManifest) -> None:
    """Reject any adapter manifest that declares presentation or side effects."""
    if not isinstance(manifest, AdapterManifest):
        raise TypeError("manifest must be an AdapterManifest")
    denied = [
        capability.name
        for capability in manifest.capabilities
        if capability.mode is not CapabilityMode.OBSERVE
    ]
    if denied:
        raise PermissionError(
            "adapter is restricted to observation; denied capabilities: "
            + ", ".join(sorted(denied))
        )
