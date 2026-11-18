"""Host-side validation for SurfCore adapter result metadata.

This module is deliberately independent of the worker process and CSD store.
The caller supplies the checkpoint it used to construct the worker request.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SurfCoreQQResultMetadata:
    stream_ref: str
    after_cursor: int
    proposed_cursor: int


def validate_surfcore_qq_result_metadata(
    result_metadata: Mapping[str, Any] | tuple[tuple[str, Any], ...],
    *,
    expected_stream_ref: str,
    expected_after_cursor: int,
) -> SurfCoreQQResultMetadata:
    """Validate the exact QQ cursor result against the host's request checkpoint.

    This validates metadata only. The caller must durably submit every returned
    observation to CSD before persisting proposed_cursor.
    """
    if not isinstance(expected_stream_ref, str) or not expected_stream_ref.strip():
        raise ValueError("expected_stream_ref must be a non-empty string")
    if (
        isinstance(expected_after_cursor, bool)
        or not isinstance(expected_after_cursor, int)
        or expected_after_cursor < 0
    ):
        raise ValueError("expected_after_cursor must be a non-negative integer")

    if isinstance(result_metadata, Mapping):
        metadata = dict(result_metadata)
    elif isinstance(result_metadata, tuple):
        metadata = {}
        for item in result_metadata:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError("result_metadata entries must be key/value pairs")
            key, value = item
            if key in metadata:
                raise ValueError("result_metadata contains duplicate keys")
            metadata[key] = value
    else:
        raise TypeError("result_metadata must be a mapping or immutable key/value tuple")

    expected_keys = {"stream_ref", "after_cursor", "proposed_cursor"}
    if set(metadata) != expected_keys:
        raise ValueError("SurfCore QQ result metadata fields do not match the exact schema")

    stream_ref = metadata["stream_ref"]
    after_cursor = metadata["after_cursor"]
    proposed_cursor = metadata["proposed_cursor"]
    if not isinstance(stream_ref, str) or stream_ref != expected_stream_ref:
        raise ValueError("SurfCore QQ stream_ref does not match the host request")
    for name, value in (("after_cursor", after_cursor), ("proposed_cursor", proposed_cursor)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"SurfCore QQ {name} must be a non-negative integer")
    if after_cursor != expected_after_cursor:
        raise ValueError("SurfCore QQ after_cursor does not match the host checkpoint")
    if proposed_cursor < after_cursor:
        raise ValueError("SurfCore QQ proposed_cursor cannot move backwards")

    return SurfCoreQQResultMetadata(
        stream_ref=stream_ref,
        after_cursor=after_cursor,
        proposed_cursor=proposed_cursor,
    )
