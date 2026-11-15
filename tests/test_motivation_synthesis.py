from __future__ import annotations

import unittest

from core.life_engine.motivation import (
    MotivationEvidence,
    MotivationSignalState,
    MotivationSnapshot,
    MotivationUpdateProposal,
    validate_motivation_update,
)


def evidence(
    event_id,
    kind,
    *,
    origin="internal_state",
    encounter="enc-1",
    subject="topic:blue-boat",
    at="2026-11-14T10:00:00+00:00",
    alternatives=False,
):
    return MotivationEvidence(
        event_id=event_id,
        encounter_id=encounter,
        subject_ref=subject,
        evidence_kind=kind,
        origin=origin,
        occurred_at=at,
        context="synthetic test context",
        meaningful_alternatives=alternatives,
    )


def signal(
    *,
    signal_id="interest-1",
    version=1,
    kind="interest",
    subject="topic:blue-boat",
    status="active",
    origin="internally_initiated",
    supporting=("old-support",),
    counter=(),
    statement="A tentative interest in the blue-boat topic.",
    voluntary_encounters=(),
):
    return MotivationSignalState(
        signal_id=signal_id,
        version=version,
        kind=kind,
        subject_ref=subject,
        scope="test scope",
        status=status,
        origin_class=origin,
        supporting_event_ids=supporting,
        counter_evidence_event_ids=counter,
        statement=statement,
        voluntary_encounters=voluntary_encounters,
    )


def snapshot(*, evidence_items=(), signals=(), version=7):
    return MotivationSnapshot(
        state_version=version,
        evidence=tuple(evidence_items),
        signals=tuple(signals),
    )


def create_proposal(
    *,
    kind="interest",
    operation="create",
    supporting=("ev-1",),
    counter=(),
    stage="tentative",
    signal_id="new-interest-1",
    target=None,
    target_version=None,
    version=7,
    subject="topic:blue-boat",
    statement=None,
):
    effective_statement = (
        statement if statement is not None
        else ("The topic may be interesting to explore." if operation == "create" else None)
    )
    return MotivationUpdateProposal(
        proposal_id="proposal-1",
        based_on_state_version=version,
        operation=operation,
        kind=kind,
        subject_ref=subject,
        scope="test scope",
        rationale="Synthetic test rationale.",
        supporting_event_ids=tuple(supporting),
        counter_evidence_event_ids=tuple(counter),
        new_signal_id=signal_id if operation == "create" else None,
        target_signal_id=target,
        target_signal_version=target_version,
        requested_interest_stage=(stage if kind == "interest" and operation in {"create", "reinforce"} else None),
        statement=effective_statement,
    )


