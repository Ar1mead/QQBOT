from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
    GOAL_BATCH_DECISION_EVENT,
    GOAL_BATCH_PROPOSAL_EVENT,
    INTERACTION_EVENT,
    MOTIVATION_PROPOSAL_EVENT,
)
from core.csd.cognitive import OBSERVATION_EVENT
from core.csd.goals import (
    GOAL_ACTIVATION_DECISION_EVENT,
    GOAL_ACTIVATION_PROPOSAL_EVENT,
)
from core.life_engine import CognitiveStoreLifeSnapshotReader, CognitiveStoreLifeProposalSink
from core.life_engine import ChoiceProposal, DeliberationProposal, validate_life_proposal


def event(event_id, event_type, source, payload, *, at="2026-11-15T08:00:00+00:00"):
    return CognitiveEvent(
        event_id=event_id,
        occurred_at=at,
        correlation_id=f"test:{event_id}",
        event_type=event_type,
        source=source,
        payload=payload,
    )


def add_internal_signal(store: CognitiveMemoryStore, suffix: str = "one") -> str:
    interaction_id = f"interaction-{suffix}"
    store.submit_event(event(
        interaction_id, INTERACTION_EVENT, "interaction-adapter:test",
        {
            "encounter_id": f"encounter-{suffix}",
            "subject_ref": f"topic:{suffix}",
            "evidence_kind": "voluntary_selection",
            "origin": "internal_state",
            "context": "synthetic test selection",
            "meaningful_alternatives": True,
            "choice_set_refs": [f"item:{suffix}", "item:other"],
            "selected_ref": f"item:{suffix}",
            "origin_event_id": None,
            "related_event_id": None,
            "adapter": {"component": "test", "version": "0.1"},
            "session_scope": "test",
        },
    ))
    proposal_id = f"motivation-{suffix}"
    store.submit_event(event(
        f"motivation-event-{suffix}", MOTIVATION_PROPOSAL_EVENT,
        "motivation-proposal:test",
        {
            "proposal_id": proposal_id,
            "operation": "create",
            "kind": "interest",
            "subject_ref": f"topic:{suffix}",
            "scope": "general",
            "statement": f"An emerging interest in {suffix}.",
            "supporting_event_ids": [interaction_id],
            "counter_evidence_event_ids": [],
            "new_signal_id": f"signal-{suffix}",
            "target_signal_id": None,
            "target_signal_version": None,
            "requested_interest_stage": "tentative",
            "rationale": "synthetic test hypothesis",
            "origin": {"component": "test", "version": "0.1"},
            "based_on": {"state_version": store.get_state_snapshot()["state_version"]},
        },
        at="2026-11-15T08:01:00+00:00",
    ))
    result = store.evaluate_motivation_proposal(proposal_id)
    if result["status"] != "accepted":
        raise AssertionError(result)
    return f"signal-{suffix}"


def add_user_requested_signal(store: CognitiveMemoryStore) -> str:
    store.submit_event(event(
        "user-request-observation", OBSERVATION_EVENT, "test.observation",
        {
            "observation_id": "obs-user-request",
            "observation_kind": "user_message",
            "content": "Please look into this subject.",
            "source_ref": "fixture://user-request",
            "observed_at": "2026-11-15T08:00:00+00:00",
            "coverage": {"modality": "text", "complete_for_fixture": True},
        },
    ))
    store.submit_event(event(
        "user-request-interaction", INTERACTION_EVENT,
        "interaction-adapter:test",
        {
            "encounter_id": "encounter-user-request",
            "subject_ref": "topic:user-topic",
            "evidence_kind": "user_requested_action",
            "origin": "user_request",
            "context": "The user explicitly requested this subject.",
            "meaningful_alternatives": False,
            "choice_set_refs": [],
            "selected_ref": "item:user-topic",
            "origin_event_id": "user-request-observation",
            "related_event_id": None,
            "adapter": {"component": "test", "version": "0.1"},
            "session_scope": "test",
        },
    ))
    store.submit_event(event(
        "user-motivation-event", MOTIVATION_PROPOSAL_EVENT,
        "motivation-proposal:test",
        {
            "proposal_id": "user-motivation",
            "operation": "create",
            "kind": "interest",
            "subject_ref": "topic:user-topic",
            "scope": "general",
            "statement": "An interest connected to a user request.",
            "supporting_event_ids": ["user-request-interaction"],
            "counter_evidence_event_ids": [],
            "new_signal_id": "user-signal",
            "target_signal_id": None,
            "target_signal_version": None,
            "requested_interest_stage": "tentative",
            "rationale": "Synthetic test hypothesis.",
            "origin": {"component": "test", "version": "0.1"},
            "based_on": {"state_version": store.get_state_snapshot()["state_version"]},
        },
        at="2026-11-15T08:01:00+00:00",
    ))
    result = store.evaluate_motivation_proposal("user-motivation")
    if result["status"] != "accepted":
        raise AssertionError(result)
    return "user-signal"


