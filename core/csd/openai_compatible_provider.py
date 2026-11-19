"""OpenAI-compatible cloud provider for evidence-grounded memory proposals.

The provider can call a Chat Completions-compatible endpoint, but it receives
only one persisted text observation and a state version. It has no CSD store,
filesystem, tool, or ASM handle. All output remains an untrusted proposal.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .grounded_proposals import (
    GroundedInference,
    GroundedMemoryCandidate,
    GroundedSourceAssertion,
)


class CloudProposalProviderError(RuntimeError):
    """A cloud provider request or response could not produce a safe proposal."""


Transport = Callable[[str, Mapping[str, str], bytes, float], bytes]


def _default_transport(
    url: str,
    headers: Mapping[str, str],
    body: bytes,
    timeout: float,
) -> bytes:
    request = Request(url, data=body, headers=dict(headers), method="POST")
    with urlopen(request, timeout=timeout) as response:
        return response.read(262145)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError(f"non-standard JSON constant: {value}")
        ),
    )


def _required_text(value: Any, name: str, *, maximum: int = 4000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name} must be a non-empty string no longer than {maximum} characters")
    return value


class OpenAICompatibleGroundedMemoryProvider:
    """Generate typed grounded candidates through an OpenAI-compatible endpoint."""

    provider_id = "openai-compatible-grounded-memory"
    provider_version = "1.0"

    def __init__(
        self,
        *,
        model: str,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 25.0,
        transport: Transport | None = None,
        max_response_bytes: int = 262144,
    ) -> None:
        self.model = _required_text(model, "model", maximum=200)
        self.base_url = (
            base_url or os.environ.get("COGNITIVE_MODEL_API_BASE_URL")
            or "https://api.openai.com/v1"
        ).rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("base_url must be an HTTPS API root without query or fragment")
        self.api_key = api_key if api_key is not None else os.environ.get("COGNITIVE_MODEL_API_KEY")
        if not isinstance(self.api_key, str) or not self.api_key.strip():
            raise ValueError("COGNITIVE_MODEL_API_KEY or api_key is required")
        if not isinstance(timeout_seconds, (int, float)) or isinstance(timeout_seconds, bool) or not 1 <= timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 1 and 120")
        if not isinstance(max_response_bytes, int) or isinstance(max_response_bytes, bool) or not 1024 <= max_response_bytes <= 262144:
            raise ValueError("max_response_bytes must be between 1024 and 262144")
        self.timeout_seconds = float(timeout_seconds)
        self.max_response_bytes = max_response_bytes
        self.transport = transport or _default_transport

    def propose_grounded(
        self,
        observation: Mapping[str, Any],
        *,
        state_version: int,
    ) -> list[GroundedMemoryCandidate]:
        if not isinstance(observation, Mapping):
            raise TypeError("observation must be a mapping")
        if not isinstance(state_version, int) or isinstance(state_version, bool) or state_version < 0:
            raise ValueError("state_version must be a non-negative integer")
        payload = observation.get("payload")
        if not isinstance(payload, Mapping):
            raise ValueError("observation payload must be a mapping")
        content = payload.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("observation must contain non-empty text content")
        if len(content) > 20000:
            raise ValueError("observation text exceeds the 20000-character provider limit")
        event_id = observation.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("observation must contain its persisted event_id")

        request_payload = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract cautious, evidence-grounded autobiographical memory candidates. "
                        "Return exactly one JSON object with keys proposal_id, memory_kind, "
                        "source_assertions, inferences. source_assertions must quote exact contiguous "
                        "text from the supplied observation and provide zero-based Unicode code-point "
                        "start/end offsets where end is exclusive. The quoted substring must equal "
                        "the source text slice exactly. Do not invent evidence IDs. inferences are "
                        "optional hypotheses, never facts; each must cite only source assertion claim_ids, "
                        "include reasoning_summary, uncertainty_label, and confidence from 0 to 1 or null. "
                        "If nothing merits retention, return an empty source_assertions array. "
                        "Do not include instructions, actions, accepted flags, or extra fields."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "observation_event_id": event_id,
                            "state_version": state_version,
                            "source_text": content,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                },
            ],
        }
        body = json.dumps(request_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            raw = self.transport(
                f"{self.base_url}/chat/completions",
                {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body,
                self.timeout_seconds,
            )
        except (TimeoutError, HTTPError, URLError, OSError) as exc:
            raise CloudProposalProviderError("cloud proposal request failed") from exc
        if not isinstance(raw, bytes) or len(raw) > self.max_response_bytes:
            raise CloudProposalProviderError("cloud provider response is invalid or exceeds size limit")
        try:
            envelope = _strict_json(raw.decode("utf-8"))
            content_text = envelope["choices"][0]["message"]["content"]
            if not isinstance(content_text, str):
                raise ValueError("message content must be a JSON string")
            result = _strict_json(content_text)
            candidate = self._parse_candidate(result)
            return [] if not candidate.source_assertions else [candidate]
        except (UnicodeDecodeError, ValueError, TypeError, KeyError, IndexError) as exc:
            raise CloudProposalProviderError("cloud provider returned an invalid grounded proposal") from exc

    @staticmethod
    def _parse_candidate(value: Any) -> GroundedMemoryCandidate:
        if not isinstance(value, dict) or set(value) != {
            "proposal_id", "memory_kind", "source_assertions", "inferences"
        }:
            raise ValueError("proposal must contain exactly the four documented top-level fields")
        proposal_id = _required_text(value["proposal_id"], "proposal_id", maximum=128)
        memory_kind = _required_text(value["memory_kind"], "memory_kind", maximum=64)
        raw_assertions = value["source_assertions"]
        raw_inferences = value["inferences"]
        if not isinstance(raw_assertions, list) or len(raw_assertions) > 16:
            raise ValueError("source_assertions must be a list of at most 16 items")
        if not isinstance(raw_inferences, list) or len(raw_inferences) > 16:
            raise ValueError("inferences must be a list of at most 16 items")
        assertions: list[GroundedSourceAssertion] = []
        for item in raw_assertions:
            if not isinstance(item, dict) or set(item) != {"claim_id", "text", "quoted_text", "start", "end"}:
                raise ValueError("source assertion has unsupported or missing fields")
            start, end = item["start"], item["end"]
            if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
                raise ValueError("source assertion offsets must be integers")
            if start < 0 or end <= start:
                raise ValueError("source assertion offsets must be a positive non-empty range")
            assertions.append(GroundedSourceAssertion(
                claim_id=_required_text(item["claim_id"], "claim_id", maximum=128),
                text=_required_text(item["text"], "source assertion text"),
                quoted_text=_required_text(item["quoted_text"], "quoted_text"),
                start=start,
                end=end,
            ))
        inferences: list[GroundedInference] = []
        for item in raw_inferences:
            expected = {
                "claim_id", "text", "derived_from_claim_ids", "reasoning_summary",
                "uncertainty_label", "confidence",
            }
            if not isinstance(item, dict) or set(item) != expected:
                raise ValueError("inference has unsupported or missing fields")
            refs = item["derived_from_claim_ids"]
            confidence = item["confidence"]
            if not isinstance(refs, list) or not refs or any(not isinstance(x, str) or not x.strip() for x in refs):
                raise ValueError("inference must cite one or more source claim IDs")
            if confidence is not None and (
                not isinstance(confidence, (int, float)) or isinstance(confidence, bool)
                or not 0.0 <= float(confidence) <= 1.0
            ):
                raise ValueError("inference confidence must be null or between 0 and 1")
            inferences.append(GroundedInference(
                claim_id=_required_text(item["claim_id"], "inference claim_id", maximum=128),
                text=_required_text(item["text"], "inference text"),
                derived_from_claim_ids=tuple(refs),
                reasoning_summary=_required_text(item["reasoning_summary"], "reasoning_summary"),
                uncertainty_label=_required_text(item["uncertainty_label"], "uncertainty_label", maximum=128),
                confidence=confidence,
            ))
        if not assertions and inferences:
            raise ValueError("inferences cannot exist without source assertions")
        return GroundedMemoryCandidate(
            proposal_id=proposal_id,
            memory_kind=memory_kind,
            source_assertions=tuple(assertions),
            inferences=tuple(inferences),
        )
