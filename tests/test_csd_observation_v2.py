from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from adapters.contracts.observation import (
    ContentOrigin,
    ObservationCoverage,
    ObservationEvidence,
)
from adapters.csd_mapping import observation_evidence_to_csd_event
from core.csd import (
    CognitiveEvent,
    CognitiveIdempotencyConflict,
    CognitiveIntegrityError,
    CognitiveMemoryStore,
    GroundedMemoryCandidate,
    GroundedMemoryProposalPipeline,
    GroundedSourceAssertion,
)
from core.csd.cognitive import OBSERVATION_EVENT, OBSERVATION_EVENT_V2


class _GroundedProvider:
    provider_id = "test.observation-v2-provider"
    provider_version = "0.1"

    def __init__(self, candidate):
        self.candidate = candidate

    def propose_grounded(self, observation, *, state_version):
        self.observation = observation
        self.state_version = state_version
        return [self.candidate]


class CSDObservationV2Tests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = CognitiveMemoryStore(Path(self.temp_dir.name) / "observation-v2.sqlite3")
        self.content = "The subtitle reads: a silver leaf rested on the windowsill."
        self.quote = "a silver leaf rested on the windowsill."

    def tearDown(self):
        self.store.close()
        self.temp_dir.cleanup()

    def evidence(self, *, content_origin=ContentOrigin.SOURCE_PROVIDED,
                 modality="text", complete=False, account_ref="acct-opaque-01"):
        digest = "sha256:" + hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return ObservationEvidence(
            observation_id="obs-001",
            adapter_id="bilibili.readonly",
            adapter_version="0.1.0",
            platform="bilibili",
            external_ref="BV1EPnG6DEJC",
            observation_kind="subtitle",
            content_origin=content_origin,
            modality=modality,
            content=self.content,
            source_ref="bilibili://video/BV1EPnG6DEJC/subtitle/zh",
            observed_at="2026-11-16T10:00:00+00:00",
            received_at="2026-11-16T10:00:02+00:00",
            extraction_method="platform_subtitle",
            content_digest=digest,
            coverage=ObservationCoverage(
                modality=modality,
                extraction_method="platform_subtitle",
                complete=complete,
                start_ms=0,
                end_ms=60_000,
                missing_ranges_ms=((20_000, 25_000),) if not complete else (),
                notes=("Synthetic fixture; source text remains untrusted.",),
            ),
            source_artifact_ref="bilibili://video/BV1EPnG6DEJC/subtitle/zh",
            account_ref=account_ref,
        )

    def v1_event(self):
        return CognitiveEvent(
            event_id="evt-legacy-observation-v1",
            occurred_at="2026-11-16T10:00:02+00:00",
            correlation_id="legacy-observation-1",
            event_type=OBSERVATION_EVENT,
            source="test.legacy-observation",
            payload={
                "observation_id": "legacy-obs-1",
                "observation_kind": "text_fixture",
                "content": "Legacy observation remains readable.",
                "source_ref": "fixture://legacy/observation",
                "observed_at": "2026-11-16T10:00:00+00:00",
                "coverage": {"modality": "text", "complete_for_fixture": True},
            },
        )

    def test_adapter_evidence_maps_to_stable_csd_v2_event(self):
        evidence = self.evidence()
        first = observation_evidence_to_csd_event(evidence)
        second = observation_evidence_to_csd_event(evidence)

        self.assertEqual(first.event_type, OBSERVATION_EVENT_V2)
        self.assertEqual(first.event_id, "observation:bilibili.readonly:obs-001")
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(dict(first.payload), dict(second.payload))
        self.assertEqual(first.payload["content_origin"], "source_provided")
        self.assertEqual(first.payload["account_ref"], "acct-opaque-01")

        self.store.submit_event(first)
        stored = self.store.get_event(first.event_id)
        self.assertEqual(stored["payload"], dict(first.payload))
        self.assertEqual(stored["payload"]["coverage"]["missing_ranges_ms"], [[20_000, 25_000]])
        self.assertEqual(self.store.get_memories(), [])

    def test_repeated_v2_delivery_is_idempotent_and_conflicts_are_rejected(self):
        event = observation_evidence_to_csd_event(self.evidence())
        first = self.store.submit_event(event)
        duplicate = self.store.submit_event(event)

        self.assertEqual(first["status"], "accepted")
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 1)

        changed_payload = dict(event.payload)
        changed_payload["content"] = "Different content for the same stable observation ID."
        changed_payload["content_digest"] = "sha256:" + hashlib.sha256(
            changed_payload["content"].encode("utf-8")
        ).hexdigest()
        conflicting = replace(event, payload=changed_payload)
        with self.assertRaises(CognitiveIdempotencyConflict):
            self.store.submit_event(conflicting)
        self.assertEqual(self.store.get_state_snapshot()["event_count"], 1)

    def test_adapter_extracted_content_remains_untrusted(self):
        evidence = self.evidence(content_origin=ContentOrigin.ADAPTER_EXTRACTED)
        event = observation_evidence_to_csd_event(evidence)
        self.store.submit_event(event)
        stored = self.store.get_event(event.event_id)
        self.assertEqual(stored["payload"]["content_origin"], "adapter_extracted")
        self.assertIs(stored["payload"]["untrusted"], True)

    def test_v2_rejects_missing_range_outside_covered_interval(self):
        event = observation_evidence_to_csd_event(self.evidence())
        payload = dict(event.payload)
        coverage = dict(payload["coverage"])
        coverage["missing_ranges_ms"] = [[5_000, 70_000]]
        payload["coverage"] = coverage
        with self.assertRaisesRegex(ValueError, "missing range ends after covered interval"):
            self.store.submit_event(replace(event, payload=payload))

    def test_v2_rejects_overlapping_missing_ranges(self):
        event = observation_evidence_to_csd_event(self.evidence())
        payload = dict(event.payload)
        coverage = dict(payload["coverage"])
        coverage["missing_ranges_ms"] = [[10_000, 30_000], [20_000, 25_000]]
        payload["coverage"] = coverage
        with self.assertRaisesRegex(ValueError, "sorted and non-overlapping"):
            self.store.submit_event(replace(event, payload=payload))

    def test_v2_rejects_event_identity_not_bound_to_adapter(self):
        event = observation_evidence_to_csd_event(self.evidence())
        with self.assertRaisesRegex(ValueError, "identity or source"):
            self.store.submit_event(replace(event, correlation_id="unrelated-correlation"))

    def test_v2_rejects_digest_mismatch(self):
        event = observation_evidence_to_csd_event(self.evidence())
        payload = dict(event.payload)
        payload["content_digest"] = "sha256:" + ("0" * 64)
        with self.assertRaisesRegex(ValueError, "content_digest"):
            self.store.submit_event(replace(event, payload=payload))

    def test_v2_rejects_content_marked_as_trusted(self):
        event = observation_evidence_to_csd_event(self.evidence())
        payload = dict(event.payload)
        payload["untrusted"] = False
        with self.assertRaisesRegex(ValueError, "must remain untrusted"):
            self.store.submit_event(replace(event, payload=payload))

    def test_v2_rejects_coverage_modality_mismatch(self):
        event = observation_evidence_to_csd_event(self.evidence())
        payload = dict(event.payload)
        coverage = dict(payload["coverage"])
        coverage["modality"] = "audio"
        payload["coverage"] = coverage
        with self.assertRaisesRegex(ValueError, "coverage modality mismatch"):
            self.store.submit_event(replace(event, payload=payload))

    def test_recovery_rejects_v2_trust_flag_tampering_with_recomputed_digests(self):
        event = observation_evidence_to_csd_event(self.evidence())
        self.store.submit_event(event)
        stored = self.store.get_event(event.event_id)
        payload = dict(stored["payload"])
        payload["untrusted"] = False
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )
        payload_ref = "sha256:" + hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
        row = self.store._db.execute(
            "SELECT received_at FROM events WHERE event_id=?", (event.event_id,)
        ).fetchone()
        self.store._db.execute("DROP TRIGGER events_no_update")
        self.store._db.execute("DROP TRIGGER payloads_no_update")
        self.store._db.execute(
            "INSERT INTO payloads(payload_ref,payload_json) VALUES (?,?)",
            (payload_ref, payload_json),
        )
        rewritten = replace(event, payload=payload)
        event_digest = self.store._event_digest(
            rewritten, payload_ref, row["received_at"]
        )
        self.store._db.execute(
            "UPDATE events SET payload_ref=?,event_digest=? WHERE event_id=?",
            (payload_ref, event_digest, event.event_id),
        )

        with self.assertRaisesRegex(CognitiveIntegrityError, "invalid durable event schema"):
            self.store.recover()

    def test_v1_and_v2_events_survive_recovery(self):
        legacy = self.v1_event()
        modern = observation_evidence_to_csd_event(self.evidence())
        self.store.submit_event(legacy)
        self.store.submit_event(modern)

        report = self.store.recover()

        self.assertEqual(report["events"], 2)
        self.assertEqual(self.store.get_event(legacy.event_id)["event_type"], OBSERVATION_EVENT)
        self.assertEqual(self.store.get_event(modern.event_id)["event_type"], OBSERVATION_EVENT_V2)

    def test_grounded_pipeline_can_use_v2_text_observation(self):
        event = observation_evidence_to_csd_event(self.evidence(complete=False))
        self.store.submit_event(event)
        start = self.content.index(self.quote)
        candidate = GroundedMemoryCandidate(
            proposal_id="proposal-from-v2-observation",
            memory_kind="episodic_candidate",
            source_assertions=(GroundedSourceAssertion(
                claim_id="claim-source-1",
                text=self.quote,
                quoted_text=self.quote,
                start=start,
                end=start + len(self.quote),
            ),),
        )
        provider = _GroundedProvider(candidate)
        result = GroundedMemoryProposalPipeline(self.store, provider).propose_from_observation(
            event.event_id
        )

        self.assertEqual(result[0]["status"], "accepted")
        self.assertEqual(provider.observation["event_type"], OBSERVATION_EVENT_V2)
        decision = self.store.evaluate_proposal("proposal-from-v2-observation")
        self.assertEqual(decision["status"], "accepted")
        memory = self.store.get_memories()[0]
        self.assertEqual(memory["evidence_event_ids"], [event.event_id])
        self.assertEqual(memory["claims"][0]["evidence"][0]["quoted_text"], self.quote)

    def test_v2_image_observation_is_not_passed_to_text_grounded_provider(self):
        event = observation_evidence_to_csd_event(
            self.evidence(modality="image", complete=True)
        )
        self.store.submit_event(event)
        provider = _GroundedProvider(GroundedMemoryCandidate(
            proposal_id="should-not-be-created",
            memory_kind="episodic_candidate",
            source_assertions=(),
        ))
        with self.assertRaisesRegex(ValueError, "requires a text observation"):
            GroundedMemoryProposalPipeline(self.store, provider).propose_from_observation(
                event.event_id
            )
        self.assertFalse(hasattr(provider, "observation"))


if __name__ == "__main__":
    unittest.main()
