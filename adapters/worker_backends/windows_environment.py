"""Explicit, allowlisted Unicode environment block for Windows workers."""
from __future__ import annotations

import ctypes
import ntpath
from collections.abc import Mapping
from dataclasses import dataclass


MAX_ENVIRONMENT_CHARACTERS = 32767
ALLOWED_ENVIRONMENT_KEYS = frozenset(
    {
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "PATH",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONNOUSERSITE",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONSAFEPATH",
    }
)
REQUIRED_ENVIRONMENT_KEYS = frozenset({"SYSTEMROOT", "WINDIR", "TEMP", "TMP"})


@dataclass(frozen=True)
class WorkerEnvironment:
    """Own the exact UTF-16 environment block passed to CreateProcessW."""

    values: tuple[tuple[str, str], ...]
    block_text: str
    buffer: ctypes.Array

    @property
    def pointer(self):
        return ctypes.cast(self.buffer, ctypes.c_void_p)

    def validate_for_launch(self) -> None:
        rebuilt = build_worker_environment(dict(self.values))
        if rebuilt.block_text != self.block_text:
            raise ValueError("worker environment metadata and text block do not match")
        actual = ctypes.wstring_at(ctypes.addressof(self.buffer), len(self.block_text))
        if actual != self.block_text:
            raise ValueError("worker environment native buffer does not match its validated text")


def build_worker_environment(values: Mapping[str, str]) -> WorkerEnvironment:
    """Build a minimal double-NUL-terminated environment block.

    The caller must supply only trusted, host-selected paths. Unknown keys are
    rejected rather than inherited. Names are canonicalized to uppercase and
    sorted case-insensitively as required for a Windows environment block.
    """
    if not isinstance(values, Mapping):
        raise TypeError("environment values must be a mapping")

    normalized: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key or "=" in key or "\x00" in key:
            raise ValueError("environment variable names must be non-empty and contain no '=' or NUL")
        canonical = key.upper()
        if canonical not in ALLOWED_ENVIRONMENT_KEYS:
            raise ValueError(f"environment variable is not allowlisted: {key}")
        if canonical in normalized:
            raise ValueError(f"duplicate environment variable after case normalization: {key}")
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError(f"environment value for {key} must be a NUL-free string")
        if not value:
            raise ValueError(f"environment value for {key} must not be empty")
        normalized[canonical] = value

    missing = REQUIRED_ENVIRONMENT_KEYS - normalized.keys()
    if missing:
        raise ValueError(f"missing required environment variables: {', '.join(sorted(missing))}")

    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
        if not ntpath.isabs(normalized[key]):
            raise ValueError(f"{key} must be an absolute Windows path")

    # These flags prevent user-site imports, bytecode writes, and implicit CWD
    # prepending. The runtime and package paths still must be pinned by the host.
    required_python_flags = {
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONSAFEPATH": "1",
    }
    for key, value in required_python_flags.items():
        if key in normalized and normalized[key] != value:
            raise ValueError(f"{key} must be exactly {value}")
        normalized[key] = value

    ordered = tuple(sorted(normalized.items(), key=lambda item: item[0].casefold()))
    block_text = "\x00".join(f"{key}={value}" for key, value in ordered) + "\x00\x00"
    if len(block_text) > MAX_ENVIRONMENT_CHARACTERS:
        raise ValueError("worker environment block exceeds Windows' 32767-character limit")

    # Allocate exactly the characters in the double-NUL block; do not append
    # an extra implicit terminator to the block passed to CreateProcessW.
    buffer_type = ctypes.c_wchar * len(block_text)
    buffer = buffer_type(*block_text)
    return WorkerEnvironment(values=ordered, block_text=block_text, buffer=buffer)
