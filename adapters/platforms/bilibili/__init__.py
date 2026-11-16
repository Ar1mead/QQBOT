"""Bilibili adapter primitives. Real network access is intentionally not wired yet."""

from .target import BilibiliTarget, parse_bilibili_target

__all__ = ["BilibiliTarget", "parse_bilibili_target"]
