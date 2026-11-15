from __future__ import annotations

import unittest

from core.life_engine import (
    ActiveActivityState,
    ActivityOption,
    ChoiceProposal,
    DeliberationProposal,
    GoalProposal,
    GoalState,
    LifeEngine,
    LifeSnapshot,
    MotivationSignal,
    validate_life_proposal,
)


def signal(
    signal_id="sig-interest",
    origin_class="internally_initiated",
    *,
    active=True,
    kind="interest",
    subject_ref="topic:blue-boat",
    supporting_event_ids=("evt-source-1",),
    counter_evidence_event_ids=(),
    interest_stage=None,
    voluntary_encounters=(),
):
    return MotivationSignal(
        signal_id=signal_id,
        kind=kind,
        origin_class=origin_class,
        subject_ref=subject_ref,
        description="A synthetic motivation signal.",
        supporting_event_ids=supporting_event_ids,
        counter_evidence_event_ids=counter_evidence_event_ids,
        active=active,
        scope="synthetic topic scope",
        interest_stage=interest_stage,
        voluntary_encounters=voluntary_encounters,
    )


def option(activity_id="activity-read", *, permission=True, prerequisites=True,
           side_effect="read_only", serves_goal_ids=("goal-1",), source_ids=("sig-interest",)):
    return ActivityOption(
        activity_id=activity_id,
        activity_kind="inspect_topic",
        description="Inspect one bounded synthetic topic.",
        source_signal_ids=source_ids,
        serves_goal_ids=serves_goal_ids,
        required_capability="bilibili.read",
        permission_granted=permission,
        prerequisites_satisfied=prerequisites,
        side_effect_level=side_effect,
    )


def snapshot(*, signals=None, goals=None, options=None, active=("activity-running",),
             active_permission=True, active_stop=False, active_side_effect="read_only",
             include_active_details=True, version=4):
    active_ids = tuple(active)
    active_states = tuple(
        ActiveActivityState(
            activity_id,
            "bilibili.read",
            active_permission,
            active_stop,
            active_side_effect,
        )
        for activity_id in active_ids
    ) if include_active_details else ()
    return LifeSnapshot(
        state_version=version,
        signals=tuple(signals if signals is not None else (signal(),)),
        goals=tuple(goals if goals is not None else (
            GoalState("goal-1", "Understand one topic", "active", ("evt-goal-1",)),
        )),
        activity_options=tuple(options if options is not None else (option(),)),
        active_activity_ids=active_ids,
        active_activity_states=active_states,
    )


def choice(disposition="no_op", **kwargs):
    defaults = {
        "rationale": "A synthetic, concise decision reason.",
        "considered_activity_ids": (),
        "activity_id": None,
        "goal_id": None,
        "active_activity_id": None,
        "evidence_event_ids": ("evt-source-1",),
    }
    defaults.update(kwargs)
    return ChoiceProposal(disposition=disposition, **defaults)


def proposal(snap, selected=None, *, goals=(), disposition=None):
    return DeliberationProposal(
        based_on_state_version=snap.state_version,
        goal_proposals=tuple(goals),
        choice=selected or choice(disposition or "no_op"),
    )


class FakeReader:
    def __init__(self, value):
        self.value = value

    def get_life_snapshot(self):
        return self.value


class FakeDeliberator:
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error
        self.calls = 0

    def deliberate(self, snapshot_value):
        self.calls += 1
        if self.error:
            raise self.error
        return self.value


class FakeSink:
    def __init__(self):
        self.calls = []

    def submit_life_proposal(self, value, *, expected_state_version):
        self.calls.append((value, expected_state_version))
        return {"status": "pending", "expected_state_version": expected_state_version}