class MotivationEvidenceOriginTests(unittest.TestCase):
    def test_passive_recommendation_is_exposure_not_internal_interest(self):
        item = evidence("ev-1", "passive_exposure", origin="platform_recommendation")
        result = validate_motivation_update(snapshot(evidence_items=(item,)),
                                            create_proposal())
        self.assertEqual(result.derived_origin_class, "externally_exposed")
        self.assertEqual(result.voluntary_encounter_ids, ())

    def test_user_requested_watch_remains_user_requested(self):
        item = evidence("ev-1", "user_requested_action", origin="user_request")
        result = validate_motivation_update(snapshot(evidence_items=(item,)),
                                            create_proposal())
        self.assertEqual(result.derived_origin_class, "user_requested_encounter")
        self.assertEqual(result.voluntary_encounter_ids, ())

    def test_platform_autoplay_is_not_voluntary_choice(self):
        item = evidence("ev-1", "platform_autoplay", origin="platform_recommendation")
        result = validate_motivation_update(snapshot(evidence_items=(item,)),
                                            create_proposal())
        self.assertEqual(result.voluntary_encounter_ids, ())
        self.assertFalse(result.emerging_interest_supported)

    def test_one_voluntary_choice_is_not_emerging_interest(self):
        item = evidence("ev-1", "voluntary_selection", alternatives=True)
        result = validate_motivation_update(
            snapshot(evidence_items=(item,)),
            create_proposal(stage="tentative"),
        )
        self.assertEqual(result.voluntary_encounter_ids, ("enc-1",))
        self.assertFalse(result.emerging_interest_supported)

    def test_voluntary_choice_without_meaningful_alternatives_is_not_independent(self):
        item = evidence("ev-1", "voluntary_selection", alternatives=False)
        result = validate_motivation_update(
            snapshot(evidence_items=(item,)),
            create_proposal(stage="tentative"),
        )
        self.assertEqual(result.voluntary_encounter_ids, ())

    def test_emerging_interest_needs_distinct_time_separated_encounters(self):
        items = (
            evidence("ev-1", "voluntary_selection", encounter="enc-1",
                     at="2026-11-14T10:00:00+00:00", alternatives=True),
            evidence("ev-2", "return_visit", encounter="enc-2",
                     at="2026-11-14T11:00:00+00:00", alternatives=True),
        )
        result = validate_motivation_update(
            snapshot(evidence_items=items),
            create_proposal(supporting=("ev-1", "ev-2"), stage="emerging"),
        )
        self.assertTrue(result.emerging_interest_supported)
        self.assertEqual(result.voluntary_encounter_ids, ("enc-1", "enc-2"))

    def test_emerging_interest_rejects_two_events_from_same_encounter(self):
        items = (
            evidence("ev-1", "voluntary_selection", encounter="enc-1",
                     at="2026-11-14T10:00:00+00:00", alternatives=True),
            evidence("ev-2", "return_visit", encounter="enc-1",
                     at="2026-11-14T11:00:00+00:00", alternatives=True),
        )
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=items),
                create_proposal(supporting=("ev-1", "ev-2"), stage="emerging"),
            )

    def test_emerging_interest_rejects_distinct_encounters_with_same_timestamp(self):
        items = (
            evidence("ev-1", "voluntary_selection", encounter="enc-1",
                     at="2026-11-14T10:00:00+00:00", alternatives=True),
            evidence("ev-2", "return_visit", encounter="enc-2",
                     at="2026-11-14T10:00:00+00:00", alternatives=True),
        )
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=items),
                create_proposal(supporting=("ev-1", "ev-2"), stage="emerging"),
            )

    def test_emerging_interest_can_accumulate_across_signal_versions(self):
        prior = signal(
            origin="user_requested_encounter",
            supporting=("ev-old",),
            voluntary_encounters=(("enc-old", "2026-11-13T10:00:00+00:00", "ev-old"),),
        )
        new = evidence(
            "ev-new", "voluntary_selection", encounter="enc-new",
            at="2026-11-14T10:00:00+00:00", alternatives=True,
        )
        result = validate_motivation_update(
            snapshot(evidence_items=(new,), signals=(prior,)),
            create_proposal(
                operation="reinforce", target="interest-1",
                target_version=1, supporting=("ev-new",),
            ),
        )
        self.assertTrue(result.emerging_interest_supported)
        self.assertEqual(result.voluntary_encounter_ids, ("enc-new", "enc-old"))
        self.assertEqual(result.derived_origin_class, "user_requested_encounter")

    def test_stored_voluntary_encounter_must_reference_supporting_event(self):
        invalid = signal(
            supporting=("ev-old",),
            voluntary_encounters=(("enc-old", "2026-11-13T10:00:00+00:00", "unknown-event"),),
        )
        new = evidence("ev-new", "voluntary_selection", alternatives=True)
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(new,), signals=(invalid,)),
                create_proposal(
                    operation="reinforce", target="interest-1",
                    target_version=1, supporting=("ev-new",),
                ),
            )

    def test_duplicate_stored_voluntary_encounter_ids_are_rejected(self):
        invalid = signal(
            voluntary_encounters=(
                ("enc-old", "2026-11-13T10:00:00+00:00", "old-support"),
                ("enc-old", "2026-11-13T11:00:00+00:00", "old-support"),
            ),
        )
        new = evidence("ev-new", "voluntary_selection", alternatives=True)
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(new,), signals=(invalid,)),
                create_proposal(
                    operation="reinforce", target="interest-1",
                    target_version=1, supporting=("ev-new",),
                ),
            )

    def test_one_evidence_event_cannot_represent_two_encounters(self):
        invalid = signal(
            voluntary_encounters=(
                ("enc-1", "2026-11-13T10:00:00+00:00", "old-support"),
                ("enc-2", "2026-11-13T11:00:00+00:00", "old-support"),
            ),
        )
        new = evidence("ev-new", "voluntary_selection", alternatives=True)
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(new,), signals=(invalid,)),
                create_proposal(
                    operation="reinforce", target="interest-1",
                    target_version=1, supporting=("ev-new",),
                ),
            )

    def test_non_interest_signal_cannot_carry_interest_encounter_summary(self):
        invalid = signal(
            kind="need",
            voluntary_encounters=(("enc-1", "2026-11-13T10:00:00+00:00", "old-support"),),
        )
        item = evidence("ev-new", "need_condition")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(invalid,)),
                create_proposal(
                    kind="need", operation="reinforce", target="interest-1",
                    target_version=1, supporting=("ev-new",),
                ),
            )

    def test_mixed_user_and_internal_evidence_is_not_purely_internal(self):
        items = (
            evidence("ev-1", "voluntary_selection", origin="internal_state",
                     encounter="enc-1", alternatives=True),
            evidence("ev-2", "user_requested_action", origin="user_request",
                     encounter="enc-2"),
        )
        result = validate_motivation_update(
            snapshot(evidence_items=items),
            create_proposal(supporting=("ev-1", "ev-2")),
        )
        self.assertEqual(result.derived_origin_class, "mixed_origin")

    def test_creation_origin_ignores_counterevidence_provenance(self):
        items = (
            evidence("ev-1", "passive_exposure", origin="platform_recommendation"),
            evidence("ev-2", "counter_evidence", origin="internal_state"),
        )
        result = validate_motivation_update(
            snapshot(evidence_items=items),
            create_proposal(supporting=("ev-1",), counter=("ev-2",)),
        )
        self.assertEqual(result.derived_origin_class, "externally_exposed")

    def test_internal_origin_is_not_changed_by_user_request_counterevidence(self):
        items = (
            evidence("ev-1", "voluntary_selection", origin="internal_state",
                     encounter="enc-1", alternatives=True),
            evidence("ev-2", "counter_evidence", origin="user_request",
                     encounter="enc-2"),
        )
        result = validate_motivation_update(
            snapshot(evidence_items=items),
            create_proposal(supporting=("ev-1",), counter=("ev-2",)),
        )
        self.assertEqual(result.derived_origin_class, "internally_initiated")

    def test_established_interest_cannot_be_assigned_by_provider(self):
        item = evidence("ev-1", "passive_exposure", origin="platform_recommendation")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(stage="established"),
            )

    def test_user_requested_event_cannot_be_mislabeled_as_internal(self):
        item = evidence("ev-1", "user_requested_action", origin="internal_state")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(),
            )

    def test_platform_autoplay_cannot_be_mislabeled_as_external_opportunity_or_internal(self):
        item = evidence("ev-1", "platform_autoplay", origin="external_opportunity")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(),
            )

    def test_voluntary_selection_cannot_be_user_requested(self):
        item = evidence(
            "ev-1", "voluntary_selection",
            origin="user_request", alternatives=True,
        )
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(),
            )

    def test_self_commitment_followthrough_is_not_interest_evidence(self):
        item = evidence(
            "ev-1", "return_visit",
            origin="self_commitment", alternatives=True,
        )
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(),
            )

    def test_autonomous_question_cannot_be_user_question(self):
        item = evidence("ev-1", "autonomous_question", origin="user_request")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(kind="curiosity"),
            )


