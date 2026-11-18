"""SurfCore-to-CSD integration primitives (no live transport)."""

from .mapping import (
    ADAPTER_VERSION,
    SCHEMA_VERSION,
    SurfCoreQQBatch,
    bilibili_manifest,
    map_surfcore_qq_batch,
    map_surfcore_record,
    map_surfcore_record_to_csd_event,
    qq_manifest,
)

__all__ = [
    "ADAPTER_VERSION",
    "SCHEMA_VERSION",
    "SurfCoreQQBatch",
    "bilibili_manifest",
    "map_surfcore_qq_batch",
    "map_surfcore_record",
    "map_surfcore_record_to_csd_event",
    "qq_manifest",
]
