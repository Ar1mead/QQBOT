"""Bilibili's initial capability declaration: target validation only.

This is not a live Bilibili client. No HTTP, cookies, account access, downloads,
comment posting, likes, follows, or other external actions are implemented.
"""
from __future__ import annotations

from adapters.contracts.observation import (
    AdapterManifest,
    Capability,
    CapabilityMode,
)
from adapters.policy import require_observation_only


BILIBILI_MANIFEST = AdapterManifest(
    adapter_id="bilibili.read_only",
    adapter_version="0.1.0",
    platform="bilibili",
    capabilities=(
        Capability(
            name="validate_video_target",
            mode=CapabilityMode.OBSERVE,
            description=(
                "Accept a canonical BV identifier as a target reference; "
                "this capability does not fetch or access platform data."
            ),
        ),
    ),
    observation_schema_versions=(2,),
)

require_observation_only(BILIBILI_MANIFEST)
