"""Evidence-grounded motivation update proposals.

This module validates proposed signal changes against a trusted CSD snapshot.
It does not mutate signal state, determine semantic truth, or execute actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Sequence


EvidenceKind = Literal[
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
]
EvidenceOrigin = Literal[
    "internal_state", "user_request", "platform_recommendation",
    "external_opportunity", "self_commitment",
]
SignalKind = Literal["interest", "need", "curiosity", "commitment", "affect"]
SignalStatus = Literal["active", "paused", "resolved"]
MotivationOperation = Literal[
    "create", "reinforce", "weaken", "contextualize", "pause", "resolve"
]
InterestStage = Literal["tentative", "emerging", "contextual"]


@dataclass(frozen=True)
class MotivationEvidence:
    event_id: str
    encounter_id: str
    subject_ref: str
    evidence_kind: EvidenceKind
    origin: EvidenceOrigin
    occurred_at: str
    context: str
    meaningful_alternatives: bool = False


@dataclass(frozen=True)
class MotivationSignalState:
    signal_id: str
    version: int
    kind: SignalKind
    subject_ref: str
    scope: str
    status: SignalStatus
    origin_class: str
    supporting_event_ids: tuple[str, ...]
    counter_evidence_event_ids: tuple[str, ...] = ()
    statement: str = ""
    # CSD-derived summary: (encounter_id, representative_timestamp, supporting_event_id).
    voluntary_encounters: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class MotivationSnapshot:
    state_version: int
    evidence: tuple[MotivationEvidence, ...]
    signals: tuple[MotivationSignalState, ...]


@dataclass(frozen=True)
class MotivationUpdateProposal:
    proposal_id: str
    based_on_state_version: int
    operation: MotivationOperation
    kind: SignalKind
    subject_ref: str
    scope: str
    rationale: str
    supporting_event_ids: tuple[str, ...] = ()
    counter_evidence_event_ids: tuple[str, ...] = ()
    new_signal_id: str | None = None
    target_signal_id: str | None = None
    target_signal_version: int | None = None
    requested_interest_stage: InterestStage | None = None
    statement: str | None = None


@dataclass(frozen=True)
class ValidatedMotivationUpdate:
    proposal: MotivationUpdateProposal
    effective_statement: str
    derived_origin_class: str
    voluntary_encounter_ids: tuple[str, ...]
    emerging_interest_supported: bool


def _nonempty(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _unique(values: Sequence[str], name: str) -> set[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a sequence of strings")
    result: set[str] = set()
    for value in values:
        _nonempty(value, name)
        if value in result:
            raise ValueError(f"{name} contains duplicate values")
        result.add(value)
    return result


def _validate_timestamp(value: str) -> None:
    _nonempty(value, "occurred_at")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("occurred_at must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("occurred_at must include a timezone offset")


def _derive_origin(evidence: Sequence[MotivationEvidence]) -> str:
    origins = {item.origin for item in evidence}
    if origins and origins.issubset({"internal_state", "self_commitment"}):
        return "internally_initiated"
    if origins == {"user_request"}:
        return "user_requested_encounter"
    if origins and origins.issubset({"platform_recommendation", "external_opportunity"}):
        return "externally_exposed"
    return "mixed_origin"


def validate_motivation_update(
    snapshot: MotivationSnapshot,
    proposal: MotivationUpdateProposal,
) -> ValidatedMotivationUpdate:
    """Validate evidence lineage and update identity without accepting state."""
    if not isinstance(snapshot, MotivationSnapshot):
        raise TypeError("snapshot must be MotivationSnapshot")
    if not isinstance(proposal, MotivationUpdateProposal):
        raise TypeError("proposal must be MotivationUpdateProposal")
    if (
        not isinstance(snapshot.state_version, int)
        or isinstance(snapshot.state_version, bool)
        or snapshot.state_version < 0
    ):
        raise ValueError("snapshot state_version must be a non-negative integer")
    if (
        not isinstance(proposal.based_on_state_version, int)
        or isinstance(proposal.based_on_state_version, bool)
        or proposal.based_on_state_version != snapshot.state_version
    ):
        raise ValueError("motivation proposal is stale or has an invalid state version")

    _nonempty(proposal.proposal_id, "proposal_id")
    _nonempty(proposal.subject_ref, "subject_ref")
    _nonempty(proposal.scope, "scope")
    _nonempty(proposal.rationale, "rationale")

    evidence_by_id: dict[str, MotivationEvidence] = {}
    for item in snapshot.evidence:
        if not isinstance(item, MotivationEvidence):
            raise TypeError("snapshot evidence must contain MotivationEvidence values")
        _nonempty(item.event_id, "evidence.event_id")
        _nonempty(item.encounter_id, "evidence.encounter_id")
        _nonempty(item.subject_ref, "evidence.subject_ref")
        _nonempty(item.context, "evidence.context")
        _validate_timestamp(item.occurred_at)
        if item.event_id in evidence_by_id:
            raise ValueError(f"duplicate evidence event_id: {item.event_id}")
        if item.evidence_kind not in {
            "passive_exposure", "user_requested_action", "platform_autoplay",
            "voluntary_selection", "return_visit", "autonomous_question",
            "question_encountered", "need_condition", "commitment_accepted",
            "affect_observation", "counter_evidence", "resolution",
        }:
            raise ValueError(f"unsupported evidence kind: {item.evidence_kind}")
        if item.origin not in {
            "internal_state", "user_request", "platform_recommendation",
            "external_opportunity", "self_commitment",
        }:
            raise ValueError(f"unsupported evidence origin: {item.origin}")
        required_origins = {
            "user_requested_action": {"user_request"},
            "platform_autoplay": {"platform_recommendation"},
            "autonomous_question": {"internal_state"},
            "need_condition": {"internal_state"},
            "affect_observation": {"internal_state"},
        }
        allowed_forced_origins = required_origins.get(item.evidence_kind)
        if allowed_forced_origins is not None and item.origin not in allowed_forced_origins:
            raise ValueError(
                f"{item.evidence_kind} must use a source-derived origin from "
                f"{sorted(allowed_forced_origins)}"
            )
        if item.evidence_kind in {"voluntary_selection", "return_visit"} and item.origin != "internal_state":
            raise ValueError(
                f"{item.evidence_kind} requires internally initiated evidence; requests, recommendations, opportunities, and commitments are not independent interest choices"
            )
        if not isinstance(item.meaningful_alternatives, bool):
            raise ValueError("meaningful_alternatives must be boolean")
        evidence_by_id[item.event_id] = item

    signal_by_id: dict[str, MotivationSignalState] = {}
    for signal in snapshot.signals:
        if not isinstance(signal, MotivationSignalState):
            raise TypeError("snapshot signals must contain MotivationSignalState values")
        _nonempty(signal.signal_id, "signal.signal_id")
        _nonempty(signal.subject_ref, "signal.subject_ref")
        _nonempty(signal.scope, "signal.scope")
        _nonempty(signal.statement, "signal.statement")
        if signal.signal_id in signal_by_id:
            raise ValueError(f"duplicate signal_id: {signal.signal_id}")
        if not isinstance(signal.version, int) or isinstance(signal.version, bool) or signal.version < 1:
            raise ValueError("signal version must be a positive integer")
        if signal.kind not in {"interest", "need", "curiosity", "commitment", "affect"}:
            raise ValueError(f"unsupported signal kind: {signal.kind}")
        if signal.status not in {"active", "paused", "resolved"}:
            raise ValueError(f"unsupported signal status: {signal.status}")
        if signal.origin_class not in {
            "internally_initiated", "user_requested_encounter",
            "externally_exposed", "mixed_origin",
        }:
            raise ValueError(f"unsupported signal origin_class: {signal.origin_class}")
        prior_support = _unique(signal.supporting_event_ids, "signal.supporting_event_ids")
        prior_counter = _unique(signal.counter_evidence_event_ids, "signal.counter_evidence_event_ids")
        if prior_support & prior_counter:
            raise ValueError("stored signal support and counterevidence references overlap")
        if signal.voluntary_encounters and signal.kind != "interest":
            raise ValueError("only interest signals may carry voluntary-interest encounter summaries")
        seen_encounters: set[str] = set()
        seen_voluntary_event_ids: set[str] = set()
        for entry in signal.voluntary_encounters:
            if not isinstance(entry, (tuple, list)) or len(entry) != 3:
                raise ValueError("voluntary_encounters entries must contain encounter_id, timestamp, evidence_event_id")
            encounter_id, timestamp, event_id = entry
            _nonempty(encounter_id, "voluntary encounter_id")
            _validate_timestamp(timestamp)
            _nonempty(event_id, "voluntary evidence_event_id")
            if encounter_id in seen_encounters:
                raise ValueError("voluntary_encounters must have unique encounter IDs")
            if event_id not in prior_support:
                raise ValueError("voluntary encounter evidence must belong to signal supporting events")
            if event_id in seen_voluntary_event_ids:
                raise ValueError("one evidence event cannot represent multiple voluntary encounters")
            seen_encounters.add(encounter_id)
            seen_voluntary_event_ids.add(event_id)
        signal_by_id[signal.signal_id] = signal

    supporting_ids = _unique(proposal.supporting_event_ids, "supporting_event_ids")
    counter_ids = _unique(proposal.counter_evidence_event_ids, "counter_evidence_event_ids")
    if supporting_ids & counter_ids:
        raise ValueError("supporting and counterevidence references must be disjoint")
    referenced_ids = supporting_ids | counter_ids
    if not referenced_ids.issubset(evidence_by_id):
        raise ValueError("motivation proposal references unknown evidence")
    supporting = [evidence_by_id[item] for item in sorted(supporting_ids)]
    counter = [evidence_by_id[item] for item in sorted(counter_ids)]
    if any(
        item.subject_ref != proposal.subject_ref
        for item in supporting + counter
    ):
        raise ValueError("motivation evidence subject does not match proposal subject")
    if any(item.evidence_kind == "counter_evidence" for item in supporting):
        raise ValueError("counter_evidence must be referenced through counter_evidence_event_ids")
    if any(item.evidence_kind != "counter_evidence" for item in counter):
        raise ValueError("counter_evidence_event_ids must reference counter_evidence records")

    if proposal.kind not in {"interest", "need", "curiosity", "commitment", "affect"}:
        raise ValueError(f"unsupported motivation signal kind: {proposal.kind}")
    if proposal.operation not in {
        "create", "reinforce", "weaken", "contextualize", "pause", "resolve"
    }:
        raise ValueError(f"unsupported motivation operation: {proposal.operation}")

    target: MotivationSignalState | None = None
    if proposal.operation == "create":
        _nonempty(proposal.new_signal_id, "new_signal_id")
        _nonempty(proposal.statement, "statement")
        if proposal.new_signal_id in signal_by_id:
            raise ValueError("new_signal_id already exists")
        if proposal.target_signal_id is not None or proposal.target_signal_version is not None:
            raise ValueError("create operation cannot target an existing signal")
    else:
        if proposal.new_signal_id is not None:
            raise ValueError("update operation cannot assign a new_signal_id")
        if proposal.operation == "contextualize" and proposal.statement is not None:
            _nonempty(proposal.statement, "statement")
        _nonempty(proposal.target_signal_id, "target_signal_id")
        target = signal_by_id.get(proposal.target_signal_id)
        if target is None:
            raise ValueError("target signal does not exist")
        if (
            not isinstance(proposal.target_signal_version, int)
            or isinstance(proposal.target_signal_version, bool)
            or proposal.target_signal_version != target.version
        ):
            raise ValueError("target signal version is stale or invalid")
        if target.kind != proposal.kind or target.subject_ref != proposal.subject_ref:
            raise ValueError("update cannot change a signal's kind or subject identity")
        if proposal.operation != "contextualize" and proposal.statement is not None and proposal.statement != target.statement:
            raise ValueError("only contextualize may revise a signal statement")
        if proposal.operation != "contextualize" and proposal.scope != target.scope:
            raise ValueError("only contextualize may change a signal's scope")
        if target.status != "active":
            raise ValueError("only active signals can be updated by this operation")
        prior_evidence_ids = (
            set(target.supporting_event_ids) | set(target.counter_evidence_event_ids)
        )
        if referenced_ids & prior_evidence_ids:
            raise ValueError("signal update must cite new evidence not already attached to the target")

    if proposal.operation in {"create", "reinforce"} and not supporting:
        raise ValueError(f"{proposal.operation} requires supporting evidence")
    if proposal.operation == "weaken":
        if not counter:
            raise ValueError("weaken requires counterevidence")
        if supporting:
            raise ValueError("weaken must not include new supporting evidence")
    if proposal.operation == "contextualize" and not (supporting or counter):
        raise ValueError("contextualize requires supporting or counterevidence")
    if proposal.operation == "resolve":
        if not any(item.evidence_kind == "resolution" for item in supporting):
            raise ValueError("resolve requires explicit resolution evidence")
        if counter:
            raise ValueError("resolve cannot include counterevidence as its resolution basis")
    if proposal.operation == "pause" and (supporting or counter):
        raise ValueError("pause does not accept supporting or counterevidence")

    if proposal.kind == "interest":
        if proposal.requested_interest_stage not in {"tentative", "emerging", "contextual", None}:
            raise ValueError("established interest maturity is CSD-derived, not provider-assigned")
        if proposal.operation in {"create", "reinforce"}:
            if proposal.requested_interest_stage == "contextual":
                raise ValueError("contextual interest scope is only produced by contextualize")
            allowed_support = {
                "passive_exposure", "user_requested_action", "platform_autoplay",
                "voluntary_selection", "return_visit", "affect_observation",
            }
            if any(item.evidence_kind not in allowed_support for item in supporting):
                raise ValueError("interest evidence contains an incompatible evidence kind")
            voluntary = [
                item for item in supporting
                if item.evidence_kind in {"voluntary_selection", "return_visit"}
                and item.origin == "internal_state"
                and item.meaningful_alternatives
            ]
            distinct_encounters = {item.encounter_id for item in voluntary}
            distinct_times = {item.occurred_at for item in voluntary}
            if proposal.requested_interest_stage == "emerging" and (
                len(distinct_encounters) < 2 or len(distinct_times) < 2
            ):
                raise ValueError(
                    "emerging interest requires voluntary evidence from distinct, time-separated encounters"
                )
        elif proposal.operation == "contextualize":
            if proposal.requested_interest_stage is not None:
                raise ValueError("contextualize cannot assign an interest maturity stage")
            allowed_support = {
                "passive_exposure", "user_requested_action", "platform_autoplay",
                "voluntary_selection", "return_visit", "affect_observation",
            }
            if any(item.evidence_kind not in allowed_support for item in supporting):
                raise ValueError("interest contextualization contains an incompatible evidence kind")
        elif proposal.requested_interest_stage is not None:
            raise ValueError("interest stage can only be proposed for create/reinforce")
    elif proposal.requested_interest_stage is not None:
        raise ValueError("requested_interest_stage applies only to interest signals")

    required_kind = {
        "need": "need_condition",
        "curiosity": "autonomous_question",
        "commitment": "commitment_accepted",
        "affect": "affect_observation",
    }.get(proposal.kind)
    if required_kind and proposal.operation in {"create", "reinforce"}:
        if not any(item.evidence_kind == required_kind for item in supporting):
            raise ValueError(f"{proposal.kind} proposal requires {required_kind} evidence")

    if proposal.operation == "pause" and target is None:
        raise ValueError("pause requires an existing active signal")

    # Initial origin is derived from positive supporting evidence only.
    # Counterevidence can weaken or contextualize a hypothesis, but must not
    # rewrite the causal origin of the signal.
    origin_class = (
        target.origin_class if target is not None
        else _derive_origin(supporting)
    )
    effective_statement = (
        proposal.statement if proposal.operation == "create"
        else (proposal.statement if proposal.operation == "contextualize" and proposal.statement is not None
              else target.statement)
    )
    voluntary_evidence = [
        item for item in supporting
        if item.evidence_kind in {"voluntary_selection", "return_visit"}
        and item.origin == "internal_state"
        and item.meaningful_alternatives
    ]
    encounter_records: dict[str, tuple[str, str]] = {}
    if target is not None:
        encounter_records.update({
            entry[0]: (entry[1], entry[2])
            for entry in target.voluntary_encounters
        })
    for encounter_id in sorted({item.encounter_id for item in voluntary_evidence}):
        candidates = [
            item for item in voluntary_evidence if item.encounter_id == encounter_id
        ]
        earliest = min(candidates, key=lambda item: (item.occurred_at, item.event_id))
        encounter_records.setdefault(
            encounter_id, (earliest.occurred_at, earliest.event_id)
        )
    voluntary_encounter_ids = tuple(sorted(encounter_records))
    emerging_supported = (
        proposal.kind == "interest"
        and len(voluntary_encounter_ids) >= 2
        and len({item[0] for item in encounter_records.values()}) >= 2
    )
    return ValidatedMotivationUpdate(
        proposal=proposal,
        effective_statement=effective_statement,
        derived_origin_class=origin_class,
        voluntary_encounter_ids=voluntary_encounter_ids,
        emerging_interest_supported=emerging_supported,
    )
