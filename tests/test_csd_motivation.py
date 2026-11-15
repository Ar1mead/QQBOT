from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from core.csd import (
    CognitiveEvent,
    CognitiveIdempotencyConflict,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
    INTERACTION_EVENT,
    MOTIVATION_DECISION_EVENT,
    MOTIVATION_PROPOSAL_EVENT,
)
from core.csd.cognitive import (
    DECISION_EVENT,
    OBSERVATION_EVENT,
    PROPOSAL_EVENT,
)


def envelope(event_id, event_type, source, payload, *, at="2026-11-14T10:00:00+00:00"):
    return CognitiveEvent(
        event_id=event_id,
        occurred_at=at,
        correlation_id="corr-motivation-tests",
        event_type=event_type,
        source=source,
        payload=payload,
    )


def interaction(
    event_id,
    *,
    kind="voluntary_selection",
    origin="internal_state",
    encounter="enc-1",
    subject="topic:blue-boat",
    selected="item:blue-boat",
    choice_set=None,
    meaningful=True,
    origin_event_id=None,
    related_event_id=None,
    at="2026-11-14T10:00:00+00:00",
    adapter="test.adapter",
):
    if choice_set is None:
        choice_set = ["item:blue-boat", "item:red-boat"] if kind in {
            "voluntary_selection", "return_visit"
        } else []
    return envelope(
        event_id,
        INTERACTION_EVENT,
        f"interaction-adapter:{adapter}",
        {
            "encounter_id": encounter,
            "subject_ref": subject,
            "evidence_kind": kind,
            "origin": origin,
            "context": "synthetic local test context",
            "meaningful_alternatives": meaningful,
            "choice_set_refs": list(choice_set),
            "selected_ref": selected,
            "origin_event_id": origin_event_id,
            "related_event_id": related_event_id,
            "adapter": {"component": adapter, "version": "0.1"},
            "session_scope": "synthetic-test-session",
        },
        at=at,
    )


def motivation_proposal(
    proposal_id,
    *,
    operation="create",
    kind="interest",
    subject="topic:blue-boat",
    scope="general",
    statement=None,
    support=("interaction-1",),
    counter=(),
    new_signal_id="signal-blue-boat",
    target_signal_id=None,
    target_version=None,
    based_on=0,
    requested_stage="tentative",
    source_component="test.synthesizer",
    at="2026-11-14T10:05:00+00:00",
):
    effective_statement = (
        statement if statement is not None
        else ("A tentative interest in blue-boat videos." if operation == "create" else None)
    )
    return envelope(
        f"event-{proposal_id}",
        MOTIVATION_PROPOSAL_EVENT,
        f"motivation-proposal:{source_component}",
        {
            "proposal_id": proposal_id,
            "operation": operation,
            "kind": kind,
            "subject_ref": subject,
            "scope": scope,
            "statement": effective_statement,
            "supporting_event_ids": list(support),
            "counter_evidence_event_ids": list(counter),
            "new_signal_id": new_signal_id,
            "target_signal_id": target_signal_id,
            "target_signal_version": target_version,
            "requested_interest_stage": requested_stage if kind == "interest" else None,
            "rationale": "Synthetic hypothesis; not a factual verdict.",
            "origin": {"component": source_component, "version": "0.1"},
            "based_on": {"state_version": based_on},
        },
        at=at,
    )


class CognitiveMotivationStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "cognitive-motivation.sqlite3"
        self.store = CognitiveMemoryStore(self.db_path)

    def tearDown(self):
        try:
            self.store.close()
        except sqlite3.ProgrammingError:
            pass
        self.temp_dir.cleanup()

    def add_interaction(self, event):
        return self.store.submit_event(event)

    def add_proposal(self, event):
        return self.store.submit_event(event)

    def test_migration_creates_schema_v2_and_preserves_v1_memory_data(self):
        observation = envelope(
            "migration-observation",
            OBSERVATION_EVENT,
            "test.observation",
            {
                "observation_id": "obs-migration",
                "observation_kind": "text_fixture",
                "content": "A legacy observation retained through schema migration.",
                "source_ref": "fixture://migration",
                "observed_at": "2026-11-14T09:00:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
            at="2026-11-14T09:00:00+00:00",
        )
        self.store.submit_event(observation)
        proposal = envelope(
            "migration-memory-proposal-event",
            PROPOSAL_EVENT,
            "test.memory-provider",
            {
                "proposal_id": "migration-memory-proposal",
                "memory_kind": "episodic_candidate",
                "candidate_content": "A legacy memory candidate retained through migration.",
                "evidence_event_ids": ["migration-observation"],
                "origin": {"component": "test.memory-provider", "version": "0.1"},
                "uncertainty": {"label": "fixture", "confidence": None},
                "based_on": {"state_version": 0},
                "operation": "create",
            },
            at="2026-11-14T09:01:00+00:00",
        )
        self.store.submit_event(proposal)
        decision = self.store.evaluate_proposal("migration-memory-proposal")
        self.assertEqual(decision["status"], "accepted")
        before = self.store.get_state_snapshot()
        before_proposal = self.store.get_proposal("migration-memory-proposal")

        # Reconstruct the actual v1 table shape: legacy event/proposal/memory
        # tables remain, while v2-only motivation projection tables do not exist.
        self.store.close()
        connection = sqlite3.connect(self.db_path)
        connection.execute("DROP TABLE motivation_signal_versions")
        connection.execute("DROP TABLE motivation_signals")
        connection.execute("DROP TABLE motivation_proposals")
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        connection.close()

        self.store = CognitiveMemoryStore(self.db_path)
        after = self.store.get_state_snapshot()
        version = int(self.store._db.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(version, 2)
        self.assertEqual(after["event_count"], before["event_count"])
        self.assertEqual(after["state_version"], before["state_version"])
        self.assertEqual(after["accepted_memory_count"], before["accepted_memory_count"])
        self.assertEqual(
            self.store.get_proposal("migration-memory-proposal"),
            before_proposal,
        )
        self.assertEqual(
            self.store.get_event("migration-observation")["event_type"],
            OBSERVATION_EVENT,
        )

    def test_failed_v1_to_v2_migration_rolls_back_partial_ddl(self):
        self.store.close()
        connection = sqlite3.connect(self.db_path)
        connection.execute("DROP TABLE motivation_signal_versions")
        connection.execute("DROP TABLE motivation_signals")
        connection.execute("DROP TABLE motivation_proposals")
        # Force the second CREATE TABLE in the migration to fail, after the
        # first table has been created inside the migration transaction.
        connection.execute(
            "CREATE TABLE motivation_signal_versions (collision_marker TEXT)"
        )
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
        connection.close()

        candidate = CognitiveMemoryStore.__new__(CognitiveMemoryStore)
        candidate._db = sqlite3.connect(str(self.db_path), isolation_level=None)
        candidate._db.row_factory = sqlite3.Row
        self.store = candidate
        with self.assertRaises(sqlite3.OperationalError):
            candidate._initialize()

        self.assertFalse(candidate._db.in_transaction)
        version = int(candidate._db.execute("PRAGMA user_version").fetchone()[0])
        self.assertEqual(version, 1)
        tables = {
            row["name"]
            for row in candidate._db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertNotIn("motivation_proposals", tables)
        self.assertIn("motivation_signal_versions", tables)

    def test_fresh_schema_is_v2(self):
        self.assertEqual(
            int(self.store._db.execute("PRAGMA user_version").fetchone()[0]),
            2,
        )

    def test_voluntary_choice_requires_internal_origin_and_real_choice_set(self):
        bad = interaction(
            "interaction-bad-origin",
            kind="voluntary_selection",
            origin="user_request",
            origin_event_id="missing-trigger",
        )
        with self.assertRaises(ValueError):
            self.add_interaction(bad)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 0)

    def test_voluntary_choice_requires_selected_item_in_choice_set(self):
        bad = interaction(
            "interaction-bad-choice",
            selected="item:not-offered",
        )
        with self.assertRaises(ValueError):
            self.add_interaction(bad)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 0)

    def test_voluntary_choice_requires_at_least_two_alternatives(self):
        bad = interaction(
            "interaction-one-choice",
            choice_set=["item:blue-boat"],
        )
        with self.assertRaises(ValueError):
            self.add_interaction(bad)

    def test_platform_autoplay_cannot_be_mislabeled_as_internal(self):
        bad = interaction(
            "interaction-autoplay-forged",
            kind="platform_autoplay",
            origin="internal_state",
            meaningful=False,
            choice_set=[],
            selected="item:blue-boat",
            origin_event_id="missing-trigger",
        )
        with self.assertRaises(ValueError):
            self.add_interaction(bad)

    def test_user_requested_action_requires_existing_origin_event(self):
        source = envelope(
            "source-user-request",
            OBSERVATION_EVENT,
            "test.user-request-fixture",
            {
                "observation_id": "obs-user-request",
                "observation_kind": "user_message",
                "content": "Synthetic user request provenance.",
                "source_ref": "fixture://user-request",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
            at="2026-11-14T09:59:00+00:00",
        )
        self.store.submit_event(source)
        requested = interaction(
            "interaction-requested",
            kind="user_requested_action",
            origin="user_request",
            meaningful=False,
            choice_set=[],
            selected="item:blue-boat",
            origin_event_id="source-user-request",
        )
        self.assertEqual(self.add_interaction(requested)["status"], "accepted")

    def test_external_origin_must_match_referenced_observation_kind(self):
        generic = envelope(
            "source-generic-observation",
            OBSERVATION_EVENT,
            "test.generic-observation",
            {
                "observation_id": "obs-generic",
                "observation_kind": "text_fixture",
                "content": "This is not a user request.",
                "source_ref": "fixture://generic",
                "observed_at": "2026-11-14T09:58:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
            at="2026-11-14T09:58:00+00:00",
        )
        self.store.submit_event(generic)
        bad_request = interaction(
            "interaction-false-user-origin",
            kind="user_requested_action",
            origin="user_request",
            meaningful=False,
            choice_set=[],
            origin_event_id="source-generic-observation",
            at="2026-11-14T09:59:00+00:00",
        )
        with self.assertRaises(ValueError):
            self.add_interaction(bad_request)

        platform = envelope(
            "source-platform-recommendation",
            OBSERVATION_EVENT,
            "test.platform-recommendation",
            {
                "observation_id": "obs-platform",
                "observation_kind": "platform_recommendation",
                "content": "The platform recommended a blue-boat video.",
                "source_ref": "fixture://platform-recommendation",
                "observed_at": "2026-11-14T10:00:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
            at="2026-11-14T10:00:00+00:00",
        )
        self.store.submit_event(platform)
        autoplay = interaction(
            "interaction-platform-autoplay",
            kind="platform_autoplay",
            origin="platform_recommendation",
            meaningful=False,
            choice_set=[],
            origin_event_id="source-platform-recommendation",
            at="2026-11-14T10:01:00+00:00",
        )
        self.assertEqual(self.add_interaction(autoplay)["status"], "accepted")

    def test_return_visit_requires_prior_same_subject_and_item(self):
        prior = interaction(
            "interaction-prior",
            kind="user_requested_action",
            origin="user_request",
            meaningful=False,
            choice_set=[],
            selected="item:blue-boat",
        )
        # This fixture's origin event is deliberately present first.
        source = envelope(
            "source-user-request",
            OBSERVATION_EVENT,
            "test.user-request-fixture",
            {
                "observation_id": "obs-request",
                "observation_kind": "user_message",
                "content": "A request.",
                "source_ref": "fixture://request",
                "observed_at": "2026-11-14T09:58:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
            at="2026-11-14T09:58:00+00:00",
        )
        self.store.submit_event(source)
        prior_payload = dict(prior.payload)
        prior_payload["origin_event_id"] = "source-user-request"
        prior = envelope(
            prior.event_id, prior.event_type, prior.source, prior_payload,
            at="2026-11-14T09:59:00+00:00",
        )
        self.add_interaction(prior)

        returned = interaction(
            "interaction-return",
            kind="return_visit",
            origin="internal_state",
            encounter="enc-2",
            related_event_id="interaction-prior",
            at="2026-11-14T11:00:00+00:00",
        )
        self.add_interaction(returned)
        bad = interaction(
            "interaction-return-wrong",
            kind="return_visit",
            origin="internal_state",
            encounter="enc-3",
            related_event_id="interaction-prior",
            selected="item:red-boat",
            at="2026-11-14T12:00:00+00:00",
        )
        with self.assertRaises(ValueError):
            self.add_interaction(bad)

        same_encounter = interaction(
            "interaction-return-same-encounter",
            kind="return_visit",
            origin="internal_state",
            encounter="enc-1",
            related_event_id="interaction-prior",
            at="2026-11-14T12:30:00+00:00",
        )
        with self.assertRaises(ValueError):
            self.add_interaction(same_encounter)

        out_of_order = interaction(
            "interaction-return-out-of-order",
            kind="return_visit",
            origin="internal_state",
            encounter="enc-4",
            related_event_id="interaction-prior",
            at="2026-11-14T09:30:00+00:00",
        )
        with self.assertRaises(ValueError):
            self.add_interaction(out_of_order)

    def test_return_visit_requires_a_prior_voluntary_selection(self):
        prior = interaction(
            "interaction-passive-prior",
            kind="passive_exposure",
            meaningful=False,
            choice_set=[],
            selected="item:blue-boat",
            encounter="enc-passive-prior",
        )
        self.add_interaction(prior)
        returned = interaction(
            "interaction-return-after-passive",
            kind="return_visit",
            encounter="enc-return-after-passive",
            related_event_id="interaction-passive-prior",
            at="2026-11-14T11:00:00+00:00",
        )
        with self.assertRaises(ValueError):
            self.add_interaction(returned)

    def test_adapter_source_must_match_adapter_metadata(self):
        good = interaction("interaction-adapter-source")
        bad = envelope(
            good.event_id,
            good.event_type,
            "interaction-adapter:other",
            good.payload,
            at=good.occurred_at,
        )
        with self.assertRaises(ValueError):
            self.add_interaction(bad)

    def test_interaction_event_identity_is_idempotent(self):
        event = interaction("interaction-idempotent")
        self.assertEqual(self.add_interaction(event)["status"], "accepted")
        self.assertEqual(self.add_interaction(event)["status"], "duplicate")
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 1)

    def test_interaction_event_identity_conflict_is_rejected(self):
        event = interaction("interaction-conflict")
        self.add_interaction(event)
        changed = interaction(
            "interaction-conflict",
            encounter="different-encounter",
        )
        with self.assertRaises(CognitiveIdempotencyConflict):
            self.add_interaction(changed)

    def test_observation_event_cannot_be_used_as_motivation_evidence(self):
        observation = envelope(
            "observation-not-interaction",
            OBSERVATION_EVENT,
            "test.observation",
            {
                "observation_id": "obs-1",
                "observation_kind": "text_fixture",
                "content": "Not an interaction choice.",
                "source_ref": "fixture://obs",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        )
        self.store.submit_event(observation)
        proposal = motivation_proposal(
            "proposal-wrong-evidence",
            support=("observation-not-interaction",),
        )
        with self.assertRaises(ValueError):
            self.add_proposal(proposal)

    def test_motivation_proposal_requires_exact_schema(self):
        self.add_interaction(interaction("interaction-1"))
        event = motivation_proposal("proposal-extra-field")
        payload = dict(event.payload)
        payload["origin_class"] = "internally_initiated"
        forged = envelope(
            event.event_id,
            event.event_type,
            event.source,
            payload,
            at=event.occurred_at,
        )
        with self.assertRaises(ValueError):
            self.add_proposal(forged)

    def test_motivation_proposal_identity_conflict_is_rejected(self):
        self.add_interaction(interaction("interaction-1"))
        first = motivation_proposal("proposal-identity")
        self.add_proposal(first)
        second = motivation_proposal(
            "proposal-identity",
            statement="A changed statement with the same proposal identity.",
        )
        second = envelope(
            "event-proposal-identity-copy",
            second.event_type,
            second.source,
            second.payload,
            at=second.occurred_at,
        )
        with self.assertRaises(CognitiveIdempotencyConflict):
            self.add_proposal(second)

    def test_create_interest_proposal_becomes_accepted_signal(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-create"))
        result = self.store.evaluate_motivation_proposal("proposal-create")
        self.assertEqual(result["status"], "accepted")
        signals = self.store.get_motivation_signals()
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["signal_id"], "signal-blue-boat")
        self.assertEqual(signals[0]["signal_version"], 1)
        self.assertEqual(signals[0]["origin_class"], "internally_initiated")
        self.assertEqual(signals[0]["interest_stage"], "tentative")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], 1)
        self.assertTrue(self.store.get_state_snapshot()["projection_consistent"])

    def test_counter_evidence_does_not_change_signal_origin_class(self):
        positive = interaction(
            "interaction-positive-origin",
            kind="voluntary_selection",
            origin="internal_state",
            encounter="enc-positive-origin",
        )
        self.add_interaction(positive)
        user_request = envelope(
            "source-user-counter",
            OBSERVATION_EVENT,
            "test.user-request",
            {
                "observation_id": "obs-user-counter",
                "observation_kind": "user_message",
                "content": "Please look at this related item.",
                "source_ref": "fixture://user-counter",
                "observed_at": "2026-11-14T09:59:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
            at="2026-11-14T09:59:00+00:00",
        )
        self.store.submit_event(user_request)
        counter = interaction(
            "interaction-user-counter",
            kind="counter_evidence",
            origin="user_request",
            meaningful=False,
            choice_set=[],
            selected=None,
            origin_event_id="source-user-counter",
            at="2026-11-14T10:00:00+00:00",
        )
        self.add_interaction(counter)
        self.add_proposal(motivation_proposal(
            "proposal-positive-origin",
            support=("interaction-positive-origin",),
            counter=("interaction-user-counter",),
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("proposal-positive-origin")["status"],
            "accepted",
        )
        self.assertEqual(
            self.store.get_motivation_signal("signal-blue-boat")["origin_class"],
            "internally_initiated",
        )

    def test_user_request_origin_is_preserved_when_later_independent_choices_accumulate(self):
        source = envelope(
            "source-user-request",
            OBSERVATION_EVENT,
            "test.user-request",
            {
                "observation_id": "obs-request",
                "observation_kind": "user_message",
                "content": "Synthetic request.",
                "source_ref": "fixture://request",
                "observed_at": "2026-11-14T09:58:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
            at="2026-11-14T09:58:00+00:00",
        )
        self.store.submit_event(source)
        requested = interaction(
            "interaction-request",
            kind="user_requested_action",
            origin="user_request",
            meaningful=False,
            choice_set=[],
            selected="item:blue-boat",
            origin_event_id="source-user-request",
            at="2026-11-14T09:59:00+00:00",
        )
        self.add_interaction(requested)
        self.add_proposal(motivation_proposal(
            "proposal-initial-user",
            support=("interaction-request",),
            based_on=0,
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("proposal-initial-user")["status"],
            "accepted",
        )
        first = self.store.get_motivation_signal("signal-blue-boat")
        self.assertEqual(first["origin_class"], "user_requested_encounter")
        self.assertEqual(first["voluntary_encounters"], [])

        chosen = interaction(
            "interaction-voluntary-1",
            kind="voluntary_selection",
            origin="internal_state",
            encounter="enc-voluntary-1",
            at="2026-11-14T10:30:00+00:00",
        )
        self.add_interaction(chosen)
        self.add_proposal(motivation_proposal(
            "proposal-reinforce-one",
            operation="reinforce",
            support=("interaction-voluntary-1",),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=1,
            based_on=1,
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("proposal-reinforce-one")["status"],
            "accepted",
        )
        second = self.store.get_motivation_signal("signal-blue-boat")
        self.assertEqual(second["origin_class"], "user_requested_encounter")
        self.assertEqual(len(second["voluntary_encounters"]), 1)
        self.assertEqual(second["interest_stage"], "tentative")

        returned = interaction(
            "interaction-voluntary-2",
            kind="return_visit",
            origin="internal_state",
            encounter="enc-voluntary-2",
            related_event_id="interaction-request",
            at="2026-11-14T12:00:00+00:00",
        )
        self.add_interaction(returned)
        self.add_proposal(motivation_proposal(
            "proposal-reinforce-two",
            operation="reinforce",
            support=("interaction-voluntary-2",),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=2,
            based_on=2,
            requested_stage="emerging",
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("proposal-reinforce-two")["status"],
            "accepted",
        )
        third = self.store.get_motivation_signal("signal-blue-boat")
        self.assertEqual(third["origin_class"], "user_requested_encounter")
        self.assertEqual(len(third["voluntary_encounters"]), 2)
        self.assertEqual(third["interest_stage"], "emerging")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], 3)

    def test_update_cannot_reuse_prior_evidence(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-create"))
        self.store.evaluate_motivation_proposal("proposal-create")
        proposal = motivation_proposal(
            "proposal-reuse",
            operation="reinforce",
            support=("interaction-1",),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=1,
            based_on=1,
        )
        with self.assertRaises(ValueError):
            self.add_proposal(proposal)

    def test_identical_proposal_identity_with_new_event_id_is_idempotent_after_acceptance(self):
        self.add_interaction(interaction("interaction-1"))
        first = motivation_proposal("proposal-same")
        self.add_proposal(first)
        self.store.evaluate_motivation_proposal("proposal-same")
        duplicate = envelope(
            "event-proposal-same-duplicate",
            first.event_type,
            first.source,
            first.payload,
            at="2026-11-14T11:00:00+00:00",
        )
        self.assertEqual(self.add_proposal(duplicate)["status"], "accepted")
        self.assertEqual(self.store.get_motivation_signals()[0]["signal_version"], 1)
        self.store.recover()
        self.assertEqual(self.store.get_motivation_signals()[0]["signal_version"], 1)

    def test_duplicate_motivation_proposal_cannot_bypass_source_validation(self):
        self.add_interaction(interaction("interaction-duplicate-source"))
        original = motivation_proposal(
            "proposal-duplicate-source",
            support=("interaction-duplicate-source",),
        )
        self.add_proposal(original)
        before = self.store.get_state_snapshot()["event_count"]
        forged_duplicate = envelope(
            "event-proposal-duplicate-source-copy",
            original.event_type,
            "motivation-proposal:forged-component",
            original.payload,
            at="2026-11-14T11:00:00+00:00",
        )
        with self.assertRaises(ValueError):
            self.add_proposal(forged_duplicate)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)

    def test_update_target_version_must_be_positive_integer(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-create"))
        self.store.evaluate_motivation_proposal("proposal-create")
        event = motivation_proposal(
            "proposal-bool-version",
            operation="reinforce",
            support=("interaction-2",),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=True,
            based_on=1,
        )
        with self.assertRaises(ValueError):
            self.add_proposal(event)

    def test_motivation_proposal_stale_global_state_is_deferred(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-create"))
        self.store.evaluate_motivation_proposal("proposal-create")
        second = interaction(
            "interaction-2",
            encounter="enc-2",
            at="2026-11-14T11:00:00+00:00",
        )
        self.add_interaction(second)
        self.add_proposal(motivation_proposal(
            "proposal-stale-state",
            operation="reinforce",
            support=("interaction-2",),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=1,
            based_on=0,
        ))
        result = self.store.evaluate_motivation_proposal("proposal-stale-state")
        self.assertEqual(result["status"], "deferred")
        self.assertEqual(self.store.get_motivation_signal("signal-blue-boat")["signal_version"], 1)
        self.assertEqual(self.store.get_state_snapshot()["state_version"], 1)

    def test_pausing_signal_is_a_durable_state_transition(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-create"))
        self.store.evaluate_motivation_proposal("proposal-create")
        pause = motivation_proposal(
            "proposal-pause",
            operation="pause",
            support=(),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=1,
            based_on=1,
        )
        self.add_proposal(pause)
        result = self.store.evaluate_motivation_proposal("proposal-pause")
        self.assertEqual(result["status"], "accepted")
        state = self.store.get_motivation_signal("signal-blue-boat")
        self.assertEqual(state["status"], "paused")
        self.assertEqual(state["signal_version"], 2)
        self.assertEqual(self.store.get_state_snapshot()["state_version"], 2)

    def test_signal_lifecycle_weaken_contextualize_and_resolve(self):
        self.add_interaction(interaction("interaction-lifecycle-create"))
        self.add_proposal(motivation_proposal(
            "proposal-lifecycle-create",
            support=("interaction-lifecycle-create",),
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("proposal-lifecycle-create")["status"],
            "accepted",
        )

        counter = interaction(
            "interaction-lifecycle-counter",
            kind="counter_evidence",
            meaningful=False,
            choice_set=[],
            selected=None,
            at="2026-11-14T10:30:00+00:00",
        )
        self.add_interaction(counter)
        self.add_proposal(motivation_proposal(
            "proposal-lifecycle-weaken",
            operation="weaken",
            support=(),
            counter=("interaction-lifecycle-counter",),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=1,
            based_on=1,
            at="2026-11-14T10:31:00+00:00",
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("proposal-lifecycle-weaken")["status"],
            "accepted",
        )
        weakened = self.store.get_motivation_signal("signal-blue-boat")
        self.assertEqual(weakened["signal_version"], 2)
        self.assertEqual(
            weakened["counter_evidence_event_ids"],
            ["interaction-lifecycle-counter"],
        )

        contextual_choice = interaction(
            "interaction-lifecycle-context",
            encounter="enc-lifecycle-context",
            at="2026-11-14T11:00:00+00:00",
        )
        self.add_interaction(contextual_choice)
        self.add_proposal(motivation_proposal(
            "proposal-lifecycle-contextualize",
            operation="contextualize",
            support=("interaction-lifecycle-context",),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=2,
            based_on=2,
            statement="An interest limited to a particular kind of blue-boat video.",
            scope="video:blue-boat",
            requested_stage=None,
            at="2026-11-14T11:01:00+00:00",
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("proposal-lifecycle-contextualize")["status"],
            "accepted",
        )
        contextualized = self.store.get_motivation_signal("signal-blue-boat")
        self.assertEqual(contextualized["signal_version"], 3)
        self.assertEqual(contextualized["interest_stage"], "contextual")
        self.assertEqual(contextualized["scope"], "video:blue-boat")

        resolution = interaction(
            "interaction-lifecycle-resolution",
            kind="resolution",
            meaningful=False,
            choice_set=[],
            selected=None,
            at="2026-11-14T12:00:00+00:00",
        )
        self.add_interaction(resolution)
        self.add_proposal(motivation_proposal(
            "proposal-lifecycle-resolve",
            operation="resolve",
            support=("interaction-lifecycle-resolution",),
            new_signal_id=None,
            target_signal_id="signal-blue-boat",
            target_version=3,
            scope="video:blue-boat",
            based_on=3,
            at="2026-11-14T12:01:00+00:00",
        ))
        self.assertEqual(
            self.store.evaluate_motivation_proposal("proposal-lifecycle-resolve")["status"],
            "accepted",
        )
        resolved = self.store.get_motivation_signal("signal-blue-boat")
        self.assertEqual(resolved["signal_version"], 4)
        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(self.store.get_state_snapshot()["state_version"], 4)

    def test_csd_decision_event_cannot_be_forged_through_public_submit(self):
        forged = envelope(
            "forged-motivation-decision",
            MOTIVATION_DECISION_EVENT,
            "csd.authority.v1",
            {},
        )
        with self.assertRaises(ValueError):
            self.store.submit_event(forged)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 0)

    def test_failed_motivation_projection_rolls_back_decision_and_signal(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-atomic"))
        original = self.store._apply_motivation_decision

        def fail(*args, **kwargs):
            raise RuntimeError("injected failure before commit")

        self.store._apply_motivation_decision = fail
        before = self.store.get_state_snapshot()["event_count"]
        with self.assertRaises(RuntimeError):
            self.store.evaluate_motivation_proposal("proposal-atomic")
        self.store._apply_motivation_decision = original
        self.assertEqual(self.store.get_state_snapshot()["event_count"], before)
        self.assertEqual(self.store.get_motivation_proposal("proposal-atomic")["status"], "pending")
        self.assertEqual(self.store.get_motivation_signals(), [])

    def test_recovery_rebuilds_motivation_projections_without_provider(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-recover"))
        self.store.evaluate_motivation_proposal("proposal-recover")
        before = self.store.get_motivation_signals()

        def forbidden(*args, **kwargs):
            raise AssertionError("recovery must never invoke a synthesizer")

        self.store.evaluate_motivation_proposal = forbidden
        report = self.store.recover()
        self.assertEqual(report["motivation_signals"], 1)
        self.assertEqual(self.store.get_motivation_signals(), before)

    def test_recovery_detects_coordinated_signal_projection_tampering(self):
        self.add_interaction(interaction("interaction-tamper-signal"))
        self.add_proposal(motivation_proposal(
            "proposal-tamper-signal",
            support=("interaction-tamper-signal",),
        ))
        self.store.evaluate_motivation_proposal("proposal-tamper-signal")
        expected = self.store.get_motivation_signals()

        # Corrupt both projection tables identically. Cross-checking the tables
        # against each other alone would incorrectly consider this consistent.
        self.store._db.execute(
            "UPDATE motivation_signal_versions SET signal_json='{}' "
            "WHERE signal_id='signal-blue-boat'"
        )
        self.store._db.execute(
            "UPDATE motivation_signals SET signal_json='{}' "
            "WHERE signal_id='signal-blue-boat'"
        )
        self.assertFalse(self.store.get_state_snapshot()["projection_consistent"])
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_motivation_signals()

        self.store.recover()
        self.assertTrue(self.store.get_state_snapshot()["projection_consistent"])
        self.assertEqual(self.store.get_motivation_signals(), expected)

    def test_motivation_proposal_projection_is_checked_against_event_history(self):
        self.add_interaction(interaction("interaction-tamper-proposal"))
        self.add_proposal(motivation_proposal(
            "proposal-tamper-status",
            support=("interaction-tamper-proposal",),
        ))
        self.store.evaluate_motivation_proposal("proposal-tamper-status")
        self.store._db.execute(
            "UPDATE motivation_proposals SET status='rejected' "
            "WHERE proposal_id='proposal-tamper-status'"
        )
        self.assertFalse(self.store.get_state_snapshot()["projection_consistent"])
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_motivation_proposal("proposal-tamper-status")

        self.store.recover()
        self.assertEqual(
            self.store.get_motivation_proposal("proposal-tamper-status")["status"],
            "accepted",
        )

    def test_recovery_repairs_deleted_motivation_projection(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-rebuild"))
        self.store.evaluate_motivation_proposal("proposal-rebuild")
        self.store._db.execute("DELETE FROM motivation_signals")
        self.assertFalse(self.store.get_state_snapshot()["projection_consistent"])
        with self.assertRaises(CognitiveIntegrityError):
            self.store.get_motivation_signals()
        self.store.recover()
        self.assertTrue(self.store.get_state_snapshot()["projection_consistent"])
        self.assertEqual(len(self.store.get_motivation_signals()), 1)

    def test_memory_and_motivation_share_one_global_state_version(self):
        self.add_interaction(interaction("interaction-1"))
        self.add_proposal(motivation_proposal("proposal-first-motivation"))
        self.store.evaluate_motivation_proposal("proposal-first-motivation")

        observation = envelope(
            "memory-observation",
            OBSERVATION_EVENT,
            "test.observation",
            {
                "observation_id": "obs-memory",
                "observation_kind": "text_fixture",
                "content": "A fictional boat beside a bridge.",
                "source_ref": "fixture://memory",
                "observed_at": "2026-11-14T12:30:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
            at="2026-11-14T12:30:00+00:00",
        )
        self.store.submit_event(observation)
        memory_proposal = envelope(
            "memory-proposal-event",
            PROPOSAL_EVENT,
            "test.memory-provider",
            {
                "proposal_id": "memory-proposal-1",
                "memory_kind": "episodic_candidate",
                "candidate_content": "I encountered a fictional description of a boat.",
                "evidence_event_ids": ["memory-observation"],
                "origin": {"component": "test.memory-provider", "version": "0.1"},
                "uncertainty": {"label": "fixture", "confidence": None},
                "based_on": {"state_version": 1},
                "operation": "create",
            },
            at="2026-11-14T12:31:00+00:00",
        )
        self.store.submit_event(memory_proposal)
        self.assertEqual(self.store.evaluate_proposal("memory-proposal-1")["status"], "accepted")
        state = self.store.get_state_snapshot()
        self.assertEqual(state["state_version"], 2)
        self.assertEqual(state["accepted_memory_count"], 1)
        self.assertEqual(state["motivation_signal_count"], 1)
        self.assertTrue(state["projection_consistent"])

    def test_memory_decision_after_motivation_does_not_break_recovery(self):
        self.test_memory_and_motivation_share_one_global_state_version()
        before = self.store.get_state_snapshot()
        self.store.recover()
        after = self.store.get_state_snapshot()
        self.assertEqual(after["state_version"], before["state_version"])
        self.assertTrue(after["projection_consistent"])


if __name__ == "__main__":
    unittest.main()