class MotivationEvidenceIntegrityTests(unittest.TestCase):
    def test_unknown_evidence_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_motivation_update(snapshot(), create_proposal())

    def test_create_requires_a_signal_statement(self):
        from dataclasses import replace
        candidate = replace(create_proposal(), statement=None)
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(evidence("ev-1", "passive_exposure"),)),
                candidate,
            )

    def test_existing_signal_requires_a_statement(self):
        item = evidence("ev-1", "voluntary_selection", alternatives=True)
        invalid = signal(statement="")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(invalid,)),
                create_proposal(operation="reinforce", target="interest-1",
                                target_version=1, supporting=("ev-1",)),
            )

    def test_evidence_subject_must_match_proposal_subject(self):
        item = evidence("ev-1", "passive_exposure", subject="creator:other")
        with self.assertRaises(ValueError):
            validate_motivation_update(snapshot(evidence_items=(item,)),
                                       create_proposal())

    def test_stale_snapshot_version_is_rejected(self):
        item = evidence("ev-1", "passive_exposure")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), version=8),
                create_proposal(version=7),
            )

    def test_boolean_state_version_is_rejected(self):
        item = evidence("ev-1", "passive_exposure")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), version=1),
                create_proposal(version=True),
            )

    def test_duplicate_event_identity_in_snapshot_is_rejected(self):
        item = evidence("ev-1", "passive_exposure")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item, item)),
                create_proposal(),
            )

    def test_naive_timestamp_is_rejected(self):
        item = evidence("ev-1", "passive_exposure", at="2026-11-14T10:00:00")
        with self.assertRaises(ValueError):
            validate_motivation_update(snapshot(evidence_items=(item,)),
                                       create_proposal())

    def test_invalid_existing_signal_origin_is_rejected(self):
        item = evidence("ev-1", "passive_exposure")
        invalid = signal(origin="model_says_self_initiated")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(invalid,)),
                create_proposal(),
            )

    def test_support_and_counter_lists_must_be_disjoint(self):
        item = evidence("ev-1", "counter_evidence")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(supporting=("ev-1",), counter=("ev-1",)),
            )

    def test_counter_evidence_cannot_be_misfiled_as_support(self):
        item = evidence("ev-1", "counter_evidence")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(supporting=("ev-1",)),
            )

    def test_non_counter_record_cannot_be_used_as_counterevidence(self):
        item = evidence("ev-1", "passive_exposure")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(supporting=(), counter=("ev-1",)),
            )


