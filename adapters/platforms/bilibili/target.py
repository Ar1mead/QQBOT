"""Strict Bilibili target parsing for the initial read-only stage.

Only canonical BV identifiers are accepted. URLs, short links, local paths,
IP addresses, and arbitrary hosts are rejected before they reach an extractor.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

_BVID_RE = re.compile(r"^BV[0-9A-Za-z]{10}$")


@dataclass(frozen=True)
class BilibiliTarget:
    bvid: str

    def __post_init__(self) -> None:
        if not isinstance(self.bvid, str) or not _BVID_RE.fullmatch(self.bvid):
            raise ValueError("bvid must be a canonical 12-character BV identifier")


def parse_bilibili_target(value: str) -> BilibiliTarget:
    if not isinstance(value, str):
        raise ValueError("Bilibili target must be a BV identifier string")
    candidate = value.strip()
    if not _BVID_RE.fullmatch(candidate):
        raise ValueError("only canonical BV identifiers are accepted; URLs and paths are disabled")
    return BilibiliTarget(candidate)