def goal_event(
    proposal_id: str,
    signal_ids: list[str],
    *,
    state_version: int,
    goals: list[dict] | None = None,
    event_id: str | None = None,
):
    if goals is None:
        goals = [{
            "goal_id": f"goal-{proposal_id}",
            "desired_condition": "Understand the subject more deeply.",
            "origin_signal_ids": signal_ids,
            "rationale": "The subject remains interesting.",
            "success_condition": "A coherent explanation is recorded.",
            "stop_condition": "Further inquiry no longer adds value.",
            "review_condition": "Review after new relevant evidence.",
        }]
    return event(
        event_id or f"goal-proposal-event-{proposal_id}",
        GOAL_BATCH_PROPOSAL_EVENT,
        "life-goal-proposal:test.deliberator",
        {
            "proposal_id": proposal_id,
            "based_on": {"state_version": state_version},
            "goals": goals,
            "choice": {"disposition": "no_op", "rationale": "No activity is selected now."},
            "origin": {"component": "test.deliberator", "version": "0.1"},
            "contract_version": "life.goal_batch_proposed.v1",
        },
        at="2026-11-15T08:02:00+00:00",
    )


class CSDGoalStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "goals.sqlite3"
        self.store = CognitiveMemoryStore(self.path)

    def tearDown(self):
        try:
            self.store.close()
        except sqlite3.ProgrammingError:
            pass
        self.temp_dir.cleanup()

    def test_candidate_batch_is_persisted_atomically_and_exposed_to_life_engine(self):
        signal_id = add_internal_signal(self.store)
        before = self.store.get_state_snapshot()["state_version"]
        proposal = goal_event("batch-1", [signal_id], state_version=before)
        self.store.submit_event(proposal)
        result = self.store.evaluate_goal_batch_proposal("batch-1")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before + 1)
        goals = self.store.get_goals()
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0]["status"], "candidate")
        self.assertEqual(goals[0]["goal_version"], 1)
        self.assertEqual(goals[0]["origin_class"], "internally_initiated")
        self.assertEqual(
            goals[0]["origin_signal_refs"],
            [{"signal_id": signal_id, "signal_version": 1}],
        )
        life = CognitiveStoreLifeSnapshotReader(self.store).get_life_snapshot()
        self.assertEqual(len(life.goals), 1)
        self.assertEqual(life.goals[0].status, "candidate")

    def test_no_op_choice_can_coexist_with_candidate_creation(self):
        signal_id = add_internal_signal(self.store)
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_event("noop-with-goal", [signal_id], state_version=version))
        result = self.store.evaluate_goal_batch_proposal("noop-with-goal")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(self.store.get_goals()[0]["status"], "candidate")

    def test_stale_goal_proposal_is_deferred_without_rebasing(self):
        signal_id = add_internal_signal(self.store, "stale")
        based_on = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_event("stale-goal", [signal_id], state_version=based_on))
        add_internal_signal(self.store, "later")
        before = self.store.get_state_snapshot()["state_version"]
        result = self.store.evaluate_goal_batch_proposal("stale-goal")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before)
        self.assertEqual(self.store.get_goals(), [])
        self.assertEqual(self.store.get_goal_proposal("stale-goal")["status"], "deferred")

    def test_missing_or_inactive_source_signal_rejects_whole_batch(self):
        signal_id = add_internal_signal(self.store, "known")
        version = self.store.get_state_snapshot()["state_version"]
        proposal = goal_event(
            "bad-source", [signal_id, "signal-does-not-exist"],
            state_version=version,
            goals=[
                {
                    "goal_id": "goal-valid",
                    "desired_condition": "Valid goal",
                    "origin_signal_ids": [signal_id],
                    "rationale": "Reason",
                    "success_condition": "Success",
                    "stop_condition": "Stop",
                    "review_condition": "Review",
                },
                {
                    "goal_id": "goal-invalid",
                    "desired_condition": "Invalid source goal",
                    "origin_signal_ids": ["signal-does-not-exist"],
                    "rationale": "Reason",
                    "success_condition": "Success",
                    "stop_condition": "Stop",
                    "review_condition": "Review",
                },
            ],
        )
        self.store.submit_event(proposal)
        result = self.store.evaluate_goal_batch_proposal("bad-source")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.get_goals(), [])

    def test_existing_goal_identity_rejects_entire_batch(self):
        signal_id = add_internal_signal(self.store, "collision")
        version = self.store.get_state_snapshot()["state_version"]
        first = goal_event("first", [signal_id], state_version=version)
        self.store.submit_event(first)
        self.assertEqual(self.store.evaluate_goal_batch_proposal("first")["status"], "accepted")
        version = self.store.get_state_snapshot()["state_version"]
        second = goal_event(
            "second", [signal_id], state_version=version,
            goals=[
                {
                    "goal_id": "goal-new",
                    "desired_condition": "A new goal",
                    "origin_signal_ids": [signal_id],
                    "rationale": "Reason",
                    "success_condition": "Success",
                    "stop_condition": "Stop",
                    "review_condition": "Review",
                },
                {
                    "goal_id": "goal-first",
                    "desired_condition": "Conflicting goal",
                    "origin_signal_ids": [signal_id],
                    "rationale": "Reason",
                    "success_condition": "Success",
                    "stop_condition": "Stop",
                    "review_condition": "Review",
                },
            ],
        )
        self.store.submit_event(second)
        self.assertEqual(self.store.evaluate_goal_batch_proposal("second")["status"], "rejected")
        self.assertEqual([item["goal_id"] for item in self.store.get_goals()], ["goal-first"])

    def test_identical_proposal_retry_is_idempotent_and_conflict_rolls_back(self):
        signal_id = add_internal_signal(self.store, "identity")
        version = self.store.get_state_snapshot()["state_version"]
        proposal = goal_event("identity", [signal_id], state_version=version)
        self.assertEqual(self.store.submit_event(proposal)["status"], "accepted")
        self.assertEqual(self.store.submit_event(proposal)["status"], "duplicate")
        conflicting = goal_event(
            "identity", [signal_id], state_version=version,
            event_id="different-event-id",
            goals=[{
                "goal_id": "different-goal",
                "desired_condition": "Different content",
                "origin_signal_ids": [signal_id],
                "rationale": "Reason",
                "success_condition": "Success",
                "stop_condition": "Stop",
                "review_condition": "Review",
            }],
        )
        before = self.store.get_state_snapshot()["event_count"]
        with self.assertRaises(ValueError):
            self.store.submit_event(conflicting)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)

    def test_public_path_cannot_append_goal_decision_event(self):
        with self.assertRaises(ValueError):
            self.store.submit_event(event(
                "csd-goal-decision:forged",
                GOAL_BATCH_DECISION_EVENT,
                "csd.authority.v1",
                {},
            ))


    def test_user_requested_origin_is_derived_by_csd(self):
        signal_id = add_user_requested_signal(self.store)
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_event("user-origin", [signal_id], state_version=version))
        result = self.store.evaluate_goal_batch_proposal("user-origin")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(self.store.get_goal("goal-user-origin")["origin_class"], "user_requested")

    def test_user_origin_with_emerging_voluntary_pattern_becomes_mixed_origin(self):
        signal_id = add_user_requested_signal(self.store)
        self.store.submit_event(event(
            "user-topic-voluntary-1", INTERACTION_EVENT, "interaction-adapter:test",
            {
                "encounter_id": "user-topic-encounter-1",
                "subject_ref": "topic:user-topic",
                "evidence_kind": "voluntary_selection",
                "origin": "internal_state",
                "context": "A later independent choice.",
                "meaningful_alternatives": True,
                "choice_set_refs": ["item:user-topic", "item:other"],
                "selected_ref": "item:user-topic",
                "origin_event_id": None,
                "related_event_id": None,
                "adapter": {"component": "test", "version": "0.1"},
                "session_scope": "test",
            },
            at="2026-11-15T08:02:00+00:00",
        ))
        self.store.submit_event(event(
            "user-topic-voluntary-2", INTERACTION_EVENT, "interaction-adapter:test",
            {
                "encounter_id": "user-topic-encounter-2",
                "subject_ref": "topic:user-topic",
                "evidence_kind": "return_visit",
                "origin": "internal_state",
                "context": "A second independent return.",
                "meaningful_alternatives": True,
                "choice_set_refs": ["item:user-topic", "item:other"],
                "selected_ref": "item:user-topic",
                "origin_event_id": None,
                "related_event_id": "user-topic-voluntary-1",
                "adapter": {"component": "test", "version": "0.1"},
                "session_scope": "test",
            },
            at="2026-11-15T08:04:00+00:00",
        ))
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(event(
            "user-interest-reinforce-event", MOTIVATION_PROPOSAL_EVENT,
            "motivation-proposal:test",
            {
                "proposal_id": "user-interest-reinforce",
                "operation": "reinforce",
                "kind": "interest",
                "subject_ref": "topic:user-topic",
                "scope": "general",
                "statement": None,
                "supporting_event_ids": ["user-topic-voluntary-1", "user-topic-voluntary-2"],
                "counter_evidence_event_ids": [],
                "new_signal_id": None,
                "target_signal_id": signal_id,
                "target_signal_version": 1,
                "requested_interest_stage": "emerging",
                "rationale": "Two independent voluntary encounters.",
                "origin": {"component": "test", "version": "0.1"},
                "based_on": {"state_version": version},
            },
            at="2026-11-15T08:05:00+00:00",
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("user-interest-reinforce")["status"],
            "accepted",
        )
        signal = self.store.get_motivation_signal(signal_id)
        self.assertEqual(signal["origin_class"], "user_requested_encounter")
        self.assertEqual(signal["interest_stage"], "emerging")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_event("mixed-origin", [signal_id], state_version=version))
        self.assertEqual(
            self.store.evaluate_goal_batch_proposal("mixed-origin")["status"],
            "accepted",
        )
        self.assertEqual(self.store.get_goal("goal-mixed-origin")["origin_class"], "mixed_origin")

    def test_multi_goal_batch_increments_shared_version_once(self):
        signal_id = add_internal_signal(self.store, "multi")
        version = self.store.get_state_snapshot()["state_version"]
        goals = []
        for suffix in ("a", "b"):
            goals.append({
                "goal_id": f"goal-multi-{suffix}",
                "desired_condition": f"Understand aspect {suffix}.",
                "origin_signal_ids": [signal_id],
                "rationale": "A related candidate.",
                "success_condition": "A useful result is recorded.",
                "stop_condition": "Further work has low value.",
                "review_condition": "Review after new evidence.",
            })
        self.store.submit_event(goal_event(
            "multi", [signal_id], state_version=version, goals=goals
        ))
        result = self.store.evaluate_goal_batch_proposal("multi")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], version + 1)
        self.assertEqual(
            [item["goal_id"] for item in self.store.get_goals()],
            ["goal-multi-a", "goal-multi-b"],
        )


    def test_goal_keeps_historical_signal_version_after_signal_is_revised(self):
        signal_id = add_internal_signal(self.store, "historical")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_event("historical-goal", [signal_id], state_version=version))
        self.assertEqual(
            self.store.evaluate_goal_batch_proposal("historical-goal")["status"],
            "accepted",
        )
        self.store.submit_event(event(
            "historical-reinforcement-interaction", INTERACTION_EVENT,
            "interaction-adapter:test",
            {
                "encounter_id": "historical-encounter-2",
                "subject_ref": "topic:historical",
                "evidence_kind": "voluntary_selection",
                "origin": "internal_state",
                "context": "A later independent choice.",
                "meaningful_alternatives": True,
                "choice_set_refs": ["item:historical", "item:other"],
                "selected_ref": "item:historical",
                "origin_event_id": None,
                "related_event_id": None,
                "adapter": {"component": "test", "version": "0.1"},
                "session_scope": "test",
            },
            at="2026-11-15T08:03:00+00:00",
        ))
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(event(
            "historical-reinforcement-proposal-event",
            MOTIVATION_PROPOSAL_EVENT,
            "motivation-proposal:test",
            {
                "proposal_id": "historical-reinforcement",
                "operation": "reinforce",
                "kind": "interest",
                "subject_ref": "topic:historical",
                "scope": "general",
                "statement": None,
                "supporting_event_ids": ["historical-reinforcement-interaction"],
                "counter_evidence_event_ids": [],
                "new_signal_id": None,
                "target_signal_id": signal_id,
                "target_signal_version": 1,
                "requested_interest_stage": "tentative",
                "rationale": "A later independent encounter.",
                "origin": {"component": "test", "version": "0.1"},
                "based_on": {"state_version": version},
            },
            at="2026-11-15T08:04:00+00:00",
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("historical-reinforcement")["status"],
            "accepted",
        )
        revised = self.store.get_motivation_signal(signal_id)
        self.assertEqual(revised["signal_version"], 2)
        goal = self.store.get_goal("goal-historical-goal")
        self.assertEqual(
            goal["origin_signal_refs"],
            [{"signal_id": signal_id, "signal_version": 1}],
        )
        self.store.recover()
        self.assertEqual(
            self.store.get_goal("goal-historical-goal")["origin_signal_refs"],
            [{"signal_id": signal_id, "signal_version": 1}],
        )

    def test_goal_version_projection_corruption_is_detected_and_recovered(self):
        signal_id = add_internal_signal(self.store, "version-corrupt")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_event("version-corrupt", [signal_id], state_version=version))
        self.assertEqual(
            self.store.evaluate_goal_batch_proposal("version-corrupt")["status"],
            "accepted",
        )
        self.store._db.execute(
            "UPDATE goal_versions SET goal_json='{}' WHERE goal_id='goal-version-corrupt'"
        )
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_goals()
        self.store.recover()
        self.assertEqual(
            self.store.get_goal("goal-version-corrupt")["status"],
            "candidate",
        )

    def test_recovery_rebuilds_candidate_goal_without_activation(self):
        signal_id = add_internal_signal(self.store, "recovery")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_event("recover-goal", [signal_id], state_version=version))
        self.store.evaluate_goal_batch_proposal("recover-goal")
        self.store._db.execute("UPDATE goals SET goal_json='{}' WHERE goal_id='goal-recover-goal'")
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_goals()
        recovered = self.store.recover()
        self.assertEqual(recovered["goals"], 1)
        goal = self.store.get_goal("goal-recover-goal")
        self.assertEqual(goal["status"], "candidate")
        self.assertEqual(goal["goal_version"], 1)


