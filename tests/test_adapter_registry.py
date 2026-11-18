import hashlib
import unittest

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
from adapters.registry import (
    AdapterContractViolation,
    AdapterDispatchDenied,
    AdapterRegistrationError,
    ObservationAdapterRegistry,
)
from adapters.testing import FakeObservationAdapter


class ObservationAdapterRegistryTests(unittest.TestCase):
    def make_manifest(self, *, adapter_id="test.reader", capabilities=None):
        return AdapterManifest(
            adapter_id=adapter_id,
            adapter_version="1.0",
            platform="test-platform",
            capabilities=capabilities or (
                Capability("observe:text", CapabilityMode.OBSERVE, "Read text evidence"),
            ),
        )

    def make_evidence(self, *, adapter_id="test.reader", adapter_version="1.0",
                      platform="test-platform", modality="text"):
        content = "external text remains untrusted"
        return ObservationEvidence(
            observation_id="obs-1",
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            platform=platform,
            external_ref="item:1",
            observation_kind="caption",
            content_origin=ContentOrigin.SOURCE_PROVIDED,
            modality=modality,
            content=content,
            source_ref="https://example.invalid/item/1",
            observed_at="2026-11-18T10:00:00+00:00",
            received_at="2026-11-18T10:00:01+00:00",
            extraction_method="fixture",
            content_digest="sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest(),
            coverage=ObservationCoverage(
                modality=modality, extraction_method="fixture", complete=True
            ),
        )

    def make_adapter(self, *, manifest=None, evidence=None):
        manifest = manifest or self.make_manifest()
        result = ObservationResult(
            ObservationStatus.COMPLETE,
            evidence=(evidence or self.make_evidence(),),
        )
        return FakeObservationAdapter(manifest=manifest, result=result)

    def test_only_explicitly_registered_adapter_can_be_dispatched(self):
        registry = ObservationAdapterRegistry()
        request = ObservationRequest("req-1", "target:1", ("text",))
        with self.assertRaisesRegex(AdapterDispatchDenied, "not registered"):
            registry.observe("test.reader", request)

    def test_dispatch_allows_only_declared_observation_modalities(self):
        registry = ObservationAdapterRegistry()
        adapter = self.make_adapter()
        registry.register(adapter)
        request = ObservationRequest("req-1", "target:1", ("text",))
        result = registry.observe("test.reader", request)
        self.assertEqual(result.status, ObservationStatus.COMPLETE)
        self.assertEqual(adapter.requests, [request])

        denied = ObservationRequest("req-2", "target:1", ("text", "audio"))
        with self.assertRaisesRegex(AdapterDispatchDenied, "audio"):
            registry.observe("test.reader", denied)
        self.assertEqual(adapter.requests, [request])

    def test_registry_rejects_present_and_side_effect_manifests(self):
        for mode in (CapabilityMode.PRESENT, CapabilityMode.SIDE_EFFECT):
            manifest = self.make_manifest(capabilities=(
                Capability("unsafe", mode, "not permitted"),
            ))
            registry = ObservationAdapterRegistry()
            with self.subTest(mode=mode):
                with self.assertRaises(AdapterRegistrationError):
                    registry.register(self.make_adapter(manifest=manifest))

    def test_registry_rejects_duplicate_adapter_ids(self):
        registry = ObservationAdapterRegistry()
        registry.register(self.make_adapter())
        with self.assertRaisesRegex(AdapterRegistrationError, "already registered"):
            registry.register(self.make_adapter())

    def test_registry_pins_manifest_and_checks_returned_evidence_identity(self):
        manifest = self.make_manifest()
        adapter = self.make_adapter(
            manifest=manifest,
            evidence=self.make_evidence(adapter_version="9.9"),
        )
        registry = ObservationAdapterRegistry()
        registry.register(adapter)
        # Mutating the adapter's exposed manifest after registration must not
        # replace the manifest under which it was admitted.
        adapter.manifest = self.make_manifest(adapter_id="spoofed.reader")
        request = ObservationRequest("req-1", "target:1", ("text",))
        with self.assertRaisesRegex(AdapterContractViolation, "identity"):
            registry.observe("test.reader", request)


if __name__ == "__main__":
    unittest.main()
