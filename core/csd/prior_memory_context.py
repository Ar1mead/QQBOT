"""Versioned, bounded selector for accepted autobiographical memories."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

CONTEXT_SCHEMA_VERSION = 1
SELECTOR_ALGORITHM_VERSION = "unicode-lexical-overlap-v1"
DEFAULT_MAX_ITEMS = 8
DEFAULT_PER_ITEM_CHARS = 1200
DEFAULT_TOTAL_CHARS = 8000


class PriorMemoryContextError(ValueError):
    """An accepted-memory record cannot be represented safely in context."""


def _tokens(value: str) -> set[str]:
    result: set[str] = set()
    for run in re.findall(r"[a-z0-9]+|[\u3400-\u9fff]+", value.casefold()):
        if re.fullmatch(r"[a-z0-9]+", run):
            if len(run) >= 2:
                result.add(run)
        elif len(run) == 1:
            result.add(run)
        else:
            result.update(run[i:i + 2] for i in range(len(run) - 1))
    return result


def _required(value: Any, field: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise PriorMemoryContextError(f"{field} must be non-empty text up to {maximum} characters")
    return value


def _memory_text(memory: Mapping[str, Any]) -> str:
    parts: list[str] = []
    if isinstance(memory.get("content"), str):
        parts.append(memory["content"])
    claims = memory.get("claims", [])
    if not isinstance(claims, list):
        raise PriorMemoryContextError("memory claims must be a list")
    for claim in claims:
        if not isinstance(claim, Mapping):
            raise PriorMemoryContextError("memory claim must be an object")
        if isinstance(claim.get("text"), str):
            parts.append(claim["text"])
    return "\n".join(parts)


def _record(memory: Mapping[str, Any], text_limit: int) -> dict[str, Any]:
    if memory.get("status") != "accepted":
        raise PriorMemoryContextError("only accepted memories may enter prior context")
    claims = memory.get("claims", [])
    if not isinstance(claims, list):
        raise PriorMemoryContextError("memory claims must be a list")
    bounded_claims = []
    was_truncated = False
    for claim in claims[:32]:
        if not isinstance(claim, Mapping):
            raise PriorMemoryContextError("memory claim must be an object")
        uncertainty = claim.get("uncertainty")
        if uncertainty is not None and not isinstance(uncertainty, Mapping):
            raise PriorMemoryContextError("claim uncertainty must be an object or null")
        label = uncertainty.get("label") if uncertainty is not None else None
        confidence = uncertainty.get("confidence") if uncertainty is not None else None
        if label is not None and not isinstance(label, str):
            raise PriorMemoryContextError("uncertainty label must be text")
        if confidence is not None and (
            not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
            or not 0 <= confidence <= 1
        ):
            raise PriorMemoryContextError("uncertainty confidence must be between 0 and 1")
        evidence = claim.get("evidence", [])
        if not isinstance(evidence, list):
            raise PriorMemoryContextError("claim evidence must be a list")
        provenance = []
        for item in evidence[:16]:
            if not isinstance(item, Mapping):
                raise PriorMemoryContextError("evidence provenance must be an object")
            locator = item.get("locator")
            if locator is not None and not isinstance(locator, Mapping):
                raise PriorMemoryContextError("evidence locator must be an object or null")
            safe_locator = None
            if locator is not None:
                safe_locator = {
                    key: locator[key] for key in ("kind", "unit", "start", "end")
                    if key in locator and isinstance(locator[key], (str, int))
                    and not isinstance(locator[key], bool)
                }
            quoted = item.get("quoted_text")
            if isinstance(quoted, str) and len(quoted) > text_limit:
                was_truncated = True
            provenance.append({
                "event_id": _required(item.get("event_id"), "evidence event_id"),
                "locator": safe_locator,
                "quoted_text": quoted[:text_limit] if isinstance(quoted, str) else None,
            })
        claim_text = claim.get("text", "")
        if not isinstance(claim_text, str):
            raise PriorMemoryContextError("claim text must be text")
        was_truncated = was_truncated or len(claim_text) > text_limit
        was_truncated = was_truncated or len(claims) > 32 or len(evidence) > 16
        reasoning = claim.get("reasoning_summary", "")
        if not isinstance(reasoning, str):
            reasoning = ""
        was_truncated = was_truncated or len(reasoning) > text_limit
        bounded_claims.append({
            "claim_id": _required(claim.get("claim_id"), "claim_id"),
            "text": claim_text[:text_limit],
            "epistemic_type": claim.get("epistemic_type") if isinstance(
                claim.get("epistemic_type"), str
            ) else "unspecified",
            "uncertainty": {"label": label, "confidence": confidence} if uncertainty is not None else None,
            "derived_from_claim_ids": list(claim.get("derived_from_claim_ids", []))[:32]
                if isinstance(claim.get("derived_from_claim_ids", []), list) else [],
            "reasoning_summary": reasoning[:text_limit],
            "evidence": provenance,
        })
    content = memory.get("content", "")
    if not isinstance(content, str):
        content = ""
    evidence_ids = memory.get("evidence_event_ids", [])
    if not isinstance(evidence_ids, list):
        raise PriorMemoryContextError("evidence_event_ids must be a list")
    was_truncated = was_truncated or len(content) > text_limit
    was_truncated = was_truncated or len(evidence_ids) > 32
    created_at = _required(memory.get("created_at"), "created_at", 128)
    try:
        parsed_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if parsed_time.tzinfo is None:
            parsed_time = parsed_time.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError) as exc:
        raise PriorMemoryContextError("created_at must be a valid ISO-8601 timestamp") from exc
    return {
        "memory_id": _required(memory.get("memory_id"), "memory_id"),
        "proposal_id": _required(memory.get("proposal_id"), "proposal_id"),
        "created_at": created_at,
        "memory_kind": _required(memory.get("memory_kind"), "memory_kind", 128),
        "content": content[:text_limit],
        "claims": bounded_claims,
        "evidence_event_ids": [_required(item, "evidence_event_id") for item in evidence_ids[:32]],
        "truncated": was_truncated,
    }


def _encoded_size(value: Mapping[str, Any]) -> int:
    return len(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _timestamp_rank(value: str) -> float:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _truncate_record(record: dict[str, Any], existing: list[dict[str, Any]],
                     existing_truncated_ids: list[str], state_version: int,
                     total_chars: int) -> dict[str, Any] | None:
    text_total = len(record["content"]) + sum(len(claim["text"]) for claim in record["claims"])
    low, high, best = 0, text_total, None
    while low <= high:
        budget = (low + high) // 2
        candidate = json.loads(json.dumps(record, ensure_ascii=False))
        remaining = budget
        candidate["content"] = record["content"][:remaining]
        remaining -= len(candidate["content"])
        for index, claim in enumerate(candidate["claims"]):
            claim["text"] = record["claims"][index]["text"][:max(0, remaining)]
            remaining -= len(claim["text"])
        candidate["truncated"] = True
        trial = {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "selector_algorithm": SELECTOR_ALGORITHM_VERSION,
            "state_version": state_version,
            "historical_text_is_untrusted": True,
            "memories": existing + [candidate],
            "truncated_memory_ids": existing_truncated_ids + [candidate["memory_id"]],
        }
        if _encoded_size(trial) <= total_chars:
            best = candidate
            low = budget + 1
        else:
            high = budget - 1
    return best


def build_prior_memory_context(
    memories: Sequence[Mapping[str, Any]],
    observation_text: str,
    *,
    state_version: int,
    max_items: int = DEFAULT_MAX_ITEMS,
    per_item_chars: int = DEFAULT_PER_ITEM_CHARS,
    total_chars: int = DEFAULT_TOTAL_CHARS,
) -> dict[str, Any]:
    """Select by lexical overlap; this is not semantic retrieval."""
    if not isinstance(observation_text, str):
        raise TypeError("observation_text must be text")
    if not isinstance(state_version, int) or isinstance(state_version, bool) or state_version < 0:
        raise ValueError("state_version must be a non-negative integer")
    for name, value, minimum, maximum in (
        ("max_items", max_items, 1, 32),
        ("per_item_chars", per_item_chars, 32, 8192),
        ("total_chars", total_chars, 256, 32768),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}")
    if not isinstance(memories, Sequence) or isinstance(memories, (str, bytes)):
        raise TypeError("memories must be a sequence")
    query_tokens = _tokens(observation_text)
    seen: dict[str, str] = {}
    ranked = []
    for raw in memories:
        if not isinstance(raw, Mapping):
            raise PriorMemoryContextError("memory must be an object")
        record = _record(raw, per_item_chars)
        memory_id = record["memory_id"]
        fingerprint = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if memory_id in seen:
            if seen[memory_id] != fingerprint:
                raise PriorMemoryContextError("duplicate memory_id has conflicting content")
            continue
        seen[memory_id] = fingerprint
        score = len(query_tokens.intersection(_tokens(_memory_text(raw))))
        if score:
            record["relevance_score"] = score
            ranked.append((score, record["created_at"], memory_id, record))
    ranked.sort(key=lambda item: (-item[0], -_timestamp_rank(item[1]), item[2]))
    selected: list[dict[str, Any]] = []
    truncated_ids: list[str] = []
    for _, _, _, record in ranked:
        if len(selected) >= max_items:
            break
        trial = {
            "schema_version": CONTEXT_SCHEMA_VERSION,
            "selector_algorithm": SELECTOR_ALGORITHM_VERSION,
            "state_version": state_version,
            "historical_text_is_untrusted": True,
            "memories": selected + [record],
            "truncated_memory_ids": truncated_ids,
        }
        if _encoded_size(trial) <= total_chars:
            selected.append(record)
            if record["truncated"]:
                truncated_ids.append(record["memory_id"])
            continue
        shortened = _truncate_record(record, selected, truncated_ids, state_version, total_chars)
        if shortened is not None:
            selected.append(shortened)
            truncated_ids.append(shortened["memory_id"])
            break
    result = {
        "schema_version": CONTEXT_SCHEMA_VERSION,
        "selector_algorithm": SELECTOR_ALGORITHM_VERSION,
        "state_version": state_version,
        "historical_text_is_untrusted": True,
        "memories": selected,
        "truncated_memory_ids": truncated_ids,
    }
    if _encoded_size(result) > total_chars:
        raise PriorMemoryContextError("context metadata exceeds total character budget")
    return result