class MotivationSignalOperationTests(unittest.TestCase):
    def test_need_creation_requires_need_condition(self):
        item = evidence("ev-1", "passive_exposure")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(kind="need"),
            )

    def test_valid_need_creation_requires_condition_evidence(self):
        item = evidence("ev-1", "need_condition")
        result = validate_motivation_update(
            snapshot(evidence_items=(item,)),
            create_proposal(kind="need"),
        )
        self.assertEqual(result.derived_origin_class, "internally_initiated")

    def test_curiosity_creation_requires_autonomous_question(self):
        item = evidence("ev-1", "question_encountered")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(kind="curiosity"),
            )

    def test_commitment_creation_requires_acceptance_evidence(self):
        item = evidence("ev-1", "user_requested_action", origin="user_request")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(kind="commitment"),
            )

    def test_affect_creation_requires_affect_observation(self):
        item = evidence("ev-1", "passive_exposure")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,)),
                create_proposal(kind="affect"),
            )

    def test_weaken_requires_new_counterevidence(self):
        item = evidence("ev-new", "counter_evidence")
        target = signal(supporting=("old-support",))
        result = validate_motivation_update(
            snapshot(evidence_items=(item,), signals=(target,)),
            create_proposal(operation="weaken", target="interest-1",
                            target_version=1, supporting=(), counter=("ev-new",)),
        )
        self.assertEqual(result.derived_origin_class, "internally_initiated")

    def test_weaken_cannot_smuggle_new_supporting_evidence(self):
        counter = evidence("ev-counter", "counter_evidence")
        support = evidence("ev-support", "passive_exposure")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(counter, support), signals=(signal(),)),
                create_proposal(operation="weaken", target="interest-1",
                                target_version=1, supporting=("ev-support",),
                                counter=("ev-counter",)),
            )

    def test_reinforce_requires_new_evidence(self):
        old = signal(supporting=("ev-old",))
        item = evidence("ev-new", "voluntary_selection", alternatives=True)
        result = validate_motivation_update(
            snapshot(evidence_items=(item,), signals=(old,)),
            create_proposal(operation="reinforce", target="interest-1",
                            target_version=1, supporting=("ev-new",)),
        )
        self.assertEqual(result.proposal.operation, "reinforce")
        self.assertEqual(result.effective_statement, old.statement)

    def test_reinforce_cannot_rewrite_signal_statement(self):
        old = signal(supporting=("ev-old",))
        item = evidence("ev-new", "voluntary_selection", alternatives=True)
        candidate = create_proposal(
            operation="reinforce", target="interest-1", target_version=1,
            supporting=("ev-new",), statement="A completely different interest.",
        )
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(old,)),
                candidate,
            )

    def test_contextualize_can_refine_statement_and_scope(self):
        old = signal(supporting=("ev-old",))
        item = evidence("ev-new", "voluntary_selection", alternatives=True)
        candidate = create_proposal(
            operation="contextualize", target="interest-1", target_version=1,
            supporting=("ev-new",), statement="Interest in this topic during quiet evenings.",
        )
        from dataclasses import replace
        candidate = replace(candidate, scope="quiet evenings")
        result = validate_motivation_update(
            snapshot(evidence_items=(item,), signals=(old,)),
            candidate,
        )
        self.assertEqual(result.effective_statement, "Interest in this topic during quiet evenings.")

    def test_contextualize_cannot_assign_maturity(self):
        from dataclasses import replace
        old = signal(supporting=("ev-old",))
        item = evidence("ev-new", "voluntary_selection", alternatives=True)
        candidate = create_proposal(
            operation="contextualize", target="interest-1", target_version=1,
            supporting=("ev-new",),
        )
        candidate = replace(candidate, requested_interest_stage="emerging")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(old,)),
                candidate,
            )

    def test_signal_revision_cannot_reuse_old_evidence(self):
        old = signal(supporting=("ev-old",))
        item = evidence("ev-old", "voluntary_selection", alternatives=True)
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(old,)),
                create_proposal(operation="reinforce", target="interest-1",
                                target_version=1, supporting=("ev-old",)),
            )

    def test_stale_target_signal_version_is_rejected(self):
        old = signal(version=3)
        item = evidence("ev-new", "voluntary_selection", alternatives=True)
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(old,)),
                create_proposal(operation="reinforce", target="interest-1",
                                target_version=2, supporting=("ev-new",)),
            )

    def test_non_contextual_update_cannot_change_signal_scope(self):
        old = signal()
        item = evidence("ev-new", "voluntary_selection", alternatives=True)
        changed_scope = create_proposal(
            operation="reinforce", target="interest-1", target_version=1,
            supporting=("ev-new",),
        )
        changed_scope = MotivationUpdateProposal(
            **{**changed_scope.__dict__, "scope": "different scope"}
        )
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(old,)),
                changed_scope,
            )

    def test_paused_signal_cannot_be_updated(self):
        old = signal(status="paused")
        item = evidence("ev-new", "voluntary_selection", alternatives=True)
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(old,)),
                create_proposal(operation="reinforce", target="interest-1",
                                target_version=1, supporting=("ev-new",)),
            )

    def test_pause_can_be_an_intentional_choice_without_new_evidence(self):
        old = signal()
        result = validate_motivation_update(
            snapshot(signals=(old,)),
            create_proposal(operation="pause", target="interest-1",
                            target_version=1, supporting=()),
        )
        self.assertEqual(result.derived_origin_class, "internally_initiated")

    def test_resolve_requires_resolution_evidence(self):
        item = evidence("ev-new", "passive_exposure")
        with self.assertRaises(ValueError):
            validate_motivation_update(
                snapshot(evidence_items=(item,), signals=(signal(),)),
                create_proposal(operation="resolve", target="interest-1",
                                target_version=1, supporting=("ev-new",)),
            )

    def test_resolve_accepts_explicit_resolution_evidence(self):
        item = evidence("ev-new", "resolution")
        result = validate_motivation_update(
            snapshot(evidence_items=(item,), signals=(signal(),)),
            create_proposal(operation="resolve", target="interest-1",
                            target_version=1, supporting=("ev-new",)),
        )
        self.assertEqual(result.proposal.operation, "resolve")


if __name__ == "__main__":
    unittest.main()