class LifeProposalValidationTests(unittest.TestCase):
    def test_noop_is_valid_even_when_activity_options_exist(self):
        snap = snapshot()
        validated = validate_life_proposal(snap, proposal(snap))
        self.assertEqual(validated.proposal.choice.disposition, "no_op")
        self.assertFalse(validated.requires_asm_governance)

    def test_empty_snapshot_can_legitimately_choose_noop(self):
        snap = snapshot(signals=(), goals=(), options=(), active=())
        validated = validate_life_proposal(snap, proposal(snap, choice("no_op", evidence_event_ids=())))
        self.assertEqual(validated.goal_origin_classes, ())

    def test_read_only_activity_is_selectable_without_asm_side_effect_governance(self):
        snap = snapshot()
        selected = choice(
            "start_activity",
            considered_activity_ids=("activity-read",),
            activity_id="activity-read",
            goal_id="goal-1",
        )
        result = validate_life_proposal(snap, proposal(snap, selected))
        self.assertFalse(result.requires_asm_governance)

    def test_side_effecting_activity_is_only_marked_for_asm_governance(self):
        snap = snapshot(options=(option(side_effect="external_side_effect"),))
        selected = choice(
            "start_activity",
            considered_activity_ids=("activity-read",),
            activity_id="activity-read",
            goal_id="goal-1",
        )
        result = validate_life_proposal(snap, proposal(snap, selected))
        self.assertTrue(result.requires_asm_governance)
        self.assertFalse(hasattr(result, "executor"))

    def test_missing_permission_blocks_activity(self):
        snap = snapshot(options=(option(permission=False),))
        selected = choice(
            "start_activity",
            considered_activity_ids=("activity-read",),
            activity_id="activity-read",
            goal_id="goal-1",
        )
        with self.assertRaises(PermissionError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_unsatisfied_prerequisite_blocks_activity(self):
        snap = snapshot(options=(option(prerequisites=False),))
        selected = choice(
            "start_activity",
            considered_activity_ids=("activity-read",),
            activity_id="activity-read",
            goal_id="goal-1",
        )
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_unknown_activity_cannot_be_invented_by_deliberator(self):
        snap = snapshot()
        selected = choice("start_activity", activity_id="model-invented")
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_selected_activity_must_be_in_considered_set(self):
        snap = snapshot()
        selected = choice("start_activity", activity_id="activity-read", goal_id="goal-1")
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_stale_state_version_is_rejected(self):
        snap = snapshot(version=4)
        stale = DeliberationProposal(3, (), choice())
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, stale)

    def test_unknown_considered_activity_is_rejected(self):
        snap = snapshot()
        selected = choice("wait", considered_activity_ids=("not-in-snapshot",))
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_choice_evidence_must_exist_in_snapshot(self):
        snap = snapshot()
        selected = choice("wait", evidence_event_ids=("evt-fabricated",))
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_internal_goal_origin_is_derived_from_snapshot_not_model_label(self):
        snap = snapshot()
        candidate = GoalProposal(
            "goal-new", "Understand the topic", ("sig-interest",),
            "The interest has persisted across voluntary encounters.",
            "A coherent explanation can be produced.",
            "Stop when evidence is exhausted or interest fades.",
            "Review after the next meaningful encounter.",
        )
        result = validate_life_proposal(snap, proposal(snap, goals=(candidate,)))
        self.assertEqual(result.goal_origin_classes, (("goal-new", "internally_initiated"),))

    def test_user_requested_goal_origin_remains_user_requested(self):
        user_signal = signal("sig-user", "user_requested_encounter", kind="opportunity")
        user_option = option(source_ids=("sig-user",))
        snap = snapshot(signals=(user_signal,), options=(user_option,))
        candidate = GoalProposal(
            "goal-user", "Complete the requested comparison", ("sig-user",),
            "The user requested this comparison.",
            "The comparison is delivered.",
            "Stop if the request is withdrawn.",
            "Review when the requested scope is complete.",
        )
        result = validate_life_proposal(snap, proposal(snap, goals=(candidate,)))
        self.assertEqual(result.goal_origin_classes, (("goal-user", "user_requested"),))

    def test_external_opportunity_is_not_misclassified_as_internal(self):
        external = signal("sig-opportunity", "externally_exposed", kind="opportunity")
        external_option = option(source_ids=("sig-opportunity",))
        snap = snapshot(signals=(external,), options=(external_option,))
        candidate = GoalProposal(
            "goal-external", "Inspect the newly available item", ("sig-opportunity",),
            "A new item became available.",
            "The item is understood or intentionally skipped.",
            "Stop when the item is no longer available.",
            "Review after one bounded inspection.",
        )
        result = validate_life_proposal(snap, proposal(snap, goals=(candidate,)))
        self.assertEqual(result.goal_origin_classes, (("goal-external", "externally_triggered"),))

    def test_user_origin_is_not_rewritten_when_interest_later_emerges(self):
        evolved_user_interest = signal(
            "sig-user-evolved",
            "user_requested_encounter",
            kind="interest",
            interest_stage="emerging",
            supporting_event_ids=("evt-source-1", "evt-source-2"),
            voluntary_encounters=(
                ("enc-1", "2026-11-14T10:00:00+00:00", "evt-source-1"),
                ("enc-2", "2026-11-15T10:00:00+00:00", "evt-source-2"),
            ),
        )
        snap = snapshot(
            signals=(evolved_user_interest,),
            options=(option(source_ids=("sig-user-evolved",)),),
        )
        candidate = GoalProposal(
            "goal-evolved-user-interest", "Explore the topic independently",
            ("sig-user-evolved",),
            "The topic has developed repeated voluntary interest.",
            "The bounded question is answered.",
            "Stop if the interest fades.",
            "Review after the next encounter.",
        )
        result = validate_life_proposal(snap, proposal(snap, goals=(candidate,)))
        self.assertEqual(
            result.goal_origin_classes,
            (("goal-evolved-user-interest", "mixed_origin"),),
        )

    def test_interest_encounter_summary_requires_timezone_aware_timestamps(self):
        invalid = signal(
            interest_stage="emerging",
            evidence_event_ids=("evt-1", "evt-2"),
            voluntary_encounters=(
                ("enc-1", "2026-11-14T10:00:00", "evt-1"),
                ("enc-2", "2026-11-15T10:00:00+00:00", "evt-2"),
            ),
        )
        with self.assertRaises(ValueError):
            validate_life_proposal(
                snapshot(signals=(invalid,), options=()),
                proposal(snapshot(signals=(invalid,), options=())),
            )

    def test_interest_encounter_summary_must_reference_supporting_evidence(self):
        invalid = signal(
            interest_stage="emerging",
            voluntary_encounters=(
                ("enc-1", "2026-11-14T10:00:00+00:00", "evt-source-1"),
                ("enc-2", "2026-11-15T10:00:00+00:00", "not-in-support"),
            ),
        )
        with self.assertRaises(ValueError):
            validate_life_proposal(
                snapshot(signals=(invalid,), options=()),
                proposal(snapshot(signals=(invalid,), options=())),
            )

    def test_mixed_internal_and_user_origins_are_not_claimed_as_purely_internal(self):
        snap = snapshot(signals=(signal(), signal("sig-user", "user_requested_encounter", kind="opportunity")))
        candidate = GoalProposal(
            "goal-mixed", "Explore the topic", ("sig-interest", "sig-user"),
            "An internal interest and a user request both contributed.",
            "The bounded question is answered.",
            "Stop if either source of motivation is withdrawn.",
            "Review after the initial exploration.",
        )
        result = validate_life_proposal(snap, proposal(snap, goals=(candidate,)))
        self.assertEqual(result.goal_origin_classes, (("goal-mixed", "mixed_origin"),))

    def test_goal_cannot_originate_from_inactive_signal(self):
        inactive = signal(active=False)
        snap = snapshot(signals=(inactive,), options=())
        candidate = GoalProposal(
            "goal-inactive", "Explore", ("sig-interest",), "Reason.",
            "Done.", "Stop.", "Review.",
        )
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, goals=(candidate,)))

    def test_duplicate_goal_identity_is_rejected(self):
        snap = snapshot()
        candidate = GoalProposal(
            "goal-1", "Duplicate", ("sig-interest",), "Reason.",
            "Done.", "Stop.", "Review.",
        )
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, goals=(candidate,)))

    def test_pause_requires_existing_active_goal(self):
        snap = snapshot(goals=(GoalState("goal-1", "Understand", "active"),))
        selected = choice("pause_goal", goal_id="goal-1")
        self.assertEqual(validate_life_proposal(snap, proposal(snap, selected)).proposal.choice.disposition,
                         "pause_goal")

    def test_pause_cannot_target_non_active_goal(self):
        snap = snapshot(goals=(GoalState("goal-1", "Understand", "paused"),))
        selected = choice("pause_goal", goal_id="goal-1")
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_activity_cannot_target_a_paused_goal(self):
        snap = snapshot(goals=(GoalState("goal-1", "Understand", "paused"),))
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap))

    def test_stop_requires_known_active_activity(self):
        snap = snapshot(active=("activity-running",))
        selected = choice("stop_activity", active_activity_id="activity-running")
        self.assertEqual(validate_life_proposal(snap, proposal(snap, selected)).proposal.choice.disposition,
                         "stop_activity")

    def test_stop_cannot_target_unknown_activity(self):
        snap = snapshot()
        selected = choice("stop_activity", active_activity_id="not-running")
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_continue_activity_uses_current_activity_identity(self):
        snap = snapshot()
        selected = choice("continue_activity", active_activity_id="activity-running")
        self.assertEqual(validate_life_proposal(snap, proposal(snap, selected)).proposal.choice.disposition,
                         "continue_activity")

    def test_continue_activity_is_blocked_after_permission_revocation(self):
        snap = snapshot(active_permission=False)
        selected = choice("continue_activity", active_activity_id="activity-running")
        with self.assertRaises(PermissionError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_continue_activity_requires_trusted_active_state_details(self):
        snap = snapshot(include_active_details=False)
        selected = choice("continue_activity", active_activity_id="activity-running")
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_continue_activity_is_blocked_when_stop_condition_is_met(self):
        snap = snapshot(active_stop=True)
        selected = choice("continue_activity", active_activity_id="activity-running")
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_continue_side_effecting_activity_requires_asm(self):
        snap = snapshot(active_side_effect="external_side_effect")
        selected = choice("continue_activity", active_activity_id="activity-running")
        self.assertTrue(validate_life_proposal(snap, proposal(snap, selected)).requires_asm_governance)

    def test_stopping_side_effecting_activity_requires_asm(self):
        snap = snapshot(active_side_effect="external_side_effect")
        selected = choice("stop_activity", active_activity_id="activity-running")
        self.assertTrue(validate_life_proposal(snap, proposal(snap, selected)).requires_asm_governance)

    def test_noop_cannot_smuggle_an_activity_selection(self):
        snap = snapshot()
        selected = choice("no_op", activity_id="activity-read")
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap, selected))

    def test_activity_option_must_cite_an_active_motivation_signal(self):
        inactive = signal(active=False)
        snap = snapshot(signals=(inactive,), options=(option(),))
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap))

    def test_activity_can_be_grounded_in_an_active_goal_without_current_signal(self):
        snap = snapshot(
            signals=(),
            options=(option(source_ids=(), serves_goal_ids=("goal-1",)),),
            active=(),
        )
        selected = choice(
            "start_activity",
            considered_activity_ids=("activity-read",),
            activity_id="activity-read",
            goal_id="goal-1",
            evidence_event_ids=("evt-goal-1",),
        )
        self.assertFalse(validate_life_proposal(snap, proposal(snap, selected)).requires_asm_governance)

    def test_activity_without_signal_or_goal_origin_is_rejected(self):
        snap = snapshot(
            options=(option(source_ids=(), serves_goal_ids=()),),
        )
        with self.assertRaises(ValueError):
            validate_life_proposal(snap, proposal(snap))

    def test_self_accepted_commitment_is_classified_as_internal_origin(self):
        commitment = MotivationSignal(
            signal_id="sig-commitment",
            kind="commitment",
            origin_class="internally_initiated",
            subject_ref="commitment:self-accepted",
            description="A self-accepted commitment.",
            supporting_event_ids=("evt-commitment",),
        )
        snap = snapshot(signals=(commitment,), options=())
        candidate = GoalProposal(
            "goal-from-commitment",
            "Fulfil the commitment",
            ("sig-commitment",),
            "The individual previously accepted this commitment.",
            "The commitment is fulfilled.",
            "Stop if the commitment is withdrawn or no longer valid.",
            "Review when the due condition changes.",
        )
        selected = choice("no_op", evidence_event_ids=("evt-commitment",))
        result = validate_life_proposal(
            snap, proposal(snap, selected, goals=(candidate,))
        )
        self.assertEqual(
            result.goal_origin_classes,
            (("goal-from-commitment", "internally_initiated"),),
        )