if __name__ == "__main__":
    unittest.main()


def goal_activation_event(
    proposal_id: str,
    goal_id: str,
    *,
    state_version: int,
    expected_goal_version: int = 1,
    rationale: str = "I choose to pursue this goal for now.",
    event_id: str | None = None,
):
    return event(
        event_id or f"goal-activation-proposal-event-{proposal_id}",
        GOAL_ACTIVATION_PROPOSAL_EVENT,
        "life-goal-activation-proposal:test.deliberator",
        {
            "proposal_id": proposal_id,
            "based_on": {"state_version": state_version},
            "goal_id": goal_id,
            "expected_goal_version": expected_goal_version,
            "rationale": rationale,
            "origin": {"component": "test.deliberator", "version": "0.1"},
            "contract_version": "life.goal_activation_proposed.v1",
        },
    )


class CSDGoalActivationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "activation.sqlite3"
        self.store = CognitiveMemoryStore(self.path)

    def tearDown(self):
        try:
            self.store.close()
        except sqlite3.ProgrammingError:
            pass
        self.temp_dir.cleanup()

    def create_candidate(self, suffix="activation"):
        signal_id = add_internal_signal(self.store, suffix)
        version = self.store.get_state_snapshot()["state_version"]
        proposal_id = f"candidate-{suffix}"
        self.store.submit_event(goal_event(proposal_id, [signal_id], state_version=version))
        result = self.store.evaluate_goal_batch_proposal(proposal_id)
        self.assertEqual(result["status"], "accepted")
        return f"goal-{proposal_id}", signal_id

    def test_explicit_activation_creates_version_two_and_increments_state_once(self):
        goal_id, signal_id = self.create_candidate()
        before = self.store.get_state_snapshot()["state_version"]
        candidate = self.store.get_goal(goal_id)
        self.assertEqual(candidate["status"], "candidate")
        self.assertEqual(candidate["goal_version"], 1)

        proposal = goal_activation_event(
            "activate-once", goal_id, state_version=before
        )
        self.store.submit_event(proposal)
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before)

        result = self.store.evaluate_goal_activation_proposal("activate-once")
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], before + 1)

        active = self.store.get_goal(goal_id)
        self.assertEqual(active["status"], "active")
        self.assertEqual(active["goal_version"], 2)
        self.assertEqual(active["origin_class"], candidate["origin_class"])
        self.assertEqual(active["origin_signal_refs"], candidate["origin_signal_refs"])
        self.assertEqual(active["origin_signal_refs"], [{"signal_id": signal_id, "signal_version": 1}])
        self.assertEqual(active["proposal_id"], candidate["proposal_id"])
        self.assertEqual(active["proposal_event_id"], candidate["proposal_event_id"])
        self.assertEqual(active["created_at"], candidate["created_at"])
        self.assertEqual(active["activation_proposal_id"], "activate-once")
        self.assertNotIn("activity_id", active)
        self.assertNotIn("capability", active)


    def test_activation_preserves_origin_lineage_after_source_signal_is_paused(self):
        goal_id, signal_id = self.create_candidate("paused-source")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(event(
            "pause-source-signal-proposal-event",
            MOTIVATION_PROPOSAL_EVENT,
            "motivation-proposal:test",
            {
                "proposal_id": "pause-source-signal",
                "operation": "pause",
                "kind": "interest",
                "subject_ref": "topic:paused-source",
                "scope": "general",
                "statement": None,
                "supporting_event_ids": [],
                "counter_evidence_event_ids": [],
                "new_signal_id": None,
                "target_signal_id": signal_id,
                "target_signal_version": 1,
                "requested_interest_stage": None,
                "rationale": "The source interest is paused independently of the goal.",
                "origin": {"component": "test", "version": "0.1"},
                "based_on": {"state_version": version},
            },
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("pause-source-signal")["status"],
            "accepted",
        )
        self.assertEqual(self.store.get_motivation_signal(signal_id)["status"], "paused")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event(
            "activate-after-source-pause", goal_id, state_version=version
        ))
        self.assertEqual(
            self.store.evaluate_goal_activation_proposal("activate-after-source-pause")["status"],
            "accepted",
        )
        active = self.store.get_goal(goal_id)
        self.assertEqual(active["status"], "active")
        self.assertEqual(
            active["origin_signal_refs"],
            [{"signal_id": signal_id, "signal_version": 1}],
        )

    def test_stale_shared_state_version_is_deferred_without_rebasing(self):
        goal_id, signal_id = self.create_candidate("stale-state")
        old_version = self.store.get_state_snapshot()["state_version"]
        add_internal_signal(self.store, "stale-state-later")
        current = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event(
            "stale-state-activation", goal_id, state_version=old_version
        ))
        result = self.store.evaluate_goal_activation_proposal("stale-state-activation")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], current)
        self.assertEqual(self.store.get_goal(goal_id)["status"], "candidate")

    def test_stale_goal_version_is_deferred(self):
        goal_id, _ = self.create_candidate("stale-goal-version")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event(
            "stale-goal-version-activation", goal_id,
            state_version=version, expected_goal_version=7,
        ))
        result = self.store.evaluate_goal_activation_proposal("stale-goal-version-activation")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(self.store.get_goal(goal_id)["status"], "candidate")
        self.assertEqual(self.store.get_goal(goal_id)["goal_version"], 1)

    def test_unknown_goal_is_rejected(self):
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event(
            "unknown-goal-activation", "missing-goal", state_version=version
        ))
        result = self.store.evaluate_goal_activation_proposal("unknown-goal-activation")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.get_goals(), [])

    def test_already_active_goal_cannot_be_activated_twice(self):
        goal_id, _ = self.create_candidate("twice")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event(
            "first-activation", goal_id, state_version=version
        ))
        self.assertEqual(
            self.store.evaluate_goal_activation_proposal("first-activation")["status"],
            "accepted",
        )
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event(
            "second-activation", goal_id, state_version=version, expected_goal_version=2
        ))
        result = self.store.evaluate_goal_activation_proposal("second-activation")
        self.assertEqual(result["status"], "rejected")
        self.assertEqual(self.store.get_goal(goal_id)["goal_version"], 2)

    def test_two_proposals_for_same_candidate_cannot_both_activate(self):
        goal_id, _ = self.create_candidate("race")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event("race-a", goal_id, state_version=version))
        self.store.submit_event(goal_activation_event("race-b", goal_id, state_version=version))
        self.assertEqual(self.store.evaluate_goal_activation_proposal("race-a")["status"], "accepted")
        self.assertEqual(self.store.evaluate_goal_activation_proposal("race-b")["status"], "deferred")
        self.assertEqual(self.store.get_goal(goal_id)["goal_version"], 2)

    def test_activation_proposal_identity_conflict_rolls_back(self):
        goal_id, _ = self.create_candidate("identity")
        version = self.store.get_state_snapshot()["state_version"]
        first = goal_activation_event("same-activation-id", goal_id, state_version=version)
        self.store.submit_event(first)
        before = self.store.get_state_snapshot()["event_count"]
        conflicting = goal_activation_event(
            "same-activation-id", goal_id, state_version=version,
            rationale="Different immutable rationale.", event_id="different-activation-event",
        )
        with self.assertRaises(ValueError):
            self.store.submit_event(conflicting)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)

    def test_recovery_rebuilds_active_goal_from_authoritative_events(self):
        goal_id, _ = self.create_candidate("recovery-active")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event(
            "recovery-activation", goal_id, state_version=version
        ))
        self.store.evaluate_goal_activation_proposal("recovery-activation")
        self.store._db.execute("UPDATE goals SET goal_json='{}' WHERE goal_id=?", (goal_id,))
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_goal(goal_id)
        recovered = self.store.recover()
        self.assertEqual(recovered["goals"], 1)
        self.assertEqual(self.store.get_goal(goal_id)["status"], "active")
        self.assertEqual(self.store.get_goal(goal_id)["goal_version"], 2)


    def test_life_engine_activation_sink_commits_only_the_goal_transition(self):
        goal_id, _ = self.create_candidate("life-sink")
        snapshot = CognitiveStoreLifeSnapshotReader(self.store).get_life_snapshot()
        goal = next(item for item in snapshot.goals if item.goal_id == goal_id)
        proposal = DeliberationProposal(
            based_on_state_version=snapshot.state_version,
            goal_proposals=(),
            choice=ChoiceProposal(
                disposition="activate_goal",
                rationale="I choose to pursue this candidate for now.",
                goal_id=goal_id,
                expected_goal_version=goal.goal_version,
            ),
        )
        validated = validate_life_proposal(snapshot, proposal)
        result = CognitiveStoreLifeProposalSink(self.store).submit_life_proposal(
            validated, expected_state_version=snapshot.state_version
        )
        self.assertEqual(result["status"], "accepted")
        active = self.store.get_goal(goal_id)
        self.assertEqual(active["status"], "active")
        self.assertEqual(active["goal_version"], 2)
        self.assertNotIn("activity_id", active)

    def test_activation_projection_tampering_is_detected_and_recovered(self):
        goal_id, _ = self.create_candidate("activation-projection")
        version = self.store.get_state_snapshot()["state_version"]
        self.store.submit_event(goal_activation_event(
            "projection-activation", goal_id, state_version=version
        ))
        self.store.evaluate_goal_activation_proposal("projection-activation")
        self.store._db.execute(
            "UPDATE goal_activation_proposals SET status='pending' WHERE proposal_id='projection-activation'"
        )
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_goals()
        self.store.recover()
        self.assertEqual(
            self.store.get_goal_proposal("candidate-activation-projection")["status"], "accepted"
        )
        self.assertEqual(self.store.get_goal(goal_id)["status"], "active")

    def test_v3_database_migrates_to_v4_activation_projection(self):
        self.store.close()
        db = sqlite3.connect(self.path)
        db.execute("DROP TABLE goal_activation_proposals")
        db.execute("PRAGMA user_version = 3")
        db.commit()
        db.close()
        self.store = CognitiveMemoryStore(self.path)
        version = int(self.store._db.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(version, 4)
        self.assertIsNotNone(self.store._db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='goal_activation_proposals'"
        ).fetchone())


