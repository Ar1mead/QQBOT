"""Typed, provider-neutral contracts for autonomous motivation and choice.

This package creates deliberation proposals only. It does not own durable state,
call models, execute activities, or grant capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Sequence


SignalKind = Literal["need", "interest", "curiosity", "affect", "commitment", "opportunity"]
SignalOriginClass = Literal[
    "internally_initiated",
    "user_requested_encounter",
    "externally_exposed",
    "mixed_origin",
]
InterestStage = Literal["tentative", "emerging", "contextual"]
SideEffectLevel = Literal["none", "read_only", "external_side_effect"]
Disposition = Literal[
    "start_activity",
    "continue_activity",
    "wait",
    "request_information",
    "pause_goal",
    "abandon_goal",
    "revise_goal",
    "decline",
    "stop_activity",
    "no_op",
]


@dataclass(frozen=True)
class MotivationSignal:
    signal_id: str
    signal_version: int
    kind: SignalKind
    origin_class: SignalOriginClass
    subject_ref: str
    description: str
    supporting_event_ids: tuple[str, ...]
    counter_evidence_event_ids: tuple[str, ...] = ()
    active: bool = True
    scope: str = "general"
    interest_stage: InterestStage | None = None
    # CSD-derived (encounter_id, occurrence timestamp, supporting event ID).
    voluntary_encounters: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True)
class GoalState:
    goal_id: str
    desired_condition: str
    status: Literal["active", "paused", "blocked"]
    evidence_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActiveActivityState:
    activity_id: str
    required_capability: str
    permission_granted: bool
    stop_condition_met: bool
    side_effect_level: SideEffectLevel


@dataclass(frozen=True)
class ActivityOption:
    """A capability-filtered option supplied by trusted runtime/CSD context.

    The deliberator may select an option by ID. It cannot create its own
    permission flag, capability grant, or prerequisite result.
    """

    activity_id: str
    activity_kind: str
    description: str
    source_signal_ids: tuple[str, ...]
    serves_goal_ids: tuple[str, ...]
    required_capability: str
    permission_granted: bool
    prerequisites_satisfied: bool
    side_effect_level: SideEffectLevel


@dataclass(frozen=True)
class LifeSnapshot:
    state_version: int
    signals: tuple[MotivationSignal, ...]
    goals: tuple[GoalState, ...]
    activity_options: tuple[ActivityOption, ...]
    active_activity_ids: tuple[str, ...] = ()
    active_activity_states: tuple[ActiveActivityState, ...] = ()


@dataclass(frozen=True)
class GoalProposal:
    goal_id: str
    desired_condition: str
    origin_signal_ids: tuple[str, ...]
    rationale: str
    success_condition: str
    stop_condition: str
    review_condition: str


@dataclass(frozen=True)
class ChoiceProposal:
    disposition: Disposition
    rationale: str
    considered_activity_ids: tuple[str, ...] = ()
    activity_id: str | None = None
    goal_id: str | None = None
    active_activity_id: str | None = None
    evidence_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DeliberationProposal:
    based_on_state_version: int
    goal_proposals: tuple[GoalProposal, ...]
    choice: ChoiceProposal


@dataclass(frozen=True)
class ValidatedLifeProposal:
    """Validated proposal plus derived origin classifications.

    This is still untrusted proposed state. Only the CSD sink may persist an
    authoritative transition from it.
    """

    proposal: DeliberationProposal
    goal_origin_classes: tuple[tuple[str, str], ...]
    # Exact signal versions resolved from the same trusted CSD snapshot.
    goal_origin_signal_versions: tuple[tuple[str, tuple[tuple[str, int], ...]], ...]
    requires_asm_governance: bool


def _unique_nonempty(values: Sequence[str], field_name: str) -> set[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence, not a string")
    result: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must contain non-empty strings")
        if value in result:
            raise ValueError(f"{field_name} must not contain duplicates")
        result.add(value)
    return result


def validate_life_proposal(
    snapshot: LifeSnapshot,
    proposal: DeliberationProposal,
) -> ValidatedLifeProposal:
    """Validate references and hard admissibility; never rank or execute options."""
    if not isinstance(snapshot, LifeSnapshot):
        raise TypeError("snapshot must be LifeSnapshot")
    if not isinstance(proposal, DeliberationProposal):
        raise TypeError("deliberator must return DeliberationProposal")
    if not isinstance(snapshot.state_version, int) or isinstance(snapshot.state_version, bool) or snapshot.state_version < 0:
        raise ValueError("snapshot.state_version must be a non-negative integer")
    if proposal.based_on_state_version != snapshot.state_version:
        raise ValueError("proposal was generated from a stale or different state version")

    signal_by_id: dict[str, MotivationSignal] = {}
    for signal in snapshot.signals:
        if not isinstance(signal, MotivationSignal):
            raise TypeError("snapshot signals must be MotivationSignal values")
        if not signal.signal_id or not signal.signal_id.strip():
            raise ValueError("signal_id must be non-empty")
        if not isinstance(signal.signal_version, int) or isinstance(signal.signal_version, bool) or signal.signal_version < 1:
            raise ValueError("signal_version must be a positive integer")
        if signal.signal_id in signal_by_id:
            raise ValueError(f"duplicate signal_id: {signal.signal_id}")
        if signal.kind not in {"need", "interest", "curiosity", "affect", "commitment", "opportunity"}:
            raise ValueError(f"unsupported signal kind: {signal.kind}")
        if signal.origin_class not in {
            "internally_initiated", "user_requested_encounter",
            "externally_exposed", "mixed_origin",
        }:
            raise ValueError(f"unsupported signal origin_class: {signal.origin_class}")
        if not isinstance(signal.subject_ref, str) or not signal.subject_ref.strip():
            raise ValueError("signal subject_ref must be non-empty")
        if not isinstance(signal.description, str) or not signal.description.strip():
            raise ValueError("signal description must be non-empty")
        if not isinstance(signal.scope, str) or not signal.scope.strip():
            raise ValueError("signal scope must be non-empty")
        if not isinstance(signal.active, bool):
            raise ValueError("signal.active must be boolean")
        support_ids = _unique_nonempty(signal.supporting_event_ids, "signal.supporting_event_ids")
        counter_ids = _unique_nonempty(
            signal.counter_evidence_event_ids, "signal.counter_evidence_event_ids"
        )
        if support_ids & counter_ids:
            raise ValueError("signal support and counterevidence references must be disjoint")
        if not isinstance(signal.voluntary_encounters, (tuple, list)):
            raise ValueError("voluntary_encounters must be a sequence")
        if signal.kind == "interest":
            if signal.interest_stage is not None and signal.interest_stage not in {
                "tentative", "emerging", "contextual"
            }:
                raise ValueError("unsupported CSD-derived interest stage")
        elif signal.interest_stage is not None or signal.voluntary_encounters:
            raise ValueError("only interest signals may carry interest maturity/encounter summaries")
        seen_encounters: set[str] = set()
        seen_events: set[str] = set()
        timestamps: set[datetime] = set()
        for entry in signal.voluntary_encounters:
            if not isinstance(entry, (tuple, list)) or len(entry) != 3:
                raise ValueError("voluntary_encounters entries must contain encounter_id, timestamp, event_id")
            encounter_id, timestamp, event_id = entry
            if not isinstance(encounter_id, str) or not encounter_id.strip():
                raise ValueError("voluntary encounter_id must be non-empty")
            if not isinstance(timestamp, str) or not timestamp.strip():
                raise ValueError("voluntary encounter timestamp must be non-empty")
            try:
                parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("voluntary encounter timestamp must be ISO-8601") from exc
            if parsed_timestamp.tzinfo is None or parsed_timestamp.utcoffset() is None:
                raise ValueError("voluntary encounter timestamp must include a timezone")
            if not isinstance(event_id, str) or not event_id.strip():
                raise ValueError("voluntary encounter event_id must be non-empty")
            if encounter_id in seen_encounters or event_id in seen_events:
                raise ValueError("voluntary encounter IDs and evidence event IDs must be unique")
            if event_id not in support_ids:
                raise ValueError("voluntary encounter evidence must be in supporting event IDs")
            seen_encounters.add(encounter_id)
            seen_events.add(event_id)
            timestamps.add(parsed_timestamp.astimezone(timezone.utc))
        if signal.interest_stage == "emerging" and (
            len(seen_encounters) < 2 or len(timestamps) < 2
        ):
            raise ValueError("emerging interest requires two distinct time-separated voluntary encounters")
        signal_by_id[signal.signal_id] = signal

    goal_by_id: dict[str, GoalState] = {}
    for goal in snapshot.goals:
        if not isinstance(goal, GoalState):
            raise TypeError("snapshot goals must be GoalState values")
        if not goal.goal_id or not goal.goal_id.strip():
            raise ValueError("goal_id must be non-empty")
        if goal.goal_id in goal_by_id:
            raise ValueError(f"duplicate goal_id: {goal.goal_id}")
        if goal.status not in {"active", "paused", "blocked"}:
            raise ValueError(f"unsupported current goal status: {goal.status}")
        _unique_nonempty(goal.evidence_event_ids, "goal.evidence_event_ids")
        goal_by_id[goal.goal_id] = goal

    activity_by_id: dict[str, ActivityOption] = {}
    for option in snapshot.activity_options:
        if not isinstance(option, ActivityOption):
            raise TypeError("snapshot activity_options must be ActivityOption values")
        if not option.activity_id or not option.activity_id.strip():
            raise ValueError("activity_id must be non-empty")
        if option.activity_id in activity_by_id:
            raise ValueError(f"duplicate activity_id: {option.activity_id}")
        if option.side_effect_level not in {"none", "read_only", "external_side_effect"}:
            raise ValueError(f"unsupported side_effect_level: {option.side_effect_level}")
        if not isinstance(option.permission_granted, bool):
            raise ValueError("permission_granted must be boolean")
        if not isinstance(option.prerequisites_satisfied, bool):
            raise ValueError("prerequisites_satisfied must be boolean")
        if not option.required_capability or not option.required_capability.strip():
            raise ValueError("required_capability must be non-empty")
        _unique_nonempty(option.source_signal_ids, "activity.source_signal_ids")
        _unique_nonempty(option.serves_goal_ids, "activity.serves_goal_ids")
        if not option.source_signal_ids and not option.serves_goal_ids:
            raise ValueError(f"activity {option.activity_id} must cite a motivation signal or an accepted goal")
        if not set(option.source_signal_ids).issubset(signal_by_id):
            raise ValueError(f"activity {option.activity_id} references unknown motivation signal")
        if any(not signal_by_id[item].active for item in option.source_signal_ids):
            raise ValueError(f"activity {option.activity_id} references an inactive motivation signal")
        if not set(option.serves_goal_ids).issubset(goal_by_id):
            raise ValueError(f"activity {option.activity_id} references unknown goal")
        if any(goal_by_id[item].status != "active" for item in option.serves_goal_ids):
            raise ValueError(f"activity {option.activity_id} cannot target a paused or blocked goal")
        activity_by_id[option.activity_id] = option

    active_activity_ids = _unique_nonempty(
        snapshot.active_activity_ids, "snapshot.active_activity_ids"
    )
    active_activity_by_id: dict[str, ActiveActivityState] = {}
    for active in snapshot.active_activity_states:
        if not isinstance(active, ActiveActivityState):
            raise TypeError("active_activity_states must contain ActiveActivityState values")
        if not active.activity_id or not active.activity_id.strip():
            raise ValueError("active activity_id must be non-empty")
        if active.activity_id in active_activity_by_id:
            raise ValueError(f"duplicate active activity_id: {active.activity_id}")
        if active.activity_id not in active_activity_ids:
            raise ValueError("active activity state is not listed as active in the snapshot")
        if not active.required_capability or not active.required_capability.strip():
            raise ValueError("active activity required_capability must be non-empty")
        if active.side_effect_level not in {"none", "read_only", "external_side_effect"}:
            raise ValueError("active activity has unsupported side_effect_level")
        if not isinstance(active.permission_granted, bool):
            raise ValueError("active activity permission_granted must be boolean")
        if not isinstance(active.stop_condition_met, bool):
            raise ValueError("active activity stop_condition_met must be boolean")
        active_activity_by_id[active.activity_id] = active
    new_goal_ids: set[str] = set()
    goal_origin_classes: list[tuple[str, str]] = []
    goal_origin_signal_versions: list[tuple[str, tuple[tuple[str, int], ...]]] = []
    for goal_proposal in proposal.goal_proposals:
        if not isinstance(goal_proposal, GoalProposal):
            raise TypeError("goal_proposals must contain GoalProposal values")
        if not goal_proposal.goal_id or not goal_proposal.goal_id.strip():
            raise ValueError("proposed goal_id must be non-empty")
        if goal_proposal.goal_id in goal_by_id or goal_proposal.goal_id in new_goal_ids:
            raise ValueError(f"goal identity already exists in snapshot/proposal: {goal_proposal.goal_id}")
        new_goal_ids.add(goal_proposal.goal_id)
        for name, value in (
            ("desired_condition", goal_proposal.desired_condition),
            ("rationale", goal_proposal.rationale),
            ("success_condition", goal_proposal.success_condition),
            ("stop_condition", goal_proposal.stop_condition),
            ("review_condition", goal_proposal.review_condition),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"goal proposal {name} must be non-empty")
        origin_ids = _unique_nonempty(goal_proposal.origin_signal_ids, "goal.origin_signal_ids")
        if not origin_ids or not origin_ids.issubset(signal_by_id):
            raise ValueError("goal proposal must cite one or more signals in the current snapshot")
        if any(not signal_by_id[item].active for item in origin_ids):
            raise ValueError("goal proposal cannot originate from an inactive signal")
        # Preserve each signal's immutable CSD origin class. If an initially
        # user/external-origin interest later develops an emerging pattern of
        # voluntary encounters, the resulting goal has mixed lineage rather
        # than rewriting the signal's original origin as purely internal.
        origins = set()
        for item in origin_ids:
            signal = signal_by_id[item]
            origin = signal.origin_class
            if (
                origin in {"user_requested_encounter", "externally_exposed"}
                and signal.kind == "interest"
                and signal.interest_stage == "emerging"
                and signal.voluntary_encounters
            ):
                origin = "mixed_origin"
            origins.add(origin)
        if origins == {"internally_initiated"}:
            origin_class = "internally_initiated"
        elif origins == {"user_requested_encounter"}:
            origin_class = "user_requested"
        elif origins == {"externally_exposed"}:
            origin_class = "externally_triggered"
        else:
            origin_class = "mixed_origin"
        goal_origin_classes.append((goal_proposal.goal_id, origin_class))
        goal_origin_signal_versions.append((
            goal_proposal.goal_id,
            tuple(sorted((item, signal_by_id[item].signal_version) for item in origin_ids)),
        ))

    choice = proposal.choice
    if not isinstance(choice, ChoiceProposal):
        raise TypeError("proposal.choice must be ChoiceProposal")
    if choice.disposition not in {
        "start_activity", "continue_activity", "wait", "request_information",
        "pause_goal", "abandon_goal", "revise_goal", "decline", "stop_activity", "no_op",
    }:
        raise ValueError(f"unsupported disposition: {choice.disposition}")
    if not isinstance(choice.rationale, str) or not choice.rationale.strip():
        raise ValueError("choice rationale must be non-empty")

    considered_ids = _unique_nonempty(
        choice.considered_activity_ids, "choice.considered_activity_ids"
    )
    if not considered_ids.issubset(activity_by_id):
        raise ValueError("considered_activity_ids contains an option outside the snapshot")
    evidence_ids = _unique_nonempty(choice.evidence_event_ids, "choice.evidence_event_ids")
    valid_evidence_ids = {
        event_id
        for signal in signal_by_id.values()
        for event_id in (
            tuple(signal.supporting_event_ids) + tuple(signal.counter_evidence_event_ids)
        )
    } | {
        event_id
        for goal in goal_by_id.values()
        for event_id in goal.evidence_event_ids
    }
    if not evidence_ids.issubset(valid_evidence_ids):
        raise ValueError("choice evidence must reference source events present in the snapshot")

    if choice.goal_id is not None and choice.goal_id not in goal_by_id:
        raise ValueError("choice.goal_id must reference an existing accepted goal")
    if choice.activity_id is not None and choice.activity_id not in activity_by_id:
        raise ValueError("choice.activity_id is outside the trusted activity options")
    if choice.active_activity_id is not None and choice.active_activity_id not in active_activity_ids:
        raise ValueError("choice.active_activity_id is not active in the snapshot")

    requires_asm = False
    if choice.disposition == "start_activity":
        if choice.activity_id is None:
            raise ValueError("start_activity requires activity_id")
        if choice.activity_id not in considered_ids:
            raise ValueError("selected activity must appear in considered_activity_ids")
        option = activity_by_id[choice.activity_id]
        if not option.permission_granted:
            raise PermissionError("activity option lacks the required capability permission")
        if not option.prerequisites_satisfied:
            raise ValueError("activity prerequisites are not satisfied")
        if choice.goal_id is not None and choice.goal_id not in option.serves_goal_ids:
            raise ValueError("selected activity is not linked to the selected goal")
        requires_asm = option.side_effect_level == "external_side_effect"
    elif choice.disposition in {"continue_activity", "stop_activity"}:
        if choice.active_activity_id is None:
            raise ValueError(f"{choice.disposition} requires an active_activity_id")
        if choice.activity_id is not None:
            raise ValueError(f"{choice.disposition} must reference only the existing active activity")
        if choice.goal_id is not None:
            raise ValueError(f"{choice.disposition} cannot include a goal transition")
        active_state = active_activity_by_id.get(choice.active_activity_id)
        if active_state is None:
            raise ValueError("active activity details are required for continuation or stop")
        if choice.disposition == "continue_activity":
            if not active_state.permission_granted:
                raise PermissionError("active activity no longer has the required capability permission")
            if active_state.stop_condition_met:
                raise ValueError("activity stop condition has already been met")
        requires_asm = active_state.side_effect_level == "external_side_effect"
    elif choice.disposition in {"pause_goal", "abandon_goal", "revise_goal"}:
        if choice.goal_id is None:
            raise ValueError(f"{choice.disposition} requires goal_id")
        if choice.activity_id is not None or choice.active_activity_id is not None:
            raise ValueError(f"{choice.disposition} cannot also select an activity")
        current_goal = goal_by_id[choice.goal_id]
        if choice.disposition == "pause_goal" and current_goal.status != "active":
            raise ValueError("pause_goal requires an active goal")
    elif choice.disposition in {"wait", "request_information", "decline", "no_op"}:
        if choice.activity_id is not None or choice.active_activity_id is not None:
            raise ValueError(f"{choice.disposition} cannot select an activity")
    else:
        raise ValueError(f"unhandled disposition: {choice.disposition}")

    return ValidatedLifeProposal(
        proposal=proposal,
        goal_origin_classes=tuple(goal_origin_classes),
        goal_origin_signal_versions=tuple(goal_origin_signal_versions),
        requires_asm_governance=requires_asm,
    )