class LifeEngineOrchestrationTests(unittest.TestCase):
    def test_engine_submits_validated_proposal_to_sink(self):
        snap = snapshot()
        proposal_value = proposal(snap)
        reader = FakeReader(snap)
        deliberator = FakeDeliberator(proposal_value)
        sink = FakeSink()
        result = LifeEngine(reader, deliberator, sink).consider()
        self.assertEqual(result["status"], "pending")
        self.assertEqual(deliberator.calls, 1)
        self.assertEqual(len(sink.calls), 1)
        self.assertEqual(sink.calls[0][1], snap.state_version)

    def test_noop_is_submitted_as_a_real_choice(self):
        snap = snapshot(signals=(), goals=(), options=(), active=())
        reader = FakeReader(snap)
        deliberator = FakeDeliberator(proposal(snap, choice("no_op", evidence_event_ids=())))
        sink = FakeSink()
        LifeEngine(reader, deliberator, sink).consider()
        self.assertEqual(sink.calls[0][0].proposal.choice.disposition, "no_op")

    def test_deliberator_failure_does_not_submit_anything(self):
        snap = snapshot()
        sink = FakeSink()
        engine = LifeEngine(FakeReader(snap), FakeDeliberator(error=TimeoutError("synthetic")), sink)
        with self.assertRaises(TimeoutError):
            engine.consider()
        self.assertEqual(sink.calls, [])

    def test_life_engine_exposes_no_action_executor(self):
        snap = snapshot()
        engine = LifeEngine(FakeReader(snap), FakeDeliberator(proposal(snap)), FakeSink())
        self.assertFalse(hasattr(engine, "execute"))
        self.assertFalse(hasattr(engine, "action_executor"))


if __name__ == "__main__":
    unittest.main()
