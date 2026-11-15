"""Pure adapters from authoritative CSD projections to Life Engine inputs.

This module does not read SQLite or decide whether a signal is valid. It
translates the stable CSD projection shape into provider-neutral contracts;
CSD remains the authority and its event-backed checks must run before use.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from .contracts import GoalState, LifeSnapshot, MotivationSignal


_ORIGIN_CLASSES = {
    "internally_initiated",
    "user_requested_encounter",
    "externally_exposed",
    "mixed_origin",
}
_SIGNAL_KINDS = {"need", "interest", "curiosity", "affect", "commitment"}
_STATUSES = {"active", "paused", "resolved"}


def motivation_signal_from_csd(record: Mapping[str, Any]) -> MotivationSignal:
    """Translate one CSD accepted-signal projection without losing provenance.

    The caller must obtain this record from a CSD read path that has already
    verified event-backed projection integrity. This function validates shape
    and preserves signal version, subject, evidence polarity, maturity, and
    voluntary-encounter lineage; it does not authenticate the caller.
    """
    if not isinstance(record, Mapping):
        raise TypeError("CSD signal record must be a mapping")

    required = {
        "signal_id",
        "signal_version",
        "kind",
        "subject_ref",
        "scope",
        "statement",
        "status",
        "origin_class",
        "supporting_event_ids",
        "counter_evidence_event_ids",
        "voluntary_encounters",
        "interest_stage",
    }
    missing = required - set(record)
    if missing:
        raise ValueError(f"CSD signal record is missing fields: {sorted(missing)}")

    def nonempty(name: str) -> str:
        value = record[name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"CSD signal {name} must be a non-empty string")
        return value

    signal_id = nonempty("signal_id")
    subject_ref = nonempty("subject_ref")
    scope = nonempty("scope")
    statement = nonempty("statement")
    kind = nonempty("kind")
    origin_class = nonempty("origin_class")
    status = nonempty("status")

    version = record["signal_version"]
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ValueError("CSD signal_version must be a positive integer")
    if kind not in _SIGNAL_KINDS:
        raise ValueError(f"unsupported CSD signal kind: {kind}")
    if origin_class not in _ORIGIN_CLASSES:
        raise ValueError(f"unsupported CSD signal origin_class: {origin_class}")
    if status not in _STATUSES:
        raise ValueError(f"unsupported CSD signal status: {status}")

    def string_ids(name: str) -> tuple[str, ...]:
        values = record[name]
        if not isinstance(values, (list, tuple)):
            raise ValueError(f"CSD signal {name} must be a sequence")
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"CSD signal {name} must contain non-empty strings")
            if value in seen:
                raise ValueError(f"CSD signal {name} contains duplicate IDs")
            seen.add(value)
            result.append(value)
        return tuple(result)

    supporting = string_ids("supporting_event_ids")
    counter = string_ids("counter_evidence_event_ids")
    if set(supporting) & set(counter):
        raise ValueError("CSD supporting and counterevidence IDs must be disjoint")

    raw_encounters = record["voluntary_encounters"]
    if not isinstance(raw_encounters, (list, tuple)):
        raise ValueError("CSD voluntary_encounters must be a sequence")
    encounters: list[tuple[str, str, str]] = []
    seen_encounters: set[str] = set()
    seen_events: set[str] = set()
    for item in raw_encounters:
        if not isinstance(item, Mapping):
            raise ValueError("CSD voluntary encounter must be a mapping")
        encounter_id = item.get("encounter_id")
        occurred_at = item.get("occurred_at")
        event_id = item.get("event_id")
        if not isinstance(encounter_id, str) or not encounter_id.strip():
            raise ValueError("CSD voluntary encounter_id must be non-empty")
        if not isinstance(occurred_at, str) or not occurred_at.strip():
            raise ValueError("CSD voluntary occurred_at must be non-empty")
        try:
            parsed = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("CSD voluntary occurred_at must be ISO-8601") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("CSD voluntary occurred_at must include a timezone")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("CSD voluntary event_id must be non-empty")
        if encounter_id in seen_encounters or event_id in seen_events:
            raise ValueError("CSD voluntary encounter and event IDs must be unique")
        if event_id not in supporting:
            raise ValueError("CSD voluntary encounter must reference supporting evidence")
        seen_encounters.add(encounter_id)
        seen_events.add(event_id)
        encounters.append((encounter_id, occurred_at, event_id))

    interest_stage = record["interest_stage"]
    if kind == "interest":
        if interest_stage not in {None, "tentative", "emerging", "contextual"}:
            raise ValueError("unsupported CSD interest_stage")
    elif interest_stage is not None or encounters:
        raise ValueError("only CSD interest signals may carry maturity/encounter data")

    return MotivationSignal(
        signal_id=signal_id,
        signal_version=version,
        kind=kind,
        origin_class=origin_class,
        subject_ref=subject_ref,
        description=statement,
        supporting_event_ids=supporting,
        counter_evidence_event_ids=counter,
        active=status == "active",
        scope=scope,
        interest_stage=interest_stage,
        voluntary_encounters=tuple(encounters),
    )


def motivation_signals_from_csd(
    records: Sequence[Mapping[str, Any]],
) -> tuple[MotivationSignal, ...]:
    """Translate a CSD signal collection while rejecting duplicate identities."""
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise TypeError("CSD signal collection must be a sequence of mappings")
    result = tuple(motivation_signal_from_csd(record) for record in records)
    ids = [signal.signal_id for signal in result]
    if len(set(ids)) != len(ids):
        raise ValueError("CSD signal collection contains duplicate signal IDs")
    return result

class CsdSignalSnapshotStore(Protocol):
    def get_life_signal_snapshot(self) -> Mapping[str, Any]:
        """Return an integrity-checked, transactionally consistent CSD snapshot."""


class CognitiveStoreLifeSnapshotReader:
    """Build the current partial LifeSnapshot from CSD's authoritative signal read.

    CSD does not yet persist goals or active activities, so those collections
    are intentionally empty. Capability-filtered activity options must be
    supplied by a future trusted runtime boundary, not invented here.
    """

    def __init__(self, store: CsdSignalSnapshotStore) -> None:
        self._store = store

    def get_life_snapshot(self) -> LifeSnapshot:
        snapshot = self._store.get_life_signal_snapshot()
        if not isinstance(snapshot, Mapping):
            raise TypeError("CSD life signal snapshot must be a mapping")
        version = snapshot.get("state_version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise ValueError("CSD life signal snapshot has invalid state_version")
        if set(snapshot) != {"state_version", "signals", "goals"}:
            raise ValueError("CSD life snapshot contains missing or unsupported fields")
        raw_goals = snapshot["goals"]
        if not isinstance(raw_goals, (list, tuple)):
            raise ValueError("CSD goals must be a sequence")
        goals: list[GoalState] = []
        seen_goal_ids: set[str] = set()
        for record in raw_goals:
            if not isinstance(record, Mapping):
                raise ValueError("CSD goal record must be a mapping")
            goal_id = record.get("goal_id")
            desired_condition = record.get("desired_condition")
            status = record.get("status")
            goal_version = record.get("goal_version")
            if not isinstance(goal_id, str) or not goal_id.strip():
                raise ValueError("CSD goal_id must be non-empty")
            if goal_id in seen_goal_ids:
                raise ValueError("CSD goal snapshot contains duplicate goal IDs")
            seen_goal_ids.add(goal_id)
            if not isinstance(desired_condition, str) or not desired_condition.strip():
                raise ValueError("CSD goal desired_condition must be non-empty")
            if status not in {"candidate", "active", "paused", "blocked", "satisfied", "abandoned", "superseded"}:
                raise ValueError("CSD goal has unsupported lifecycle status")
            if not isinstance(goal_version, int) or isinstance(goal_version, bool) or goal_version < 1:
                raise ValueError("CSD goal_version must be positive")
            goals.append(GoalState(
                goal_id=goal_id,
                desired_condition=desired_condition,
                status=status,
            ))
        return LifeSnapshot(
            state_version=version,
            signals=motivation_signals_from_csd(snapshot["signals"]),
            goals=tuple(goals),
            activity_options=(),
        )

