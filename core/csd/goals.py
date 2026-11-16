"""CSD-owned goal proposal, activation, and pause/resume projections.

Candidate creation, explicit candidate→active activation, and pause/resume
are separate event-backed transitions. Other lifecycle transitions and
activity execution remain outside this slice.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping


GOAL_BATCH_PROPOSAL_EVENT = "life.goal_batch_proposed.v1"
GOAL_BATCH_DECISION_EVENT = "life.goal_batch_decided.v1"
GOAL_POLICY_ID = "csd.goal-candidate-provenance"
GOAL_POLICY_VERSION = "0.1"
GOAL_DECISION_SOURCE = "csd.authority.v1"
GOAL_CONTRACT_VERSION = "life.goal_batch_proposed.v1"


def _g_nonempty(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _g_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _g_canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)


def _g_string_list(value: Any, name: str, *, nonempty: bool = True) -> list[str]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{name} must be a {'non-empty ' if nonempty else ''}list of strings")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        _g_nonempty(item, name)
        if item in seen:
            raise ValueError(f"{name} must not contain duplicates")
        seen.add(item)
        result.append(item)
    return result


class CognitiveGoalMixin:
    """Methods mixed into CognitiveMemoryStore; all writes share its transaction."""

    def _validate_goal_proposal_snapshot_version(
        self, db: Any, event: Any, *, internal: bool
    ) -> None:
        payload = event["payload"] if isinstance(event, Mapping) else event.payload
        event_id = event["event_id"] if isinstance(event, Mapping) else event.event_id
        row = db.execute(
            "SELECT sequence FROM events WHERE event_id=?", (event_id,)
        ).fetchone()
        if row is None:
            self._raise_cognitive_integrity("goal proposal event is missing from event history")
        state_at_proposal = self._authoritative_state_version(
            db, through_sequence=int(row["sequence"]) - 1
        )
        claimed = payload["based_on"]["state_version"]
        if claimed > state_at_proposal:
            message = (
                f"goal proposal claims future state_version={claimed}; "
                f"only {state_at_proposal} existed when its event was appended"
            )
            if internal:
                self._raise_cognitive_integrity(message)
            raise ValueError(message)

    def _validate_goal_batch_proposal(self, event: Any) -> None:
        payload = event["payload"] if isinstance(event, Mapping) else event.payload
        event_source = event["source"] if isinstance(event, Mapping) else event.source
        allowed = {
            "proposal_id", "based_on", "goals", "choice", "origin",
            "contract_version",
        }
        if set(payload) != allowed:
            raise ValueError("goal batch proposal contains missing or unsupported fields")
        _g_nonempty(payload.get("proposal_id"), "proposal_id")
        if payload.get("contract_version") != GOAL_CONTRACT_VERSION:
            raise ValueError("unsupported goal proposal contract_version")
        based_on = payload.get("based_on")
        if not isinstance(based_on, Mapping) or set(based_on) != {"state_version"}:
            raise ValueError("goal proposal based_on must contain state_version")
        version = based_on.get("state_version")
        if not isinstance(version, int) or isinstance(version, bool) or version < 0:
            raise ValueError("based_on.state_version must be a non-negative integer")

        origin = payload.get("origin")
        if not isinstance(origin, Mapping) or set(origin) != {"component", "version"}:
            raise ValueError("goal proposal origin must contain component and version")
        component = _g_nonempty(origin.get("component"), "origin.component")
        _g_nonempty(origin.get("version"), "origin.version")
        if event_source != f"life-goal-proposal:{component}":
            raise ValueError("goal proposal source/origin mismatch")

        choice = payload.get("choice")
        if not isinstance(choice, Mapping) or set(choice) != {"disposition", "rationale"}:
            raise ValueError("goal proposal choice must contain disposition and rationale")
        disposition = _g_nonempty(choice.get("disposition"), "choice.disposition")
        if disposition not in {
            "start_activity", "continue_activity", "wait", "request_information",
            "pause_goal", "abandon_goal", "revise_goal", "decline",
            "stop_activity", "no_op",
        }:
            raise ValueError("unsupported goal proposal choice disposition")
        _g_nonempty(choice.get("rationale"), "choice.rationale")

        goals = payload.get("goals")
        if not isinstance(goals, list) or not goals:
            raise ValueError("a goal batch must contain at least one candidate goal")
        seen_goal_ids: set[str] = set()
        for index, goal in enumerate(goals):
            if not isinstance(goal, Mapping) or set(goal) != {
                "goal_id", "desired_condition", "origin_signal_ids", "rationale",
                "success_condition", "stop_condition", "review_condition",
            }:
                raise ValueError(f"goals[{index}] has missing or unsupported fields")
            goal_id = _g_nonempty(goal.get("goal_id"), f"goals[{index}].goal_id")
            if goal_id in seen_goal_ids:
                raise ValueError("goal batch contains duplicate goal IDs")
            seen_goal_ids.add(goal_id)
            for field in (
                "desired_condition", "rationale", "success_condition",
                "stop_condition", "review_condition",
            ):
                _g_nonempty(goal.get(field), f"goals[{index}].{field}")
            _g_string_list(goal.get("origin_signal_ids"), f"goals[{index}].origin_signal_ids")

    @staticmethod
    def _derive_goal_origin(signal: Mapping[str, Any]) -> str:
        origin = signal.get("origin_class")
        if (
            origin in {"user_requested_encounter", "externally_exposed"}
            and signal.get("kind") == "interest"
            and signal.get("interest_stage") == "emerging"
            and bool(signal.get("voluntary_encounters"))
        ):
            return "mixed_origin"
        if origin == "internally_initiated":
            return "internally_initiated"
        if origin == "user_requested_encounter":
            return "user_requested"
        if origin == "externally_exposed":
            return "externally_triggered"
        if origin == "mixed_origin":
            return "mixed_origin"
        raise ValueError(f"unsupported source signal origin_class: {origin!r}")

    def _goal_signal_at(
        self, db: Any, signal_id: str, *, before_sequence: int | None
    ) -> dict[str, Any] | None:
        query = (
            "SELECT v.signal_json FROM motivation_signal_versions v "
            "JOIN events e ON e.event_id=v.decision_event_id "
            "WHERE v.signal_id=?"
        )
        params: list[Any] = [signal_id]
        if before_sequence is not None:
            query += " AND e.sequence<?"
            params.append(before_sequence)
        query += " ORDER BY e.sequence DESC LIMIT 1"
        row = db.execute(query, params).fetchone()
        return json.loads(row["signal_json"]) if row is not None else None

    def _prepare_goal_batch_decision(
        self,
        db: Any,
        proposal_id: str,
        *,
        evaluated_state_version: int,
        before_sequence: int | None,
        known_goal_ids: set[str] | None = None,
        proposal_payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if proposal_payload is None:
            row = db.execute(
                "SELECT proposal_json,proposal_event_id,decision_event_id "
                "FROM goal_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            proposal = json.loads(row["proposal_json"])
        else:
            proposal = dict(proposal_payload)
        if proposal["based_on"]["state_version"] != evaluated_state_version:
            return {
                "outcome": "deferred", "transitions": [],
                "reason": (
                    f"stale proposal state_version={proposal['based_on']['state_version']}; "
                    f"current state_version={evaluated_state_version}"
                ),
            }

        used_ids = set(known_goal_ids or ())
        if known_goal_ids is None:
            used_ids.update(
                item["goal_id"] for item in db.execute(
                    "SELECT goal_id FROM goals"
                ).fetchall()
            )
        goals = proposal["goals"]
        if any(goal["goal_id"] in used_ids for goal in goals):
            return {
                "outcome": "rejected", "transitions": [],
                "reason": "one or more goal identities already exist",
            }

        transitions: list[dict[str, Any]] = []
        for goal in goals:
            signal_refs: list[dict[str, Any]] = []
            origin_classes: set[str] = set()
            for signal_id in goal["origin_signal_ids"]:
                signal = self._goal_signal_at(
                    db, signal_id, before_sequence=before_sequence
                )
                if signal is None or signal.get("status") != "active":
                    return {
                        "outcome": "rejected", "transitions": [],
                        "reason": f"origin signal is missing or inactive: {signal_id}",
                    }
                signal_version = signal.get("signal_version")
                if (
                    not isinstance(signal_version, int)
                    or isinstance(signal_version, bool)
                    or signal_version < 1
                ):
                    self._raise_cognitive_integrity("source signal has an invalid version")
                signal_refs.append({
                    "signal_id": signal_id,
                    "signal_version": signal_version,
                })
                origin_classes.add(self._derive_goal_origin(signal))
            if origin_classes == {"internally_initiated"}:
                origin_class = "internally_initiated"
            elif origin_classes == {"user_requested"}:
                origin_class = "user_requested"
            elif origin_classes == {"externally_triggered"}:
                origin_class = "externally_triggered"
            else:
                origin_class = "mixed_origin"
            transitions.append({
                "goal_id": goal["goal_id"],
                "goal_version": 1,
                "status": "candidate",
                "origin_class": origin_class,
                "origin_signal_refs": sorted(
                    signal_refs, key=lambda item: item["signal_id"]
                ),
            })
        transitions.sort(key=lambda item: item["goal_id"])
        return {
            "outcome": "accepted",
            "transitions": transitions,
            "reason": "goal batch passed CSD source-lineage and identity checks",
        }

    def _apply_goal_batch_decision(self, db: Any, event: Any) -> None:
        payload = event.payload
        proposal_id = _g_nonempty(payload.get("proposal_id"), "decision.proposal_id")
        proposal = db.execute(
            "SELECT proposal_event_id,decision_event_id FROM goal_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if proposal is None:
            self._raise_cognitive_integrity("goal decision references a missing proposal")
        if proposal["decision_event_id"] is not None:
            self._raise_cognitive_integrity("goal proposal has more than one decision")
        if payload.get("proposal_event_id") != proposal["proposal_event_id"]:
            self._raise_cognitive_integrity("goal decision proposal-event mismatch")
        event_row = db.execute(
            "SELECT sequence FROM events WHERE event_id=?", (event.event_id,)
        ).fetchone()
        if event_row is None:
            self._raise_cognitive_integrity("goal decision event is missing from history")
        sequence = int(event_row["sequence"])
        current_version = self._authoritative_state_version(
            db, through_sequence=sequence - 1
        )
        if payload.get("evaluated_state_version") != current_version:
            self._raise_cognitive_integrity("goal decision evaluated against stale state_version")

        prepared = self._prepare_goal_batch_decision(
            db, proposal_id,
            evaluated_state_version=current_version,
            before_sequence=sequence,
        )
        expected = {
            "proposal_id": proposal_id,
            "proposal_event_id": proposal["proposal_event_id"],
            "outcome": prepared["outcome"],
            "policy": {"id": GOAL_POLICY_ID, "version": GOAL_POLICY_VERSION},
            "evaluated_state_version": current_version,
            "transitions": prepared["transitions"],
            "reason": prepared["reason"],
        }
        if set(payload) != set(expected):
            self._raise_cognitive_integrity("goal decision contains missing or unsupported fields")
        for key, value in expected.items():
            if payload.get(key) != value:
                self._raise_cognitive_integrity(f"goal decision {key} does not match CSD evaluation")
        if event.event_id != f"csd-goal-decision:{proposal_id}":
            self._raise_cognitive_integrity("goal decision event ID is not proposal-scoped")
        if event.correlation_id != f"goal-proposal:{proposal_id}":
            self._raise_cognitive_integrity("goal decision correlation_id mismatch")
        if event.source != GOAL_DECISION_SOURCE:
            self._raise_cognitive_integrity("goal decision source is not CSD authority")

        outcome = prepared["outcome"]
        transitions = prepared["transitions"]
        if outcome == "accepted":
            if not transitions:
                self._raise_cognitive_integrity("accepted goal batch must create at least one goal")
            for transition in transitions:
                goal = next(
                    item for item in json.loads(
                        db.execute(
                            "SELECT proposal_json FROM goal_proposals WHERE proposal_id=?",
                            (proposal_id,),
                        ).fetchone()["proposal_json"]
                    )["goals"] if item["goal_id"] == transition["goal_id"]
                )
                transition_id = f"csd-goal-transition:{proposal_id}:{transition['goal_id']}"
                goal_state = {
                    **goal,
                    "goal_version": 1,
                    "status": "candidate",
                    "origin_class": transition["origin_class"],
                    "origin_signal_refs": transition["origin_signal_refs"],
                    "proposal_id": proposal_id,
                    "proposal_event_id": proposal["proposal_event_id"],
                    "decision_event_id": event.event_id,
                    "transition_id": transition_id,
                    "created_at": event.occurred_at,
                }
                goal_json = _g_canonical(goal_state)
                db.execute(
                    "INSERT INTO goal_versions(goal_id,goal_version,decision_event_id,transition_id,goal_json) "
                    "VALUES (?,?,?,?,?)",
                    (goal["goal_id"], 1, event.event_id, transition_id, goal_json),
                )
                db.execute(
                    "INSERT INTO goals(goal_id,goal_version,decision_event_id,transition_id,goal_json) "
                    "VALUES (?,?,?,?,?)",
                    (goal["goal_id"], 1, event.event_id, transition_id, goal_json),
                )
        elif transitions:
            self._raise_cognitive_integrity("non-accepted goal decision cannot contain transitions")

        db.execute(
            "UPDATE goal_proposals SET status=?,decision_event_id=? WHERE proposal_id=?",
            (outcome, event.event_id, proposal_id),
        )

    def _apply_goal_projection_event(
        self, db: Any, event: Any, *, internal: bool
    ) -> None:
        if event.event_type == GOAL_BATCH_PROPOSAL_EVENT:
            if internal:
                raise ValueError("goal proposal events must use public Event Submit")
            self._validate_goal_batch_proposal(event)
            payload_json = _g_canonical(dict(event.payload))
            digest = _g_digest(payload_json)
            proposal_id = event.payload["proposal_id"]
            existing = db.execute(
                "SELECT proposal_digest FROM goal_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if existing is not None:
                if existing["proposal_digest"] != digest:
                    raise ValueError(f"goal proposal identity conflict: {proposal_id}")
                return
            db.execute(
                "INSERT INTO goal_proposals(proposal_id,proposal_digest,proposal_event_id,proposal_json,status,decision_event_id) "
                "VALUES (?,?,?,?, 'pending',NULL)",
                (proposal_id, digest, event.event_id, payload_json),
            )
            return
        if event.event_type == GOAL_BATCH_DECISION_EVENT:
            if not internal or event.source != GOAL_DECISION_SOURCE:
                self._raise_cognitive_integrity("non-authoritative goal decision event")
            self._apply_goal_batch_decision(db, event)
            return
        self._raise_cognitive_integrity("unhandled goal projection event")

    def evaluate_goal_batch_proposal(self, proposal_id: str) -> dict[str, Any]:
        """Evaluate one pending batch; no model or external action is invoked."""
        _g_nonempty(proposal_id, "proposal_id")
        from .cognitive import CognitiveEvent

        with self._tx() as db:
            row = db.execute(
                "SELECT proposal_event_id,decision_event_id FROM goal_proposals WHERE proposal_id=?",
                (proposal_id,),
            ).fetchone()
            if row is None:
                raise KeyError(proposal_id)
            if row["decision_event_id"] is not None:
                return {
                    "status": "already_decided",
                    "decision_event_id": row["decision_event_id"],
                }
            self._assert_accepted_projection_consistent()
            self._assert_motivation_projection_consistent()
            self._assert_goal_projection_consistent()
            current_version = self._authoritative_state_version(db)
            prepared = self._prepare_goal_batch_decision(
                db, proposal_id,
                evaluated_state_version=current_version,
                before_sequence=None,
            )
            event = CognitiveEvent(
                event_id=f"csd-goal-decision:{proposal_id}",
                occurred_at=datetime.now(timezone.utc).isoformat(),
                correlation_id=f"goal-proposal:{proposal_id}",
                event_type=GOAL_BATCH_DECISION_EVENT,
                source=GOAL_DECISION_SOURCE,
                payload={
                    "proposal_id": proposal_id,
                    "proposal_event_id": row["proposal_event_id"],
                    "outcome": prepared["outcome"],
                    "policy": {"id": GOAL_POLICY_ID, "version": GOAL_POLICY_VERSION},
                    "evaluated_state_version": current_version,
                    "transitions": prepared["transitions"],
                    "reason": prepared["reason"],
                },
            )
            payload_json = self._validate_event(event, internal=True)
            appended = self._append_event_in_transaction(
                db, event, payload_json, internal=True
            )
            return {
                "status": prepared["outcome"],
                "decision_event_id": event.event_id,
                "sequence": appended["sequence"],
                "reason": prepared["reason"],
            }

    def _assert_goal_projection_consistent(self) -> None:
        """Reconcile all goal projections against verified events and historical signals."""
        self._assert_motivation_projection_consistent()
        rows = self._db.execute(
            "SELECT sequence,event_id,event_type FROM events "
            "WHERE event_type IN (?,?) ORDER BY sequence",
            (GOAL_BATCH_PROPOSAL_EVENT, GOAL_BATCH_DECISION_EVENT),
        ).fetchall()
        proposals: dict[str, dict[str, Any]] = {}
        decisions: dict[str, tuple[str, dict[str, Any], int]] = {}
        expected_goals: dict[str, str] = {}
        expected_versions: dict[tuple[str, int], tuple[str, str, str]] = {}
        for row in rows:
            record = self.get_event(row["event_id"])
            payload = record["payload"]
            if row["event_type"] == GOAL_BATCH_PROPOSAL_EVENT:
                proposal_id = payload.get("proposal_id")
                if not isinstance(proposal_id, str) or not proposal_id:
                    self._raise_cognitive_integrity("goal proposal event has no proposal_id")
                self._validate_goal_batch_proposal(record)
                canonical = _g_canonical(payload)
                digest = _g_digest(canonical)
                prior = proposals.get(proposal_id)
                if prior is None:
                    proposals[proposal_id] = {
                        "digest": digest, "event_id": row["event_id"],
                        "json": canonical, "payload": payload,
                    }
                elif prior["digest"] != digest:
                    self._raise_cognitive_integrity("goal proposal identity conflict in event history")
            else:
                proposal_id = payload.get("proposal_id")
                if not isinstance(proposal_id, str) or proposal_id in decisions:
                    self._raise_cognitive_integrity("goal decision has missing/duplicate proposal identity")
                if proposal_id not in proposals:
                    self._raise_cognitive_integrity("goal decision references a missing proposal")
                proposal = proposals[proposal_id]
                current_version = self._authoritative_state_version(
                    self._db, through_sequence=int(row["sequence"]) - 1
                )
                prepared = self._prepare_goal_batch_decision(
                    self._db, proposal_id,
                    evaluated_state_version=current_version,
                    before_sequence=int(row["sequence"]),
                    known_goal_ids=set(expected_goals),
                    proposal_payload=proposal["payload"],
                )
                expected = {
                    "proposal_id": proposal_id,
                    "proposal_event_id": proposal["event_id"],
                    "outcome": prepared["outcome"],
                    "policy": {"id": GOAL_POLICY_ID, "version": GOAL_POLICY_VERSION},
                    "evaluated_state_version": current_version,
                    "transitions": prepared["transitions"],
                    "reason": prepared["reason"],
                }
                if (
                    record["source"] != GOAL_DECISION_SOURCE
                    or record["correlation_id"] != f"goal-proposal:{proposal_id}"
                    or record["event_id"] != f"csd-goal-decision:{proposal_id}"
                    or payload != expected
                ):
                    self._raise_cognitive_integrity("goal decision event differs from deterministic CSD evaluation")
                decisions[proposal_id] = (row["event_id"], payload, int(row["sequence"]))
                if prepared["outcome"] == "accepted":
                    for transition in prepared["transitions"]:
                        goal_id = transition["goal_id"]
                        if goal_id in expected_goals:
                            self._raise_cognitive_integrity("duplicate accepted goal identity in event history")
                        goal = next(
                            item for item in proposal["payload"]["goals"]
                            if item["goal_id"] == goal_id
                        )
                        transition_id = f"csd-goal-transition:{proposal_id}:{goal_id}"
                        goal_state = {
                            **goal,
                            "goal_version": 1,
                            "status": "candidate",
                            "origin_class": transition["origin_class"],
                            "origin_signal_refs": transition["origin_signal_refs"],
                            "proposal_id": proposal_id,
                            "proposal_event_id": proposal["event_id"],
                            "decision_event_id": row["event_id"],
                            "transition_id": transition_id,
                            "created_at": record["occurred_at"],
                        }
                        goal_json = _g_canonical(goal_state)
                        expected_goals[goal_id] = goal_json
                        expected_versions[(goal_id, 1)] = (
                            row["event_id"], transition_id, goal_json
                        )

        proposal_rows = self._db.execute(
            "SELECT proposal_id,proposal_digest,proposal_event_id,proposal_json,status,decision_event_id "
            "FROM goal_proposals"
        ).fetchall()
        if len(proposal_rows) != len(proposals):
            self._raise_cognitive_integrity("goal proposal projection count differs from event history")
        for row in proposal_rows:
            source = proposals.get(row["proposal_id"])
            decision = decisions.get(row["proposal_id"])
            status = decision[1]["outcome"] if decision else "pending"
            decision_id = decision[0] if decision else None
            if source is None or (
                row["proposal_digest"] != source["digest"]
                or row["proposal_event_id"] != source["event_id"]
                or row["proposal_json"] != source["json"]
                or row["status"] != status
                or row["decision_event_id"] != decision_id
            ):
                self._raise_cognitive_integrity("goal proposal projection differs from event history")
        if set(decisions) - set(proposals):
            self._raise_cognitive_integrity("goal decision references a missing proposal")

        version_rows = self._db.execute(
            "SELECT goal_id,goal_version,decision_event_id,transition_id,goal_json FROM goal_versions"
        ).fetchall()
        if len(version_rows) != len(expected_versions):
            self._raise_cognitive_integrity("goal version projection count differs from event history")
        for row in version_rows:
            expected = expected_versions.get((row["goal_id"], int(row["goal_version"])))
            if expected is None or (
                row["decision_event_id"], row["transition_id"], row["goal_json"]
            ) != expected:
                self._raise_cognitive_integrity("goal version projection differs from decision events")
        goal_rows = self._db.execute(
            "SELECT goal_id,goal_version,decision_event_id,transition_id,goal_json FROM goals"
        ).fetchall()
        if len(goal_rows) != len(expected_goals):
            self._raise_cognitive_integrity("latest goal projection count differs from event history")
        for row in goal_rows:
            expected = expected_goals.get(row["goal_id"])
            expected_state = json.loads(expected) if expected is not None else {}
            if (
                int(row["goal_version"]) != 1
                or row["decision_event_id"] != expected_state.get("decision_event_id")
                or row["transition_id"] != expected_state.get("transition_id")
                or row["goal_json"] != expected
            ):
                self._raise_cognitive_integrity("latest goal projection differs from event history")

    def get_goal_proposal(self, proposal_id: str) -> dict[str, Any]:
        _g_nonempty(proposal_id, "proposal_id")
        self._assert_goal_projection_consistent()
        row = self._db.execute(
            "SELECT proposal_json,proposal_digest,proposal_event_id,status,decision_event_id "
            "FROM goal_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        return {
            "proposal": json.loads(row["proposal_json"]),
            "proposal_digest": "sha256:" + row["proposal_digest"],
            "proposal_event_id": row["proposal_event_id"],
            "status": row["status"],
            "decision_event_id": row["decision_event_id"],
        }

    def get_goals(self) -> list[dict[str, Any]]:
        self._assert_goal_projection_consistent()
        rows = self._db.execute(
            "SELECT goal_json FROM goals ORDER BY goal_id"
        ).fetchall()
        return [json.loads(row["goal_json"]) for row in rows]

    def get_goal(self, goal_id: str) -> dict[str, Any]:
        _g_nonempty(goal_id, "goal_id")
        self._assert_goal_projection_consistent()
        row = self._db.execute(
            "SELECT goal_json FROM goals WHERE goal_id=?", (goal_id,)
        ).fetchone()
        if row is None:
            raise KeyError(goal_id)
        return json.loads(row["goal_json"])

# Pause/resume are explicit internal goal lifecycle choices. They do not
# create, schedule, or execute activities.
GOAL_PAUSE_RESUME_PROPOSAL_EVENT = "life.goal_pause_resume_proposed.v1"
GOAL_PAUSE_RESUME_DECISION_EVENT = "life.goal_pause_resume_decided.v1"
GOAL_PAUSE_RESUME_POLICY_ID = "csd.goal-pause-resume"
GOAL_PAUSE_RESUME_POLICY_VERSION = "0.1"
GOAL_PAUSE_RESUME_CONTRACT_VERSION = "life.goal_pause_resume_proposed.v1"


def _validate_goal_pause_resume_proposal(event: Any) -> None:
    payload = event["payload"] if isinstance(event, Mapping) else event.payload
    source = event["source"] if isinstance(event, Mapping) else event.source
    allowed = {
        "proposal_id", "based_on", "goal_id", "expected_goal_version",
        "operation", "rationale", "origin", "contract_version",
    }
    if set(payload) != allowed:
        raise ValueError("goal pause/resume proposal contains missing or unsupported fields")
    _g_nonempty(payload.get("proposal_id"), "proposal_id")
    if payload.get("contract_version") != GOAL_PAUSE_RESUME_CONTRACT_VERSION:
        raise ValueError("unsupported goal pause/resume contract_version")
    based_on = payload.get("based_on")
    if not isinstance(based_on, Mapping) or set(based_on) != {"state_version"}:
        raise ValueError("goal pause/resume based_on must contain state_version")
    state_version = based_on.get("state_version")
    if not isinstance(state_version, int) or isinstance(state_version, bool) or state_version < 0:
        raise ValueError("based_on.state_version must be a non-negative integer")
    _g_nonempty(payload.get("goal_id"), "goal_id")
    goal_version = payload.get("expected_goal_version")
    if not isinstance(goal_version, int) or isinstance(goal_version, bool) or goal_version < 1:
        raise ValueError("expected_goal_version must be a positive integer")
    operation = _g_nonempty(payload.get("operation"), "operation")
    if operation not in {"pause", "resume"}:
        raise ValueError("goal lifecycle operation must be pause or resume")
    _g_nonempty(payload.get("rationale"), "rationale")
    origin = payload.get("origin")
    if not isinstance(origin, Mapping) or set(origin) != {"component", "version"}:
        raise ValueError("goal pause/resume origin must contain component and version")
    component = _g_nonempty(origin.get("component"), "origin.component")
    _g_nonempty(origin.get("version"), "origin.version")
    if source != f"life-goal-pause-resume-proposal:{component}":
        raise ValueError("goal pause/resume source/origin mismatch")


def _prepare_goal_pause_resume_decision(
    self: CognitiveGoalMixin,
    db: Any,
    proposal_id: str,
    *,
    evaluated_state_version: int,
    decision_time: str,
    known_goal_states: Mapping[str, Mapping[str, Any]] | None = None,
    proposal_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if proposal_payload is None:
        row = db.execute(
            "SELECT proposal_json FROM goal_pause_resume_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        proposal = json.loads(row["proposal_json"])
    else:
        proposal = dict(proposal_payload)
    if proposal["based_on"]["state_version"] != evaluated_state_version:
        return {
            "outcome": "deferred", "transition": None,
            "reason": (
                f"stale proposal state_version={proposal['based_on']['state_version']}; "
                f"current state_version={evaluated_state_version}"
            ),
        }
    goal_id = proposal["goal_id"]
    if known_goal_states is None:
        row = db.execute("SELECT goal_json FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
        goal = json.loads(row["goal_json"]) if row is not None else None
    else:
        raw = known_goal_states.get(goal_id)
        goal = dict(raw) if raw is not None else None
    if goal is None:
        return {"outcome": "rejected", "transition": None, "reason": "target goal does not exist"}
    current_version = goal.get("goal_version")
    if not isinstance(current_version, int) or isinstance(current_version, bool) or current_version < 1:
        self._raise_cognitive_integrity("target goal has an invalid current version")
    if proposal["expected_goal_version"] != current_version:
        return {
            "outcome": "deferred", "transition": None,
            "reason": (
                f"stale expected_goal_version={proposal['expected_goal_version']}; "
                f"current goal_version={current_version}"
            ),
        }
    operation = proposal["operation"]
    expected_status = "active" if operation == "pause" else "paused"
    new_status = "paused" if operation == "pause" else "active"
    if goal.get("status") != expected_status:
        return {
            "outcome": "rejected", "transition": None,
            "reason": f"{operation} requires goal status {expected_status}",
        }
    transition = {
        "goal_id": goal_id,
        "operation": operation,
        "from_goal_version": current_version,
        "from_status": expected_status,
        "goal_version": current_version + 1,
        "status": new_status,
        "transition_id": f"csd-goal-pause-resume-transition:{proposal_id}:{goal_id}",
        "rationale": proposal["rationale"],
        "transitioned_at": decision_time,
    }
    return {
        "outcome": "accepted",
        "transition": transition,
        "reason": f"goal explicitly {new_status}; no activity or capability is changed",
    }


def _apply_goal_pause_resume_decision(self: CognitiveGoalMixin, db: Any, event: Any) -> None:
    payload = event.payload
    proposal_id = _g_nonempty(payload.get("proposal_id"), "decision.proposal_id")
    proposal = db.execute(
        "SELECT proposal_event_id,decision_event_id,proposal_json "
        "FROM goal_pause_resume_proposals WHERE proposal_id=?", (proposal_id,)
    ).fetchone()
    if proposal is None:
        self._raise_cognitive_integrity("goal pause/resume decision references a missing proposal")
    if proposal["decision_event_id"] is not None:
        self._raise_cognitive_integrity("goal pause/resume proposal has more than one decision")
    if payload.get("proposal_event_id") != proposal["proposal_event_id"]:
        self._raise_cognitive_integrity("goal pause/resume proposal-event mismatch")
    event_row = db.execute("SELECT sequence FROM events WHERE event_id=?", (event.event_id,)).fetchone()
    if event_row is None:
        self._raise_cognitive_integrity("goal pause/resume decision event is missing from history")
    sequence = int(event_row["sequence"])
    current_version = self._authoritative_state_version(db, through_sequence=sequence - 1)
    if payload.get("evaluated_state_version") != current_version:
        self._raise_cognitive_integrity("goal pause/resume decision evaluated against stale state_version")
    proposal_payload = json.loads(proposal["proposal_json"])
    prepared = _prepare_goal_pause_resume_decision(
        self, db, proposal_id,
        evaluated_state_version=current_version,
        decision_time=event.occurred_at,
        proposal_payload=proposal_payload,
    )
    expected = {
        "proposal_id": proposal_id,
        "proposal_event_id": proposal["proposal_event_id"],
        "outcome": prepared["outcome"],
        "policy": {"id": GOAL_PAUSE_RESUME_POLICY_ID, "version": GOAL_PAUSE_RESUME_POLICY_VERSION},
        "evaluated_state_version": current_version,
        "goal_id": proposal_payload["goal_id"],
        "expected_goal_version": proposal_payload["expected_goal_version"],
        "operation": proposal_payload["operation"],
        "transition": prepared["transition"],
        "reason": prepared["reason"],
    }
    if set(payload) != set(expected) or dict(payload) != expected:
        self._raise_cognitive_integrity("goal pause/resume decision differs from deterministic CSD evaluation")
    if event.event_id != f"csd-goal-pause-resume-decision:{proposal_id}":
        self._raise_cognitive_integrity("goal pause/resume decision event ID is not proposal-scoped")
    if event.correlation_id != f"goal-pause-resume-proposal:{proposal_id}":
        self._raise_cognitive_integrity("goal pause/resume decision correlation_id mismatch")
    if event.source != GOAL_DECISION_SOURCE:
        self._raise_cognitive_integrity("goal pause/resume decision source is not CSD authority")

    transition = prepared["transition"]
    if prepared["outcome"] == "accepted":
        goal_id = transition["goal_id"]
        row = db.execute("SELECT goal_json FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
        if row is None:
            self._raise_cognitive_integrity("accepted pause/resume target disappeared")
        current_goal = json.loads(row["goal_json"])
        if (
            current_goal.get("goal_version") != transition["from_goal_version"]
            or current_goal.get("status") != transition["from_status"]
        ):
            self._raise_cognitive_integrity("goal changed during pause/resume decision")
        updated = {
            **current_goal,
            "goal_version": transition["goal_version"],
            "status": transition["status"],
            "decision_event_id": event.event_id,
            "transition_id": transition["transition_id"],
            "lifecycle_proposal_id": proposal_id,
            "lifecycle_proposal_event_id": proposal["proposal_event_id"],
            "lifecycle_decision_event_id": event.event_id,
            "lifecycle_operation": transition["operation"],
            "lifecycle_rationale": transition["rationale"],
            "lifecycle_transitioned_at": transition["transitioned_at"],
        }
        goal_json = _g_canonical(updated)
        db.execute(
            "INSERT INTO goal_versions(goal_id,goal_version,decision_event_id,transition_id,goal_json) "
            "VALUES (?,?,?,?,?)",
            (goal_id, transition["goal_version"], event.event_id, transition["transition_id"], goal_json),
        )
        db.execute(
            "UPDATE goals SET goal_version=?,decision_event_id=?,transition_id=?,goal_json=? WHERE goal_id=?",
            (transition["goal_version"], event.event_id, transition["transition_id"], goal_json, goal_id),
        )
    elif transition is not None:
        self._raise_cognitive_integrity("non-accepted pause/resume decision contains a transition")
    db.execute(
        "UPDATE goal_pause_resume_proposals SET status=?,decision_event_id=? WHERE proposal_id=?",
        (prepared["outcome"], event.event_id, proposal_id),
    )


def _evaluate_goal_pause_resume_proposal(
    self: CognitiveGoalMixin, proposal_id: str
) -> dict[str, Any]:
    _g_nonempty(proposal_id, "proposal_id")
    from .cognitive import CognitiveEvent
    with self._tx() as db:
        row = db.execute(
            "SELECT proposal_event_id,decision_event_id,proposal_json "
            "FROM goal_pause_resume_proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row["decision_event_id"] is not None:
            return {"status": "already_decided", "decision_event_id": row["decision_event_id"]}
        self._assert_accepted_projection_consistent()
        self._assert_motivation_projection_consistent()
        self._assert_goal_projection_consistent()
        current_version = self._authoritative_state_version(db)
        proposal_payload = json.loads(row["proposal_json"])
        prepared = _prepare_goal_pause_resume_decision(
            self, db, proposal_id,
            evaluated_state_version=current_version,
            decision_time=datetime.now(timezone.utc).isoformat(),
            proposal_payload=proposal_payload,
        )
        decision_time = (
            prepared["transition"]["transitioned_at"]
            if prepared["transition"] is not None
            else datetime.now(timezone.utc).isoformat()
        )
        event = CognitiveEvent(
            event_id=f"csd-goal-pause-resume-decision:{proposal_id}",
            occurred_at=decision_time,
            correlation_id=f"goal-pause-resume-proposal:{proposal_id}",
            event_type=GOAL_PAUSE_RESUME_DECISION_EVENT,
            source=GOAL_DECISION_SOURCE,
            payload={
                "proposal_id": proposal_id,
                "proposal_event_id": row["proposal_event_id"],
                "outcome": prepared["outcome"],
                "policy": {"id": GOAL_PAUSE_RESUME_POLICY_ID, "version": GOAL_PAUSE_RESUME_POLICY_VERSION},
                "evaluated_state_version": current_version,
                "goal_id": proposal_payload["goal_id"],
                "expected_goal_version": proposal_payload["expected_goal_version"],
                "operation": proposal_payload["operation"],
                "transition": prepared["transition"],
                "reason": prepared["reason"],
            },
        )
        payload_json = self._validate_event(event, internal=True)
        appended = self._append_event_in_transaction(db, event, payload_json, internal=True)
        return {
            "status": prepared["outcome"],
            "decision_event_id": event.event_id,
            "sequence": appended["sequence"],
            "reason": prepared["reason"],
        }


# Candidate-to-active activation is deliberately a separate event family from
# candidate creation. It is an internal state transition, never an activity.
GOAL_ACTIVATION_PROPOSAL_EVENT = "life.goal_activation_proposed.v1"
GOAL_ACTIVATION_DECISION_EVENT = "life.goal_activation_decided.v1"
GOAL_ACTIVATION_POLICY_ID = "csd.goal-candidate-activation"
GOAL_ACTIVATION_POLICY_VERSION = "0.1"
GOAL_ACTIVATION_CONTRACT_VERSION = "life.goal_activation_proposed.v1"


def _validate_goal_activation_proposal(event: Any) -> None:
    payload = event["payload"] if isinstance(event, Mapping) else event.payload
    source = event["source"] if isinstance(event, Mapping) else event.source
    allowed = {
        "proposal_id", "based_on", "goal_id", "expected_goal_version",
        "rationale", "origin", "contract_version",
    }
    if set(payload) != allowed:
        raise ValueError("goal activation proposal contains missing or unsupported fields")
    _g_nonempty(payload.get("proposal_id"), "proposal_id")
    if payload.get("contract_version") != GOAL_ACTIVATION_CONTRACT_VERSION:
        raise ValueError("unsupported goal activation contract_version")
    based_on = payload.get("based_on")
    if not isinstance(based_on, Mapping) or set(based_on) != {"state_version"}:
        raise ValueError("goal activation based_on must contain state_version")
    state_version = based_on.get("state_version")
    if not isinstance(state_version, int) or isinstance(state_version, bool) or state_version < 0:
        raise ValueError("based_on.state_version must be a non-negative integer")
    _g_nonempty(payload.get("goal_id"), "goal_id")
    goal_version = payload.get("expected_goal_version")
    if not isinstance(goal_version, int) or isinstance(goal_version, bool) or goal_version < 1:
        raise ValueError("expected_goal_version must be a positive integer")
    _g_nonempty(payload.get("rationale"), "rationale")
    origin = payload.get("origin")
    if not isinstance(origin, Mapping) or set(origin) != {"component", "version"}:
        raise ValueError("goal activation origin must contain component and version")
    component = _g_nonempty(origin.get("component"), "origin.component")
    _g_nonempty(origin.get("version"), "origin.version")
    if source != f"life-goal-activation-proposal:{component}":
        raise ValueError("goal activation source/origin mismatch")


def _prepare_goal_activation_decision(
    self: CognitiveGoalMixin,
    db: Any,
    proposal_id: str,
    *,
    evaluated_state_version: int,
    decision_time: str,
    known_goal_states: Mapping[str, Mapping[str, Any]] | None = None,
    proposal_payload: Mapping[str, Any] | None = None,
    proposal_event_id: str | None = None,
) -> dict[str, Any]:
    if proposal_payload is None:
        row = db.execute(
            "SELECT proposal_json,proposal_event_id FROM goal_activation_proposals "
            "WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        proposal = json.loads(row["proposal_json"])
        proposal_event_id = row["proposal_event_id"]
    else:
        proposal = dict(proposal_payload)
    based_on = proposal["based_on"]["state_version"]
    goal_id = proposal["goal_id"]
    if based_on != evaluated_state_version:
        return {
            "outcome": "deferred", "transition": None,
            "reason": f"stale proposal state_version={based_on}; current state_version={evaluated_state_version}",
        }
    if known_goal_states is None:
        row = db.execute("SELECT goal_json FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
        goal = json.loads(row["goal_json"]) if row is not None else None
    else:
        raw = known_goal_states.get(goal_id)
        goal = dict(raw) if raw is not None else None
    if goal is None:
        return {"outcome": "rejected", "transition": None, "reason": "target goal does not exist"}
    if goal.get("status") != "candidate":
        return {
            "outcome": "rejected", "transition": None,
            "reason": f"target goal is not a candidate (status={goal.get('status')})",
        }
    current_goal_version = goal.get("goal_version")
    if (
        not isinstance(current_goal_version, int)
        or isinstance(current_goal_version, bool)
        or current_goal_version < 1
    ):
        self._raise_cognitive_integrity("target goal has an invalid current version")
    if proposal["expected_goal_version"] != current_goal_version:
        return {
            "outcome": "deferred", "transition": None,
            "reason": (
                f"stale expected_goal_version={proposal['expected_goal_version']}; "
                f"current goal_version={current_goal_version}"
            ),
        }
    transition_id = f"csd-goal-activation-transition:{proposal_id}:{goal_id}"
    transition = {
        "goal_id": goal_id,
        "from_goal_version": current_goal_version,
        "goal_version": current_goal_version + 1,
        "status": "active",
        "transition_id": transition_id,
        "origin_class": goal.get("origin_class"),
        "origin_signal_refs": goal.get("origin_signal_refs"),
        "created_at": goal.get("created_at"),
        "activation_rationale": proposal["rationale"],
        "activated_at": decision_time,
    }
    return {
        "outcome": "accepted",
        "transition": transition,
        "reason": "candidate goal explicitly selected for pursuit; no activity or capability is created",
    }


def _apply_goal_activation_decision(self: CognitiveGoalMixin, db: Any, event: Any) -> None:
    payload = event.payload
    proposal_id = _g_nonempty(payload.get("proposal_id"), "decision.proposal_id")
    proposal = db.execute(
        "SELECT proposal_event_id,decision_event_id FROM goal_activation_proposals "
        "WHERE proposal_id=?", (proposal_id,)
    ).fetchone()
    if proposal is None:
        self._raise_cognitive_integrity("goal activation decision references a missing proposal")
    if proposal["decision_event_id"] is not None:
        self._raise_cognitive_integrity("goal activation proposal has more than one decision")
    if payload.get("proposal_event_id") != proposal["proposal_event_id"]:
        self._raise_cognitive_integrity("goal activation proposal-event mismatch")
    event_row = db.execute("SELECT sequence FROM events WHERE event_id=?", (event.event_id,)).fetchone()
    if event_row is None:
        self._raise_cognitive_integrity("goal activation decision event is missing from history")
    sequence = int(event_row["sequence"])
    current_version = self._authoritative_state_version(db, through_sequence=sequence - 1)
    if payload.get("evaluated_state_version") != current_version:
        self._raise_cognitive_integrity("goal activation decision evaluated against stale state_version")
    prepared = _prepare_goal_activation_decision(
        self, db, proposal_id,
        evaluated_state_version=current_version,
        decision_time=event.occurred_at,
    )
    expected = {
        "proposal_id": proposal_id,
        "proposal_event_id": proposal["proposal_event_id"],
        "outcome": prepared["outcome"],
        "policy": {"id": GOAL_ACTIVATION_POLICY_ID, "version": GOAL_ACTIVATION_POLICY_VERSION},
        "evaluated_state_version": current_version,
        "goal_id": json.loads(db.execute(
            "SELECT proposal_json FROM goal_activation_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()["proposal_json"])["goal_id"],
        "expected_goal_version": json.loads(db.execute(
            "SELECT proposal_json FROM goal_activation_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()["proposal_json"])["expected_goal_version"],
        "transition": prepared["transition"],
        "reason": prepared["reason"],
    }
    if set(payload) != set(expected) or dict(payload) != expected:
        self._raise_cognitive_integrity("goal activation decision differs from deterministic CSD evaluation")
    if event.event_id != f"csd-goal-activation-decision:{proposal_id}":
        self._raise_cognitive_integrity("goal activation decision event ID is not proposal-scoped")
    if event.correlation_id != f"goal-activation-proposal:{proposal_id}":
        self._raise_cognitive_integrity("goal activation decision correlation_id mismatch")
    if event.source != GOAL_DECISION_SOURCE:
        self._raise_cognitive_integrity("goal activation decision source is not CSD authority")

    transition = prepared["transition"]
    if prepared["outcome"] == "accepted":
        goal_id = transition["goal_id"]
        current_row = db.execute("SELECT goal_json FROM goals WHERE goal_id=?", (goal_id,)).fetchone()
        if current_row is None:
            self._raise_cognitive_integrity("accepted activation target disappeared")
        current_goal = json.loads(current_row["goal_json"])
        if (
            current_goal.get("goal_version") != transition["from_goal_version"]
            or current_goal.get("status") != "candidate"
            or current_goal.get("origin_class") != transition["origin_class"]
            or current_goal.get("origin_signal_refs") != transition["origin_signal_refs"]
        ):
            self._raise_cognitive_integrity("goal changed during activation decision")
        activated = {
            **current_goal,
            "goal_version": transition["goal_version"],
            "status": "active",
            "decision_event_id": event.event_id,
            "transition_id": transition["transition_id"],
            "activation_proposal_id": proposal_id,
            "activation_proposal_event_id": proposal["proposal_event_id"],
            "activation_decision_event_id": event.event_id,
            "activation_rationale": transition["activation_rationale"],
            "activated_at": transition["activated_at"],
        }
        goal_json = _g_canonical(activated)
        db.execute(
            "INSERT INTO goal_versions(goal_id,goal_version,decision_event_id,transition_id,goal_json) "
            "VALUES (?,?,?,?,?)",
            (goal_id, transition["goal_version"], event.event_id, transition["transition_id"], goal_json),
        )
        db.execute(
            "UPDATE goals SET goal_version=?,decision_event_id=?,transition_id=?,goal_json=? "
            "WHERE goal_id=?",
            (transition["goal_version"], event.event_id, transition["transition_id"], goal_json, goal_id),
        )
    elif transition is not None:
        self._raise_cognitive_integrity("non-accepted activation decision contains a transition")

    db.execute(
        "UPDATE goal_activation_proposals SET status=?,decision_event_id=? WHERE proposal_id=?",
        (prepared["outcome"], event.event_id, proposal_id),
    )


def _apply_goal_projection_event_v2(
    self: CognitiveGoalMixin, db: Any, event: Any, *, internal: bool
) -> None:
    if event.event_type in {GOAL_BATCH_PROPOSAL_EVENT, GOAL_BATCH_DECISION_EVENT}:
        if event.event_type == GOAL_BATCH_PROPOSAL_EVENT:
            if internal:
                raise ValueError("goal proposal events must use public Event Submit")
            self._validate_goal_proposal_snapshot_version(db, event, internal=internal)
            self._validate_goal_batch_proposal(event)
            payload_json = _g_canonical(dict(event.payload))
            digest = _g_digest(payload_json)
            proposal_id = event.payload["proposal_id"]
            existing = db.execute(
                "SELECT proposal_digest FROM goal_proposals WHERE proposal_id=?", (proposal_id,)
            ).fetchone()
            if existing is not None:
                if existing["proposal_digest"] != digest:
                    raise ValueError(f"goal proposal identity conflict: {proposal_id}")
                return
            db.execute(
                "INSERT INTO goal_proposals(proposal_id,proposal_digest,proposal_event_id,proposal_json,status,decision_event_id) "
                "VALUES (?,?,?,?, 'pending',NULL)",
                (proposal_id, digest, event.event_id, payload_json),
            )
            return
        if not internal or event.source != GOAL_DECISION_SOURCE:
            self._raise_cognitive_integrity("non-authoritative goal decision event")
        self._apply_goal_batch_decision(db, event)
        return

    if event.event_type == GOAL_ACTIVATION_PROPOSAL_EVENT:
        if internal:
            raise ValueError("goal activation proposals must use public Event Submit")
        self._validate_goal_proposal_snapshot_version(db, event, internal=internal)
        _validate_goal_activation_proposal(event)
        payload_json = _g_canonical(dict(event.payload))
        digest = _g_digest(payload_json)
        proposal_id = event.payload["proposal_id"]
        existing = db.execute(
            "SELECT proposal_digest FROM goal_activation_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if existing is not None:
            if existing["proposal_digest"] != digest:
                raise ValueError(f"goal activation proposal identity conflict: {proposal_id}")
            return
        db.execute(
            "INSERT INTO goal_activation_proposals(proposal_id,proposal_digest,proposal_event_id,proposal_json,status,decision_event_id) "
            "VALUES (?,?,?,?, 'pending',NULL)",
            (proposal_id, digest, event.event_id, payload_json),
        )
        return

    if event.event_type == GOAL_PAUSE_RESUME_PROPOSAL_EVENT:
        if internal:
            raise ValueError("goal pause/resume proposals must use public Event Submit")
        self._validate_goal_proposal_snapshot_version(db, event, internal=internal)
        _validate_goal_pause_resume_proposal(event)
        payload_json = _g_canonical(dict(event.payload))
        digest = _g_digest(payload_json)
        proposal_id = event.payload["proposal_id"]
        existing = db.execute(
            "SELECT proposal_digest FROM goal_pause_resume_proposals WHERE proposal_id=?",
            (proposal_id,),
        ).fetchone()
        if existing is not None:
            if existing["proposal_digest"] != digest:
                raise ValueError(f"goal pause/resume proposal identity conflict: {proposal_id}")
            return
        db.execute(
            "INSERT INTO goal_pause_resume_proposals(proposal_id,proposal_digest,proposal_event_id,proposal_json,status,decision_event_id) "
            "VALUES (?,?,?,?, 'pending',NULL)",
            (proposal_id, digest, event.event_id, payload_json),
        )
        return

    if event.event_type == GOAL_PAUSE_RESUME_DECISION_EVENT:
        if not internal or event.source != GOAL_DECISION_SOURCE:
            self._raise_cognitive_integrity("non-authoritative goal pause/resume decision event")
        _apply_goal_pause_resume_decision(self, db, event)
        return

    if event.event_type == GOAL_ACTIVATION_DECISION_EVENT:
        if not internal or event.source != GOAL_DECISION_SOURCE:
            self._raise_cognitive_integrity("non-authoritative goal activation decision event")
        _apply_goal_activation_decision(self, db, event)
        return
    self._raise_cognitive_integrity("unhandled goal projection event")


def _evaluate_goal_activation_proposal(
    self: CognitiveGoalMixin, proposal_id: str
) -> dict[str, Any]:
    _g_nonempty(proposal_id, "proposal_id")
    from .cognitive import CognitiveEvent
    with self._tx() as db:
        row = db.execute(
            "SELECT proposal_event_id,decision_event_id,proposal_json "
            "FROM goal_activation_proposals WHERE proposal_id=?", (proposal_id,)
        ).fetchone()
        if row is None:
            raise KeyError(proposal_id)
        if row["decision_event_id"] is not None:
            return {"status": "already_decided", "decision_event_id": row["decision_event_id"]}
        self._assert_accepted_projection_consistent()
        self._assert_motivation_projection_consistent()
        self._assert_goal_projection_consistent()
        current_version = self._authoritative_state_version(db)
        prepared = _prepare_goal_activation_decision(
            self, db, proposal_id,
            evaluated_state_version=current_version,
            decision_time=datetime.now(timezone.utc).isoformat(),
        )
        now = prepared["transition"]["activated_at"] if prepared["transition"] else datetime.now(timezone.utc).isoformat()
        event = CognitiveEvent(
            event_id=f"csd-goal-activation-decision:{proposal_id}",
            occurred_at=now,
            correlation_id=f"goal-activation-proposal:{proposal_id}",
            event_type=GOAL_ACTIVATION_DECISION_EVENT,
            source=GOAL_DECISION_SOURCE,
            payload={
                "proposal_id": proposal_id,
                "proposal_event_id": row["proposal_event_id"],
                "outcome": prepared["outcome"],
                "policy": {"id": GOAL_ACTIVATION_POLICY_ID, "version": GOAL_ACTIVATION_POLICY_VERSION},
                "evaluated_state_version": current_version,
                "goal_id": json.loads(row["proposal_json"])["goal_id"],
                "expected_goal_version": json.loads(row["proposal_json"])["expected_goal_version"],
                "transition": prepared["transition"],
                "reason": prepared["reason"],
            },
        )
        payload_json = self._validate_event(event, internal=True)
        appended = self._append_event_in_transaction(db, event, payload_json, internal=True)
        return {
            "status": prepared["outcome"],
            "decision_event_id": event.event_id,
            "sequence": appended["sequence"],
            "reason": prepared["reason"],
        }


def _assert_goal_projection_consistent_v2(self: CognitiveGoalMixin) -> None:
    """Reconcile candidate and activation histories, all goal versions, and latest goals."""
    self._assert_motivation_projection_consistent()
    event_types = (
        GOAL_BATCH_PROPOSAL_EVENT, GOAL_BATCH_DECISION_EVENT,
        GOAL_ACTIVATION_PROPOSAL_EVENT, GOAL_ACTIVATION_DECISION_EVENT,
        GOAL_PAUSE_RESUME_PROPOSAL_EVENT, GOAL_PAUSE_RESUME_DECISION_EVENT,
    )
    placeholders = ",".join("?" for _ in event_types)
    rows = self._db.execute(
        f"SELECT sequence,event_id,event_type FROM events WHERE event_type IN ({placeholders}) ORDER BY sequence",
        event_types,
    ).fetchall()
    batch_proposals: dict[str, dict[str, Any]] = {}
    batch_decisions: dict[str, tuple[str, dict[str, Any]]] = {}
    activation_proposals: dict[str, dict[str, Any]] = {}
    activation_decisions: dict[str, tuple[str, dict[str, Any]]] = {}
    pause_resume_proposals: dict[str, dict[str, Any]] = {}
    pause_resume_decisions: dict[str, tuple[str, dict[str, Any]]] = {}
    expected_goals: dict[str, dict[str, Any]] = {}
    expected_versions: dict[tuple[str, int], tuple[str, str, str]] = {}

    for row in rows:
        # This replay validates every goal decision against the accumulated
        # event-derived state below. Suppress the per-event contextual callback
        # here to avoid recursively replaying the same complete history.
        record = self.get_event(
            row["event_id"], _validate_decision_context=False
        )
        payload = record["payload"]
        event_type = row["event_type"]
        if event_type == GOAL_BATCH_PROPOSAL_EVENT:
            proposal_id = _g_nonempty(payload.get("proposal_id"), "goal proposal_id")
            self._validate_goal_proposal_snapshot_version(self._db, record, internal=True)
            self._validate_goal_batch_proposal(record)
            canonical = _g_canonical(payload)
            digest = _g_digest(canonical)
            prior = batch_proposals.get(proposal_id)
            if prior is None:
                batch_proposals[proposal_id] = {
                    "digest": digest, "event_id": row["event_id"],
                    "json": canonical, "payload": payload,
                }
            elif prior["digest"] != digest:
                self._raise_cognitive_integrity("goal proposal identity conflict in event history")
            continue

        if event_type == GOAL_ACTIVATION_PROPOSAL_EVENT:
            proposal_id = _g_nonempty(payload.get("proposal_id"), "activation proposal_id")
            self._validate_goal_proposal_snapshot_version(self._db, record, internal=True)
            _validate_goal_activation_proposal(record)
            canonical = _g_canonical(payload)
            digest = _g_digest(canonical)
            prior = activation_proposals.get(proposal_id)
            if prior is None:
                activation_proposals[proposal_id] = {
                    "digest": digest, "event_id": row["event_id"],
                    "json": canonical, "payload": payload,
                }
            elif prior["digest"] != digest:
                self._raise_cognitive_integrity("goal activation proposal identity conflict in event history")
            continue

        if event_type == GOAL_PAUSE_RESUME_PROPOSAL_EVENT:
            proposal_id = _g_nonempty(payload.get("proposal_id"), "pause/resume proposal_id")
            self._validate_goal_proposal_snapshot_version(self._db, record, internal=True)
            _validate_goal_pause_resume_proposal(record)
            canonical = _g_canonical(payload)
            digest = _g_digest(canonical)
            prior = pause_resume_proposals.get(proposal_id)
            if prior is None:
                pause_resume_proposals[proposal_id] = {
                    "digest": digest, "event_id": row["event_id"],
                    "json": canonical, "payload": payload,
                }
            elif prior["digest"] != digest:
                self._raise_cognitive_integrity("goal pause/resume proposal identity conflict in event history")
            continue

        if event_type == GOAL_BATCH_DECISION_EVENT:
            proposal_id = _g_nonempty(payload.get("proposal_id"), "goal decision proposal_id")
            if proposal_id in batch_decisions or proposal_id not in batch_proposals:
                self._raise_cognitive_integrity("goal decision has duplicate or missing proposal")
            proposal = batch_proposals[proposal_id]
            current_version = self._authoritative_state_version(
                self._db, through_sequence=int(row["sequence"]) - 1
            )
            prepared = self._prepare_goal_batch_decision(
                self._db, proposal_id,
                evaluated_state_version=current_version,
                before_sequence=int(row["sequence"]),
                known_goal_ids=set(expected_goals),
                proposal_payload=proposal["payload"],
            )
            expected = {
                "proposal_id": proposal_id,
                "proposal_event_id": proposal["event_id"],
                "outcome": prepared["outcome"],
                "policy": {"id": GOAL_POLICY_ID, "version": GOAL_POLICY_VERSION},
                "evaluated_state_version": current_version,
                "transitions": prepared["transitions"],
                "reason": prepared["reason"],
            }
            if (
                record["source"] != GOAL_DECISION_SOURCE
                or record["correlation_id"] != f"goal-proposal:{proposal_id}"
                or record["event_id"] != f"csd-goal-decision:{proposal_id}"
                or payload != expected
            ):
                self._raise_cognitive_integrity("goal batch decision differs from deterministic CSD evaluation")
            batch_decisions[proposal_id] = (row["event_id"], payload)
            if prepared["outcome"] == "accepted":
                for transition in prepared["transitions"]:
                    goal_id = transition["goal_id"]
                    if goal_id in expected_goals:
                        self._raise_cognitive_integrity("duplicate accepted goal identity")
                    goal = next(item for item in proposal["payload"]["goals"] if item["goal_id"] == goal_id)
                    transition_id = f"csd-goal-transition:{proposal_id}:{goal_id}"
                    state = {
                        **goal, "goal_version": 1, "status": "candidate",
                        "origin_class": transition["origin_class"],
                        "origin_signal_refs": transition["origin_signal_refs"],
                        "proposal_id": proposal_id,
                        "proposal_event_id": proposal["event_id"],
                        "decision_event_id": row["event_id"],
                        "transition_id": transition_id,
                        "created_at": record["occurred_at"],
                    }
                    state_json = _g_canonical(state)
                    expected_goals[goal_id] = state
                    expected_versions[(goal_id, 1)] = (row["event_id"], transition_id, state_json)
            continue

        if event_type == GOAL_PAUSE_RESUME_DECISION_EVENT:
            proposal_id = _g_nonempty(payload.get("proposal_id"), "pause/resume decision proposal_id")
            if proposal_id in pause_resume_decisions or proposal_id not in pause_resume_proposals:
                self._raise_cognitive_integrity("goal pause/resume decision has duplicate or missing proposal")
            proposal = pause_resume_proposals[proposal_id]
            current_version = self._authoritative_state_version(
                self._db, through_sequence=int(row["sequence"]) - 1
            )
            prepared = _prepare_goal_pause_resume_decision(
                self, self._db, proposal_id,
                evaluated_state_version=current_version,
                decision_time=record["occurred_at"],
                known_goal_states=expected_goals,
                proposal_payload=proposal["payload"],
            )
            expected = {
                "proposal_id": proposal_id,
                "proposal_event_id": proposal["event_id"],
                "outcome": prepared["outcome"],
                "policy": {"id": GOAL_PAUSE_RESUME_POLICY_ID, "version": GOAL_PAUSE_RESUME_POLICY_VERSION},
                "evaluated_state_version": current_version,
                "goal_id": proposal["payload"]["goal_id"],
                "expected_goal_version": proposal["payload"]["expected_goal_version"],
                "operation": proposal["payload"]["operation"],
                "transition": prepared["transition"],
                "reason": prepared["reason"],
            }
            if (
                record["source"] != GOAL_DECISION_SOURCE
                or record["correlation_id"] != f"goal-pause-resume-proposal:{proposal_id}"
                or record["event_id"] != f"csd-goal-pause-resume-decision:{proposal_id}"
                or payload != expected
            ):
                self._raise_cognitive_integrity("goal pause/resume decision differs from deterministic CSD evaluation")
            pause_resume_decisions[proposal_id] = (row["event_id"], payload)
            if prepared["outcome"] == "accepted":
                transition = prepared["transition"]
                goal_id = transition["goal_id"]
                prior = expected_goals.get(goal_id)
                if prior is None:
                    self._raise_cognitive_integrity("pause/resume transition references missing goal")
                state = {
                    **prior,
                    "goal_version": transition["goal_version"],
                    "status": transition["status"],
                    "decision_event_id": row["event_id"],
                    "transition_id": transition["transition_id"],
                    "lifecycle_proposal_id": proposal_id,
                    "lifecycle_proposal_event_id": proposal["event_id"],
                    "lifecycle_decision_event_id": row["event_id"],
                    "lifecycle_operation": transition["operation"],
                    "lifecycle_rationale": transition["rationale"],
                    "lifecycle_transitioned_at": transition["transitioned_at"],
                }
                state_json = _g_canonical(state)
                expected_goals[goal_id] = state
                expected_versions[(goal_id, transition["goal_version"])] = (
                    row["event_id"], transition["transition_id"], state_json
                )
            continue

        proposal_id = _g_nonempty(payload.get("proposal_id"), "activation decision proposal_id")
        if proposal_id in activation_decisions or proposal_id not in activation_proposals:
            self._raise_cognitive_integrity("goal activation decision has duplicate or missing proposal")
        proposal = activation_proposals[proposal_id]
        current_version = self._authoritative_state_version(
            self._db, through_sequence=int(row["sequence"]) - 1
        )
        prepared = _prepare_goal_activation_decision(
            self, self._db, proposal_id,
            evaluated_state_version=current_version,
            decision_time=record["occurred_at"],
            known_goal_states=expected_goals,
            proposal_payload=proposal["payload"],
            proposal_event_id=proposal["event_id"],
        )
        expected = {
            "proposal_id": proposal_id,
            "proposal_event_id": proposal["event_id"],
            "outcome": prepared["outcome"],
            "policy": {"id": GOAL_ACTIVATION_POLICY_ID, "version": GOAL_ACTIVATION_POLICY_VERSION},
            "evaluated_state_version": current_version,
            "goal_id": proposal["payload"]["goal_id"],
            "expected_goal_version": proposal["payload"]["expected_goal_version"],
            "transition": prepared["transition"],
            "reason": prepared["reason"],
        }
        if (
            record["source"] != GOAL_DECISION_SOURCE
            or record["correlation_id"] != f"goal-activation-proposal:{proposal_id}"
            or record["event_id"] != f"csd-goal-activation-decision:{proposal_id}"
            or payload != expected
        ):
            self._raise_cognitive_integrity("goal activation decision differs from deterministic CSD evaluation")
        activation_decisions[proposal_id] = (row["event_id"], payload)
        if prepared["outcome"] == "accepted":
            transition = prepared["transition"]
            goal_id = transition["goal_id"]
            prior = expected_goals.get(goal_id)
            if prior is None:
                self._raise_cognitive_integrity("activation transition references missing goal")
            state = {
                **prior,
                "goal_version": transition["goal_version"],
                "status": "active",
                "decision_event_id": row["event_id"],
                "transition_id": transition["transition_id"],
                "activation_proposal_id": proposal_id,
                "activation_proposal_event_id": proposal["event_id"],
                "activation_decision_event_id": row["event_id"],
                "activation_rationale": transition["activation_rationale"],
                "activated_at": transition["activated_at"],
            }
            state_json = _g_canonical(state)
            expected_goals[goal_id] = state
            expected_versions[(goal_id, transition["goal_version"])] = (
                row["event_id"], transition["transition_id"], state_json
            )

    # Compare both proposal projections with their immutable event histories.
    for table, expected_items, decision_items in (
        ("goal_proposals", batch_proposals, batch_decisions),
        ("goal_activation_proposals", activation_proposals, activation_decisions),
        ("goal_pause_resume_proposals", pause_resume_proposals, pause_resume_decisions),
    ):
        rows = self._db.execute(
            f"SELECT proposal_id,proposal_digest,proposal_event_id,proposal_json,status,decision_event_id FROM {table}"
        ).fetchall()
        if len(rows) != len(expected_items):
            self._raise_cognitive_integrity(f"{table} count differs from event history")
        for row in rows:
            source = expected_items.get(row["proposal_id"])
            decision = decision_items.get(row["proposal_id"])
            status = decision[1]["outcome"] if decision else "pending"
            decision_id = decision[0] if decision else None
            if source is None or (
                row["proposal_digest"] != source["digest"]
                or row["proposal_event_id"] != source["event_id"]
                or row["proposal_json"] != source["json"]
                or row["status"] != status
                or row["decision_event_id"] != decision_id
            ):
                self._raise_cognitive_integrity(f"{table} differs from event history")

    version_rows = self._db.execute(
        "SELECT goal_id,goal_version,decision_event_id,transition_id,goal_json FROM goal_versions"
    ).fetchall()
    if len(version_rows) != len(expected_versions):
        self._raise_cognitive_integrity("goal version projection count differs from event history")
    for row in version_rows:
        expected = expected_versions.get((row["goal_id"], int(row["goal_version"])))
        if expected is None or (
            row["decision_event_id"], row["transition_id"], row["goal_json"]
        ) != expected:
            self._raise_cognitive_integrity("goal version projection differs from decision events")

    goal_rows = self._db.execute(
        "SELECT goal_id,goal_version,decision_event_id,transition_id,goal_json FROM goals"
    ).fetchall()
    if len(goal_rows) != len(expected_goals):
        self._raise_cognitive_integrity("latest goal projection count differs from event history")
    for row in goal_rows:
        expected = expected_goals.get(row["goal_id"])
        expected_json = _g_canonical(expected) if expected is not None else None
        if expected is None or (
            int(row["goal_version"]) != expected["goal_version"]
            or row["decision_event_id"] != expected["decision_event_id"]
            or row["transition_id"] != expected["transition_id"]
            or row["goal_json"] != expected_json
        ):
            self._raise_cognitive_integrity("latest goal projection differs from event history")


class CognitiveGoalLifecycleMixin:
    """CSD-authoritative candidate, activation, and pause/resume goal transitions."""

    def _apply_goal_projection_event(self, db: Any, event: Any, *, internal: bool) -> None:
        _apply_goal_projection_event_v2(self, db, event, internal=internal)

    def evaluate_goal_activation_proposal(self, proposal_id: str) -> dict[str, Any]:
        return _evaluate_goal_activation_proposal(self, proposal_id)

    def evaluate_goal_pause_resume_proposal(self, proposal_id: str) -> dict[str, Any]:
        return _evaluate_goal_pause_resume_proposal(self, proposal_id)

    def _assert_goal_projection_consistent(self) -> None:
        if not self._db.in_transaction:
            with self._read_tx():
                _assert_goal_projection_consistent_v2(self)
            return
        _assert_goal_projection_consistent_v2(self)

