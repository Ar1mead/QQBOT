"""Bilibili adapter primitives. Real network access is intentionally not wired yet."""

from .manifest import BILIBILI_MANIFEST
from .target import BilibiliTarget, parse_bilibili_target

__all__ = ["BILIBILI_MANIFEST", "BilibiliTarget", "parse_bilibili_target"]
