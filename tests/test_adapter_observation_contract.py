import hashlib
import unittest
from dataclasses import replace

from adapters.testing import FakeObservationAdapter
from adapters.contracts.observation import (
    AdapterManifest,
    Capability,
    CapabilityMode,
    ContentOrigin,
    ObservationCoverage,
    ObservationEvidence,
    ObservationRequest,
    ObservationResult,
    ObservationStatus,
)


class ObservationContractTests(unittest.TestCase):
    def make_evidence(self, *, complete=True, missing_ranges=(), untrusted=True):
        return ObservationEvidence(
            observation_id="obs-001",
            adapter_id="test.fake",
            adapter_version="0.1.0",
            platform="test",
            external_ref="item:123",
            observation_kind="caption",
            content_origin=ContentOrigin.SOURCE_PROVIDED,
            modality="text",
            content="sample text from an untrusted source",
            source_ref="https://example.invalid/item/123",
            observed_at="2026-11-16T10:00:00+00:00",
            received_at="2026-11-16T10:00:02+00:00",
            extraction_method="fixture",
            content_digest="sha256:" + hashlib.sha256(
                b"sample text from an untrusted source"
            ).hexdigest(),
            coverage=ObservationCoverage(
                modality="text", extraction_method="fixture", complete=complete,
                missing_ranges_ms=missing_ranges,
            ),
            untrusted=untrusted,
        )

    def test_fake_adapter_implements_deterministic_observation_contract(self):
        manifest = AdapterManifest(
            adapter_id="bilibili.fake",
            adapter_version="0.1.0",
            platform="bilibili",
            capabilities=(
                Capability("video.read", CapabilityMode.OBSERVE, "Read fixture evidence"),
            ),
        )
        result = ObservationResult(
            ObservationStatus.PARTIAL,
            evidence=(self.make_evidence(complete=False),),
        )
        adapter = FakeObservationAdapter(manifest=manifest, result=result)
        request = ObservationRequest(
            request_id="request-001",
            target_ref="BV1EPnG6DEJC",
            modalities=("text", "comments"),
        )

        first = adapter.observe(request)
        second = adapter.observe(request)

        self.assertIs(first, result)
        self.assertIs(second, result)
        self.assertEqual(adapter.requests, [request, request])
        self.assertTrue(adapter.manifest.observation_only)
        self.assertTrue(first.evidence[0].untrusted)

    def test_manifest_reports_observation_only_capability_surface(self):
        manifest = AdapterManifest(
            adapter_id="bilibili.fake", adapter_version="0.1.0", platform="bilibili",
            capabilities=(Capability("video.read", CapabilityMode.OBSERVE, "Read video metadata"),),
        )
        self.assertTrue(manifest.observation_only)

    def test_manifest_marks_any_side_effect_capability_as_not_observation_only(self):
        manifest = AdapterManifest(
            adapter_id="bilibili.fake", adapter_version="0.1.0", platform="bilibili",
            capabilities=(
                Capability("video.read", CapabilityMode.OBSERVE, "Read video metadata"),
                Capability("comment.create", CapabilityMode.SIDE_EFFECT, "Post a comment"),
            ),
        )
        self.assertFalse(manifest.observation_only)

    def test_complete_result_requires_complete_coverage(self):
        evidence = self.make_evidence(complete=False, missing_ranges=((1000, 2000),))
        with self.assertRaisesRegex(ValueError, "complete result requires evidence"):
            ObservationResult(ObservationStatus.COMPLETE, evidence=(evidence,))

    def test_partial_result_preserves_incomplete_coverage(self):
        evidence = self.make_evidence(complete=False, missing_ranges=((1000, 2000),))
        result = ObservationResult(ObservationStatus.PARTIAL, evidence=(evidence,))
        self.assertEqual(result.status, ObservationStatus.PARTIAL)
        self.assertEqual(result.evidence[0].coverage.missing_ranges_ms, ((1000, 2000),))

    def test_missing_coverage_ranges_must_be_sorted_and_non_overlapping(self):
        with self.assertRaisesRegex(ValueError, "sorted and non-overlapping"):
            ObservationCoverage(
                modality="text",
                extraction_method="fixture",
                complete=False,
                missing_ranges_ms=((2000, 3000), (1000, 1500)),
            )
        with self.assertRaisesRegex(ValueError, "sorted and non-overlapping"):
            ObservationCoverage(
                modality="text",
                extraction_method="fixture",
                complete=False,
                missing_ranges_ms=((1000, 2500), (2000, 3000)),
            )

    def test_missing_coverage_ranges_must_fit_declared_interval(self):
        with self.assertRaisesRegex(ValueError, "starts before covered interval"):
            ObservationCoverage(
                modality="text",
                extraction_method="fixture",
                complete=False,
                start_ms=1000,
                end_ms=5000,
                missing_ranges_ms=((500, 1500),),
            )
        with self.assertRaisesRegex(ValueError, "ends after covered interval"):
            ObservationCoverage(
                modality="text",
                extraction_method="fixture",
                complete=False,
                start_ms=1000,
                end_ms=5000,
                missing_ranges_ms=((4500, 5500),),
            )

    def test_coverage_extraction_method_must_match_evidence(self):
        evidence = self.make_evidence()
        coverage = ObservationCoverage(
            modality="text", extraction_method="different-method", complete=True
        )
        with self.assertRaisesRegex(ValueError, "must match coverage extraction_method"):
            replace(evidence, coverage=coverage)

    def test_manifest_defaults_to_observation_v2(self):
        manifest = AdapterManifest(
            adapter_id="bilibili.fake",
            adapter_version="0.1.0",
            platform="bilibili",
            capabilities=(Capability("video.read", CapabilityMode.OBSERVE, "Read fixture"),),
        )
        self.assertEqual(manifest.observation_schema_versions, (2,))

    def test_external_evidence_cannot_be_marked_trusted(self):
        with self.assertRaisesRegex(ValueError, "must remain untrusted"):
            self.make_evidence(untrusted=False)

    def test_timestamps_must_include_timezone(self):
        evidence = self.make_evidence()
        with self.assertRaisesRegex(ValueError, "must include a timezone"):
            ObservationEvidence(
                **{**evidence.__dict__, "observed_at": "2026-11-16T10:00:00"}
            )

    def test_digest_must_be_sha256(self):
        evidence = self.make_evidence()
        with self.assertRaisesRegex(ValueError, "content_digest"):
            ObservationEvidence(**{**evidence.__dict__, "content_digest": "bad"})

    def test_digest_must_match_exact_utf8_content_bytes(self):
        evidence = self.make_evidence()
        with self.assertRaisesRegex(ValueError, "does not match the UTF-8 bytes of content"):
            ObservationEvidence(
                **{**evidence.__dict__, "content_digest": "sha256:" + "b" * 64}
            )

    def test_failed_result_requires_error_code(self):
        with self.assertRaisesRegex(ValueError, "error_code"):
            ObservationResult(ObservationStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
