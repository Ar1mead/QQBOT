"""CSD-owned motivation event projections and decision path.

This mixin is used by CognitiveMemoryStore so motivation state shares the same
append-only event stream, transaction boundary, and Recovery implementation
as cognitive memories. It does not invoke models or external adapters.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid
from typing import Any, Mapping


INTERACTION_EVENT = "experience.interaction_choice_recorded.v1"
MOTIVATION_PROPOSAL_EVENT = "motivation.signal_update_proposed.v1"
MOTIVATION_DECISION_EVENT = "motivation.signal_update_decided.v1"
MOTIVATION_POLICY_ID = "csd.motivation-signal-provenance"
MOTIVATION_POLICY_VERSION = "0.1"
MOTIVATION_DECISION_SOURCE = "csd.authority.v1"

_EVIDENCE_KINDS = {
    "passive_exposure",
    "user_requested_action",
    "platform_autoplay",
    "voluntary_selection",
    "return_visit",
    "autonomous_question",
    "question_encountered",
    "need_condition",
    "commitment_accepted",
    "affect_observation",
    "counter_evidence",
    "resolution",
}
_EVIDENCE_ORIGINS = {
    "internal_state",
    "user_request",
    "platform_recommendation",
    "external_opportunity",
    "self_commitment",
}
_SIGNAL_KINDS = {"interest", "need", "curiosity", "commitment", "affect"}
_OPERATIONS = {"create", "reinforce", "weaken", "contextualize", "pause", "resolve"}
_DECISION_OUTCOMES = {"accepted", "rejected", "deferred", "needs_more_evidence"}


def _m_nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _m_string_list(value: Any, name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list of strings")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        _m_nonempty(item, name)
        if item in seen:
            raise ValueError(f"{name} must not contain duplicates")
        seen.add(item)
        result.append(item)
    return result


def _m_timestamp(value: str, name: str) -> None:
    _m_nonempty(value, name)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone offset")


class CognitiveMotivationMixin:
    """Methods mixed into CognitiveMemoryStore; all writes use its transaction."""

    def _raise_cognitive_integrity(self, message: str) -> None:
        raise RuntimeError(message)

    @staticmethod
    def _motivation_origin_class(evidence: list[dict[str, Any]]) -> str:
        origins = {item["origin"] for item in evidence}
        if origins and origins.issubset({"internal_state", "self_commitment"}):
            return "internally_initiated"
        if origins == {"user_request"}:
            return "user_requested_encounter"
        if origins and origins.issubset({"platform_recommendation", "external_opportunity"}):
            return "externally_exposed"
        return "mixed_origin"

    def _validate_interaction_event(
        self,
        db: Any,
        event: Any,
        *,
        current_sequence: int,
    ) -> None:
        payload = event.payload
        allowed = {
            "encounter_id", "subject_ref", "evidence_kind", "origin", "context",
            "meaningful_alternatives", "choice_set_refs", "selected_ref",
            "origin_event_id", "related_event_id", "adapter", "session_scope",
        }
        if set(payload) != allowed:
            raise ValueError("interaction payload contains missing or unsupported fields")

        _m_nonempty(payload.get("encounter_id"), "interaction.encounter_id")
        _m_nonempty(payload.get("subject_ref"), "interaction.subject_ref")
        _m_nonempty(payload.get("context"), "interaction.context")
        _m_nonempty(payload.get("session_scope"), "interaction.session_scope")

        kind = _m_nonempty(payload.get("evidence_kind"), "interaction.evidence_kind")
        origin = _m_nonempty(payload.get("origin"), "interaction.origin")
        if kind not in _EVIDENCE_KINDS:
            raise ValueError(f"unsupported interaction evidence_kind: {kind}")
        if origin not in _EVIDENCE_ORIGINS:
            raise ValueError(f"unsupported interaction origin: {origin}")

        adapter = payload.get("adapter")
        if not isinstance(adapter, Mapping) or set(adapter) != {"component", "version"}:
            raise ValueError("interaction.adapter must contain component and version")
        component = _m_nonempty(adapter.get("component"), "interaction.adapter.component")
        _m_nonempty(adapter.get("version"), "interaction.adapter.version")
        if event.source != f"interaction-adapter:{component}":
            raise ValueError("interaction event source/adapter mismatch")

        meaningful = payload.get("meaningful_alternatives")
        if not isinstance(meaningful, bool):
            raise ValueError("meaningful_alternatives must be boolean")
        choice_set = _m_string_list(payload.get("choice_set_refs"), "choice_set_refs")
        selected = payload.get("selected_ref")
        if selected is not None:
            _m_nonempty(selected, "selected_ref")
        origin_event_id = payload.get("origin_event_id")
        related_event_id = payload.get("related_event_id")
        if origin_event_id is not None:
            _m_nonempty(origin_event_id, "origin_event_id")
        if related_event_id is not None:
            _m_nonempty(related_event_id, "related_event_id")

        required_origins = {
            "user_requested_action": {"user_request"},
            "platform_autoplay": {"platform_recommendation"},
            "autonomous_question": {"internal_state"},
            "need_condition": {"internal_state"},
            "affect_observation": {"internal_state"},
            "resolution": {"internal_state"},
        }
        expected = required_origins.get(kind)
        if expected is not None and origin not in expected:
            raise ValueError(f"{kind} requires origin in {sorted(expected)}")

        if kind in {"user_requested_action", "platform_autoplay"}:
            if origin_event_id is None:
                raise ValueError(f"{kind} requires origin_event_id")
        if kind == "commitment_accepted":
            if origin not in {"user_request", "self_commitment"}:
                raise ValueError("commitment_accepted must preserve user_request or self_commitment origin")
            if origin_event_id is None:
                raise ValueError("commitment_accepted requires origin_event_id")
        if origin in {"user_request", "platform_recommendation", "external_opportunity", "self_commitment"}:
            if origin_event_id is None:
                raise ValueError(f"{origin} evidence requires origin_event_id")
        if origin_event_id is not None:
            row = db.execute(
                "SELECT sequence FROM events WHERE event_id=?", (origin_event_id,)
            ).fetchone()
            if row is None or int(row["sequence"]) >= current_sequence:
                raise ValueError("origin_event_id must reference an earlier durable event")

        if kind in {"voluntary_selection", "return_visit"}:
            if origin != "internal_state":
                raise ValueError(f"{kind} must have internal_state origin")
            if not meaningful or len(choice_set) < 2:
                raise ValueError(f"{kind} requires a meaningful choice set of at least two items")
            if selected is None or selected not in choice_set:
                raise ValueError(f"{kind} selected_ref must be present in choice_set_refs")
        elif meaningful:
            raise ValueError("meaningful_alternatives is reserved for voluntary selection evidence")

        if kind == "return_visit":
            if related_event_id is None:
                raise ValueError("return_visit requires related_event_id")
        elif related_event_id is not None:
            raise ValueError("related_event_id is only supported for return_visit")

        if related_event_id is not None:
            row = db.execute(
                "SELECT sequence,event_type,source,payload_ref FROM events WHERE event_id=?",
                (related_event_id,),
            ).fetchone()
            if (
                row is None
                or row["event_type"] != INTERACTION_EVENT
                or int(row["sequence"]) >= current_sequence
            ):
                raise ValueError("related_event_id must reference an earlier interaction event")
            prior = self.get_event(related_event_id)["payload"]
            if prior.get("subject_ref") != payload["subject_ref"]:
                raise ValueError("return_visit must relate to the same subject")
            if prior.get("selected_ref") != selected:
                raise ValueError("return_visit must relate to the same selected item")

        if kind == "autonomous_question":
            if origin != "internal_state" or selected is not None or choice_set:
                raise ValueError("autonomous_question must be an internal question, not a selection")
        if kind == "question_encountered" and origin == "internal_state":
            raise ValueError("internally generated questions must use autonomous_question")
        if kind in {"need_condition", "affect_observation"} and origin != "internal_state":
            raise ValueError(f"{kind} must be internally observed")
        if kind == "passive_exposure" and selected is not None and origin == "internal_state":
            raise ValueError("internal item selection must use voluntary_selection")
        if kind == "voluntary_selection" and related_event_id is not None:
            raise ValueError("voluntary_selection does not use related_event_id")

    def _motivation_evidence(self, event_id: str) -> dict[str, Any]:
        event = self.get_event(event_id)
        if event["event_type"] != INTERACTION_EVENT:
            raise ValueError(f"motivation evidence is not an interaction event: {event_id}")
        payload = event["payload"]
        return {
            "event_id": event_id,
            "encounter_id": payload["encounter_id"],
            "subject_ref": payload["subject_ref"],
            "evidence_kind": payload["evidence_kind"],
            "origin": payload["origin"],
            "occurred_at": event["occurred_at"],
            "context": payload["context"],
            "meaningful_alternatives": payload["meaningful_alternatives"],
            "choice_set_refs": payload["choice_set_refs"],
            "selected_ref": payload["selected_ref"],
        }

    def _validate_motivation_proposal(
        self,
        db: Any,
        event: Any,
        *,
        current_sequence: int,
    ) -> None:
        payload = event.payload
        allowed = {
            "proposal_id", "operation", "kind", "subject_ref", "scope", "statement",
            "supporting_event_ids", "counter_evidence_event_ids", "new_signal_id",
            "target_signal_id", "target_signal_version", "requested_interest_stage",
            "rationale", "origin", "based_on",
        }
        if set(payload) != allowed:
            raise ValueError("motivation proposal contains missing or unsupported fields")

        _m_nonempty(payload.get("proposal_id"), "proposal_id")
        operation = _m_nonempty(payload.get("operation"), "operation")
        kind = _m_nonempty(payload.get("kind"), "kind")
        subject_ref = _m_nonempty(payload.get("subject_ref"), "subject_ref")
        scope = _m_nonempty(payload.get("scope"), "scope")
        _m_nonempty(payload.get("rationale"), "rationale")
        if operation not in _OPERATIONS:
            raise ValueError(f"unsupported motivation operation: {operation}")
        if kind not in _SIGNAL_KINDS:
            raise ValueError(f"unsupported motivation kind: {kind}")

        origin = payload.get("origin")
        if not isinstance(origin, Mapping) or set(origin) != {"component", "version"}:
            raise ValueError("motivation proposal origin must contain component and version")
        _m_nonempty(origin.get("component"), "origin.component")
        _m_nonempty(origin.get("version"), "origin.version")
        if event.source != f"motivation-proposal:{origin['component']}":
            raise ValueError("motivation proposal source/origin mismatch")

        based_on = payload.get("based_on")
        if not isinstance(based_on, Mapping) or set(based_on) != {"state_version"}:
            raise ValueError("motivation proposal based_on must contain state_version")
        version = based_on.get("state_version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise ValueError("based_on.state_version must be a non-negative integer")

        supporting_ids = _m_string_list(payload.get("supporting_event_ids"), "supporting_event_ids")
        counter_ids = _m_string_list(payload.get("counter_evidence_event_ids"), "counter_evidence_event_ids")
        if set(supporting_ids) & set(counter_ids):
            raise ValueError("supporting and counterevidence event IDs must be disjoint")
 
        statement = payload.get("statement")
        if operation == "create":
            _m_nonempty(payload.get("new_signal_id"), "new_signal_id")
            _m_nonempty(statement, "statement")
            if payload.get("target_signal_id") is not None or payload.get("target_signal_version") is not None:
                raise ValueError("create cannot target an existing signal")
        else:
            if payload.get("new_signal_id") is not None:
                raise ValueError("updates cannot supply new_signal_id")
            _m_nonempty(payload.get("target_signal_id"), "target_signal_id")
            target_version = payload.get("target_signal_version")
            if (
                not isinstance(target_version, int)
                or isinstance(target_version, bool)
                or target_version < 1
            ):
                raise ValueError("target_signal_version must be a positive integer")
            if operation != "contextualize" and statement is not None:
                raise ValueError("only contextualize may supply a replacement statement")
            if operation == "contextualize" and statement is not None:
                _m_nonempty(statement, "statement")

        requested_stage = payload.get("requested_interest_stage")
        if kind == "interest":
            if requested_stage not in {"tentative", "emerging", "contextual", None}:
                raise ValueError("interest maturity must be CSD-derived")
            if operation == "contextualize" and requested_stage is not None:
                raise ValueError("contextualize cannot assign an interest maturity stage")
            if operation != "contextualize" and requested_stage == "contextual":
                raise ValueError("contextual interest scope is only produced by contextualize")
        elif requested_stage is not None:
            raise ValueError("requested_interest_stage applies only to interest")

        if operation in {"create", "reinforce"} and not supporting_ids:
            raise ValueError(f"{operation} requires supporting evidence")
        if operation == "weaken" and (not counter_ids or supporting_ids):
            raise ValueError("weaken requires only counterevidence")
        if operation == "contextualize" and not (supporting_ids or counter_ids):
            raise ValueError("contextualize requires supporting or counterevidence")
        if operation == "resolve" and counter_ids:
            raise ValueError("resolve cannot use counterevidence as its resolution basis")
        if operation == "pause" and (supporting_ids or counter_ids):
            raise ValueError("pause does not accept evidence in this prototype")
        if operation == "resolve" and not supporting_ids:
            raise ValueError("resolve requires resolution evidence")

        evidence: list[dict[str, Any]] = []
        for evidence_id in supporting_ids + counter_ids:
            row = db.execute(
                "SELECT sequence,event_type FROM events WHERE event_id=?", (evidence_id,)
            ).fetchone()
            if row is None or row["event_type"] != INTERACTION_EVENT:
                raise ValueError(f"evidence must reference an earlier interaction event: {evidence_id}")
            if int(row["sequence"]) >= current_sequence:
                raise ValueError("motivation evidence must precede its proposal event")
            item = self._motivation_evidence(evidence_id)
            if item["subject_ref"] != subject_ref:
                raise ValueError("motivation evidence subject does not match proposal subject")
            evidence.append(item)

        supporting = evidence[:len(supporting_ids)]
        counter = evidence[len(supporting_ids):]
        if any(item["evidence_kind"] == "counter_evidence" for item in supporting):
            raise ValueError("counter_evidence must be in counter_evidence_event_ids")
        if any(item["evidence_kind"] != "counter_evidence" for item in counter):
            raise ValueError("counter_evidence_event_ids must reference counter_evidence events")

        if kind == "interest":
            if operation in {"create", "reinforce"}:
                allowed_support = {
                    "passive_exposure", "user_requested_action", "platform_autoplay",
                    "voluntary_selection", "return_visit", "affect_observation",
                }
                if any(item["evidence_kind"] not in allowed_support for item in supporting):
                    raise ValueError("interest proposal contains incompatible supporting evidence")
        required_kind = {
            "need": "need_condition",
            "curiosity": "autonomous_question",
            "commitment": "commitment_accepted",
            "affect": "affect_observation",
        }.get(kind)
        if required_kind and operation in {"create", "reinforce"}:
            if not any(item["evidence_kind"] == required_kind for item in supporting):
                raise ValueError(f"{kind} requires {required_kind} evidence")
        if operation == "resolve":
            if not any(item["evidence_kind"] == "resolution" for item in supporting):
                raise ValueError("resolve requires a resolution evidence event")

        if operation == "create":
            existing = db.execute(
                "SELECT 1 FROM motivation_signals WHERE signal_id=?",
                (payload["new_signal_id"],),
            ).fetchone()
            if existing is not None:
                raise ValueError("new motivation signal identity already exists")
        else:
            target = db.execute(
                "SELECT signal_version,signal_json FROM motivation_signals WHERE signal_id=?",
                (payload["target_signal_id"],),
            ).fetchone()
            if target is None:
                raise ValueError("motivation update references an unknown signal")
            target_state = json.loads(target["signal_json"])
            if target_state["kind"] != kind or target_state["subject_ref"] != subject_ref:
                raise ValueError("motivation update cannot change signal kind or subject")
            if target_state["status"] != "active":
                raise ValueError("only active motivation signals can be updated")
            old_evidence = set(target_state["supporting_event_ids"]) | set(target_state["counter_evidence_event_ids"])
            if (set(supporting_ids) | set(counter_ids)) & old_evidence:
                raise ValueError("motivation update must reference new evidence")
            if operation != "contextualize":
                if statement is not None and statement != target_state["statement"]:
                    raise ValueError("only contextualize may change signal statement")
                if scope != target_state["scope"]:
                    raise ValueError("only contextualize may change signal scope")

    def _prepare_motivation_decision(
        self,
        db: Any,
        proposal_id: str,
        *,
        current_state_version: int,
        decision_time: str,
    ) -> dict[str, Any]:
        row = db.execute(
            "SELECT proposal_json,proposal_event_id,status,decision_event_id "
            "FROM motivation_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row["decision_event_id"] is not None:
            return {"outcome": "already_decided"}
        proposal = json.loads(row["proposal_json"])
        proposal_event = db.execute(
            "SELECT sequence,correlation_id FROM events WHERE event_id=?",
            (row["proposal_event_id"],),
        ).fetchone()
        if proposal_event is None:
            self._raise_cognitive_integrity("motivation proposal event is missing")
        based_on_version = proposal["based_on"]["state_version"]
        if based_on_version != current_state_version:
            return {
                "outcome": "deferred",
                "reason": f"stale proposal state_version={based_on_version}; current state_version={current_state_version}",
                "signal": None,
                "evidence_event_ids": proposal["supporting_event_ids"] + proposal["counter_evidence_event_ids"],
            }
        if proposal["operation"] == "create":
            duplicate_signal = db.execute(
                "SELECT 1 FROM motivation_signals WHERE signal_id=?",
                (proposal["new_signal_id"],),
            ).fetchone()
            if duplicate_signal is not None:
                return {
                    "outcome": "rejected",
                    "reason": "new signal identity was accepted by another proposal",
                    "signal": None,
                    "evidence_event_ids": proposal["supporting_event_ids"] + proposal["counter_evidence_event_ids"],
                }

        supporting_ids = proposal["supporting_event_ids"]
        counter_ids = proposal["counter_evidence_event_ids"]
        support = [self._motivation_evidence(item) for item in supporting_ids]
        counter = [self._motivation_evidence(item) for item in counter_ids]
        evidence = support + counter
        if any(item["subject_ref"] != proposal["subject_ref"] for item in evidence):
            self._raise_cognitive_integrity("motivation evidence subject changed after proposal")
        current_target = None
        if proposal["operation"] != "create":
            target = db.execute(
                "SELECT signal_version,signal_json FROM motivation_signals WHERE signal_id=?",
                (proposal["target_signal_id"],),
            ).fetchone()
            if target is None:
                return {
                    "outcome": "deferred",
                    "reason": "target signal is no longer available",
                    "signal": None,
                    "evidence_event_ids": supporting_ids + counter_ids,
                }
            current_target = json.loads(target["signal_json"])
            if current_target["signal_version"] != proposal["target_signal_version"]:
                return {
                    "outcome": "deferred",
                    "reason": "target signal version changed after proposal",
                    "signal": None,
                    "evidence_event_ids": supporting_ids + counter_ids,
                }

        origin_class = (
            current_target["origin_class"]
            if current_target is not None
            else self._motivation_origin_class(evidence)
        )
        signal_id = (
            current_target["signal_id"]
            if current_target is not None
            else proposal["new_signal_id"]
        )
        signal_version = (
            current_target["signal_version"] + 1
            if current_target is not None
            else 1
        )
        new_support = list(supporting_ids)
        new_counter = list(counter_ids)
        if current_target is not None:
            new_support = list(dict.fromkeys(current_target["supporting_event_ids"] + new_support))
            new_counter = list(dict.fromkeys(current_target["counter_evidence_event_ids"] + new_counter))
        statement = (
            proposal["statement"] if proposal["operation"] == "create"
            else (proposal["statement"] if proposal["operation"] == "contextualize" and proposal["statement"] is not None
                  else current_target["statement"])
        )
        scope = (
            proposal["scope"] if proposal["operation"] in {"create", "contextualize"}
            else current_target["scope"]
        )
        status = {
            "pause": "paused",
            "resolve": "resolved",
        }.get(proposal["operation"], "active")

        voluntary: dict[str, dict[str, str]] = {}
        if current_target is not None:
            for entry in current_target["voluntary_encounters"]:
                voluntary[entry["encounter_id"]] = {
                    "occurred_at": entry["occurred_at"],
                    "event_id": entry["event_id"],
                }
        if proposal["kind"] == "interest":
            for item in support:
                if (
                    item["evidence_kind"] in {"voluntary_selection", "return_visit"}
                    and item["origin"] == "internal_state"
                    and item["meaningful_alternatives"]
                    and item["selected_ref"] is not None
                ):
                    voluntary.setdefault(item["encounter_id"], {
                        "occurred_at": item["occurred_at"],
                        "event_id": item["event_id"],
                    })

        time_points = {item["occurred_at"] for item in voluntary.values()}
        if proposal["operation"] == "contextualize" or (
            current_target is not None and current_target.get("interest_stage") == "contextual"
        ):
            interest_stage = "contextual"
        elif len(voluntary) >= 2 and len(time_points) >= 2:
            interest_stage = "emerging"
        elif current_target is not None and current_target.get("interest_stage") == "emerging":
            interest_stage = "emerging"
        else:
            interest_stage = "tentative"

        signal = {
            "signal_id": signal_id,
            "signal_version": signal_version,
            "kind": proposal["kind"],
            "subject_ref": proposal["subject_ref"],
            "scope": scope,
            "statement": statement,
            "status": status,
            "origin_class": origin_class,
            "supporting_event_ids": new_support,
            "counter_evidence_event_ids": new_counter,
            "voluntary_encounters": [
                {
                    "encounter_id": encounter_id,
                    "occurred_at": value["occurred_at"],
                    "event_id": value["event_id"],
                }
                for encounter_id, value in sorted(voluntary.items())
            ],
            "interest_stage": interest_stage if proposal["kind"] == "interest" else None,
            "created_at": (
                current_target["created_at"] if current_target is not None
                else self.get_event(row["proposal_event_id"])["occurred_at"]
            ),
            "updated_at": decision_time,
            "proposal_id": proposal_id,
            "proposal_event_id": row["proposal_event_id"],
            "previous_signal_version": (
                current_target["signal_version"] if current_target is not None else None
            ),
        }
        return {
            "outcome": "accepted",
            "reason": "motivation signal proposal passed CSD provenance and lifecycle checks",
            "signal": signal,
            "evidence_event_ids": supporting_ids + counter_ids,
        }

    def _apply_motivation_decision(self, db: Any, event: Any) -> None:
        payload = event.payload
        proposal_id = _m_nonempty(payload.get("proposal_id"), "decision.proposal_id")
        proposal = db.execute(
            "SELECT proposal_event_id,decision_event_id FROM motivation_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if proposal is None:
            self._raise_cognitive_integrity("motivation decision references missing proposal")
        if proposal["decision_event_id"] is not None:
            self._raise_cognitive_integrity("motivation proposal has more than one decision")
        if payload.get("proposal_event_id") != proposal["proposal_event_id"]:
            self._raise_cognitive_integrity("motivation decision proposal event mismatch")

        event_row = db.execute(
            "SELECT sequence FROM events WHERE event_id=?", (event.event_id,)
        ).fetchone()
        if event_row is None:
            self._raise_cognitive_integrity("motivation decision event is missing from history")
        sequence = int(event_row["sequence"])
        current_version = self._authoritative_state_version(
            db, through_sequence=sequence - 1
        )
        version = payload.get("evaluated_state_version")
        if not isinstance(version, int) or isinstance(version, bool) or version != current_version:
            self._raise_cognitive_integrity("motivation decision evaluated against stale state_version")

        prior_motivation_decisions = self._accepted_transition_count(
            db, {MOTIVATION_DECISION_EVENT}, through_sequence=sequence - 1
        )
        projected_versions = int(db.execute(
            "SELECT COUNT(*) FROM motivation_signal_versions"
        ).fetchone()[0])
        if prior_motivation_decisions != projected_versions:
            self._raise_cognitive_integrity("motivation signal version projection is out of sync")

        prepared = self._prepare_motivation_decision(
            db, proposal_id,
            current_state_version=current_version,
            decision_time=event.occurred_at,
        )
        expected = {
            "proposal_id": proposal_id,
            "proposal_event_id": proposal["proposal_event_id"],
            "outcome": prepared["outcome"],
            "policy": {"id": MOTIVATION_POLICY_ID, "version": MOTIVATION_POLICY_VERSION},
            "evidence_event_ids": prepared.get("evidence_event_ids", []),
            "signal": prepared.get("signal"),
            "transition_id": payload.get("transition_id"),
            "reason": prepared.get("reason", "already decided"),
            "evaluated_state_version": current_version,
        }
        allowed_payload_fields = {
            "proposal_id", "proposal_event_id", "outcome", "policy",
            "evidence_event_ids", "signal", "transition_id", "reason",
            "evaluated_state_version",
        }
        if set(payload) != allowed_payload_fields:
            self._raise_cognitive_integrity("motivation decision contains missing or unsupported fields")
        for key, value in expected.items():
            if payload.get(key) != value:
                self._raise_cognitive_integrity(f"motivation decision {key} does not match CSD evaluation")
        outcome = prepared["outcome"]
        if outcome not in _DECISION_OUTCOMES:
            self._raise_cognitive_integrity("invalid motivation decision outcome")

        transition_id = payload.get("transition_id")
        if outcome == "accepted":
            if transition_id != f"csd-motivation-transition:{proposal_id}":
                self._raise_cognitive_integrity("motivation transition_id does not match proposal identity")
            signal = prepared["signal"]
            signal_json = json.dumps(
                signal, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            )
            try:
                db.execute(
                    "INSERT INTO motivation_signal_versions(signal_id,signal_version,decision_event_id,transition_id,signal_json) VALUES (?,?,?,?,?)",
                    (signal["signal_id"], signal["signal_version"], event.event_id, transition_id, signal_json),
                )
                db.execute(
                    "INSERT INTO motivation_signals(signal_id,signal_version,decision_event_id,transition_id,signal_json) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(signal_id) DO UPDATE SET signal_version=excluded.signal_version,decision_event_id=excluded.decision_event_id,transition_id=excluded.transition_id,signal_json=excluded.signal_json",
                    (signal["signal_id"], signal["signal_version"], event.event_id, transition_id, signal_json),
                )
            except Exception as exc:
                self._raise_cognitive_integrity(f"motivation signal projection update failed: {exc}")
        elif transition_id is not None or payload.get("signal") is not None:
            self._raise_cognitive_integrity("non-accepted motivation decision cannot contain a transition")

        db.execute(
            "UPDATE motivation_proposals SET status=?,decision_event_id=? WHERE proposal_id=?",
            (outcome, event.event_id, proposal_id),
        )

    def _apply_motivation_projection_event(
        self,
        db: Any,
        event: Any,
        sequence: int,
        *,
        internal: bool,
    ) -> None:
        if event.event_type == INTERACTION_EVENT:
            self._validate_interaction_event(db, event, current_sequence=sequence)
            return
        if event.event_type == MOTIVATION_PROPOSAL_EVENT:
            if internal:
                raise ValueError("motivation proposal events must use public Event Submit")
            payload_json = json.dumps(
                dict(event.payload), ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            )
            import hashlib
            digest = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
            proposal_id = _m_nonempty(event.payload.get("proposal_id"), "proposal_id")
            existing = db.execute(
                "SELECT proposal_digest FROM motivation_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if existing is not None:
                if existing["proposal_digest"] != digest:
                    raise ValueError("motivation proposal identity conflict")
                # Same immutable proposal under a second event ID is a duplicate
                # lifecycle submission, even if its target has since changed.
                return
            self._validate_motivation_proposal(db, event, current_sequence=sequence)
            db.execute(
                "INSERT INTO motivation_proposals(proposal_id,proposal_digest,proposal_event_id,proposal_json,status,decision_event_id) VALUES (?,?,?,?, 'pending',NULL)",
                (proposal_id, digest, event.event_id, payload_json),
            )
            return
        if event.event_type == MOTIVATION_DECISION_EVENT:
            if not internal or event.source != MOTIVATION_DECISION_SOURCE:
                self._raise_cognitive_integrity("non-authoritative motivation decision event")
            self._apply_motivation_decision(db, event)
            return
        self._raise_cognitive_integrity(f"unhandled motivation event type at sequence {sequence}")

    def evaluate_motivation_proposal(self, proposal_id: str) -> dict[str, Any]:
        """CSD authority path: evaluate a pending motivation proposal without a model."""
        _m_nonempty(proposal_id, "proposal_id")
        from .cognitive import CognitiveEvent

        with self._tx() as db:
            row = db.execute(
                "SELECT proposal_event_id,decision_event_id FROM motivation_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            if row["decision_event_id"] is not None:
                return {"status": "already_decided", "decision_event_id": row["decision_event_id"]}

            current_version = self._authoritative_state_version(db)
            self._assert_accepted_projection_consistent()
            self._assert_motivation_projection_consistent()
            now = datetime.now(timezone.utc).isoformat()
            prepared = self._prepare_motivation_decision(
                db, proposal_id,
                current_state_version=current_version,
                decision_time=now,
            )
            decision_no = int(db.execute(
                "SELECT COUNT(*) FROM events WHERE event_type=?",
                (MOTIVATION_DECISION_EVENT,),
            ).fetchone()[0]) + 1
            decision_event_id = f"csd-motivation-decision:{proposal_id}:{decision_no}"
            outcome = prepared["outcome"]
            transition_id = f"csd-motivation-transition:{proposal_id}" if outcome == "accepted" else None
            decision_payload = {
                "proposal_id": proposal_id,
                "proposal_event_id": row["proposal_event_id"],
                "outcome": outcome,
                "policy": {"id": MOTIVATION_POLICY_ID, "version": MOTIVATION_POLICY_VERSION},
                "evidence_event_ids": prepared.get("evidence_event_ids", []),
                "signal": prepared.get("signal"),
                "transition_id": transition_id,
                "reason": prepared.get("reason", "motivation proposal already decided"),
                "evaluated_state_version": current_version,
            }
            event = CognitiveEvent(
                event_id=decision_event_id,
                occurred_at=now,
                correlation_id=f"motivation-proposal:{proposal_id}",
                event_type=MOTIVATION_DECISION_EVENT,
                source=MOTIVATION_DECISION_SOURCE,
                payload=decision_payload,
            )
            payload_json = self._validate_event(event, internal=True)
            appended = self._append_event_in_transaction(db, event, payload_json, internal=True)
            return {
                "status": outcome,
                "decision_event_id": decision_event_id,
                "sequence": appended["sequence"],
                "reason": prepared.get("reason"),
            }

    def get_motivation_proposal(self, proposal_id: str) -> dict[str, Any]:
        _m_nonempty(proposal_id, "proposal_id")
        row = self._db.execute(
            "SELECT proposal_json,proposal_digest,proposal_event_id,status,decision_event_id "
            "FROM motivation_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        payload = json.loads(row["proposal_json"])
        import hashlib
        digest = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest()
        if digest != row["proposal_digest"]:
            self._raise_cognitive_integrity("motivation proposal projection digest mismatch")
        return {
            "proposal": payload,
            "proposal_digest": "sha256:" + row["proposal_digest"],
            "proposal_event_id": row["proposal_event_id"],
            "status": row["status"],
            "decision_event_id": row["decision_event_id"],
        }

    def get_motivation_signals(self) -> list[dict[str, Any]]:
        self._assert_motivation_projection_consistent()
        rows = self._db.execute(
            "SELECT signal_json FROM motivation_signals ORDER BY rowid"
        ).fetchall()
        return [json.loads(row["signal_json"]) for row in rows]

    def get_motivation_signal(self, signal_id: str) -> dict[str, Any]:
        self._assert_motivation_projection_consistent()
        _m_nonempty(signal_id, "signal_id")
        row = self._db.execute(
            "SELECT signal_json FROM motivation_signals WHERE signal_id=?",
            (signal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(signal_id)
        return json.loads(row["signal_json"])

    def _assert_motivation_projection_consistent(self) -> None:
        expected = self._accepted_transition_count(self._db, {MOTIVATION_DECISION_EVENT})
        versions = int(self._db.execute(
            "SELECT COUNT(*) FROM motivation_signal_versions"
        ).fetchone()[0])
        signals = int(self._db.execute(
            "SELECT COUNT(*) FROM motivation_signals"
        ).fetchone()[0])
        distinct = int(self._db.execute(
            "SELECT COUNT(DISTINCT signal_id) FROM motivation_signal_versions"
        ).fetchone()[0])
        if expected != versions or signals != distinct:
            self._raise_cognitive_integrity("motivation signal projection is out of sync; run Recovery")
        mismatches = int(self._db.execute(
            "SELECT COUNT(*) FROM motivation_signals s "
            "LEFT JOIN motivation_signal_versions v "
            "ON v.signal_id=s.signal_id AND v.signal_version=s.signal_version "
            "WHERE v.signal_id IS NULL OR v.signal_json<>s.signal_json "
            "OR v.decision_event_id<>s.decision_event_id "
            "OR v.transition_id<>s.transition_id"
        ).fetchone()[0])
        latest_mismatches = int(self._db.execute(
            "SELECT COUNT(*) FROM motivation_signals s "
            "JOIN (SELECT signal_id,MAX(signal_version) AS max_version "
            "FROM motivation_signal_versions GROUP BY signal_id) v "
            "ON v.signal_id=s.signal_id WHERE s.signal_version<>v.max_version"
        ).fetchone()[0])
        if mismatches or latest_mismatches:
            self._raise_cognitive_integrity("latest motivation signal projection differs from version history; run Recovery")

    @staticmethod
    def _accepted_transition_count(
        db: Any,
        event_types: set[str],
        *,
        through_sequence: int | None = None,
    ) -> int:
        if not event_types:
            return 0
        types = sorted(event_types)
        placeholders = ",".join("?" for _ in types)
        query = (
            f"SELECT p.payload_json FROM events e JOIN payloads p ON p.payload_ref=e.payload_ref "
            f"WHERE e.event_type IN ({placeholders})"
        )
        params: list[Any] = list(types)
        if through_sequence is not None:
            query += " AND e.sequence<=?"
            params.append(through_sequence)
        query += " ORDER BY e.sequence"
        count = 0
        for row in db.execute(query, params).fetchall():
            payload = json.loads(row["payload_json"])
            if payload.get("outcome") == "accepted":
                count += 1
        return count
