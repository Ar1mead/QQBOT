import hashlib
import unittest

from adapters.contracts.observation import (
    AdapterManifest,
    Capability,
    CapabilityMode,
    ObservationRequest,
    ObservationStatus,
)
from adapters.worker_host import (
    WorkerExecutionError,
    WorkerHost,
    WorkerProcessObservationAdapter,
)
from adapters.worker_protocol import WorkerResponse, encode_response


class FakeWorkerExecutor:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def execute(self, request_payload, *, timeout_seconds, max_response_bytes):
        self.calls.append((request_payload, timeout_seconds, max_response_bytes))
        if self.error:
            raise self.error
        return self.response


class WorkerHostTests(unittest.TestCase):
    def setUp(self):
        self.manifest = AdapterManifest(
            adapter_id="test.worker",
            adapter_version="1.2.0",
            platform="test-platform",
            capabilities=(
                Capability("observe:text", CapabilityMode.OBSERVE, "Read text"),
            ),
        )
        self.request = ObservationRequest("req-01", "target:42", ("text",))

    def make_evidence(self, **changes):
        content = "worker supplied evidence"
        evidence = {
            "observation_id": "obs-01",
            "adapter_id": self.manifest.adapter_id,
            "adapter_version": self.manifest.adapter_version,
            "platform": self.manifest.platform,
            "external_ref": self.request.target_ref,
            "observation_kind": "caption",
            "content_origin": "source_provided",
            "modality": "text",
            "content": content,
            "source_ref": "https://example.invalid/source",
            "observed_at": "2026-11-18T10:00:00+00:00",
            "received_at": "2026-11-18T10:00:01+00:00",
            "extraction_method": "worker_fixture",
            "content_digest": "sha256:" + hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "coverage": {
                "modality": "text",
                "extraction_method": "worker_fixture",
                "complete": True,
                "start_ms": None,
                "end_ms": None,
                "missing_ranges_ms": [],
                "notes": [],
            },
            "source_artifact_ref": None,
            "account_ref": None,
            "untrusted": True,
        }
        evidence.update(changes)
        return evidence

    def make_executor(self, evidence=None):
        response = WorkerResponse(
            request_id=self.request.request_id,
            adapter_id=self.manifest.adapter_id,
            adapter_version=self.manifest.adapter_version,
            status="complete",
            evidence=(evidence or self.make_evidence(),),
        )
        return FakeWorkerExecutor(response=encode_response(response))

    def test_adapter_routes_through_injected_executor_and_validates_result(self):
        executor = self.make_executor()
        adapter = WorkerProcessObservationAdapter(self.manifest, WorkerHost(executor))
        result = adapter.observe(self.request)
        self.assertEqual(result.status, ObservationStatus.COMPLETE)
        self.assertEqual(len(result.evidence), 1)
        self.assertEqual(len(executor.calls), 1)
        _, timeout, max_bytes = executor.calls[0]
        self.assertEqual(timeout, 15.0)
        self.assertGreater(max_bytes, 0)

    def test_host_requires_explicit_executor_and_has_no_fallback(self):
        with self.assertRaisesRegex(ValueError, "reviewed worker executor"):
            WorkerHost(None)

    def test_host_bounds_timeout_and_response_size(self):
        executor = self.make_executor()
        with self.assertRaisesRegex(ValueError, "timeout_seconds"):
            WorkerHost(executor, timeout_seconds=0)
        with self.assertRaisesRegex(ValueError, "timeout_seconds"):
            WorkerHost(executor, timeout_seconds=121)
        with self.assertRaisesRegex(ValueError, "max_response_bytes"):
            WorkerHost(executor, max_response_bytes=0)

    def test_timeout_fails_closed(self):
        executor = FakeWorkerExecutor(error=TimeoutError("late"))
        adapter = WorkerProcessObservationAdapter(self.manifest, WorkerHost(executor))
        with self.assertRaisesRegex(WorkerExecutionError, "timed out"):
            adapter.observe(self.request)

    def test_invalid_worker_response_fails_closed(self):
        executor = FakeWorkerExecutor(response=b'{"unexpected":true}')
        adapter = WorkerProcessObservationAdapter(self.manifest, WorkerHost(executor))
        with self.assertRaisesRegex(WorkerExecutionError, "response rejected"):
            adapter.observe(self.request)

    def test_host_rejects_response_larger_than_configured_limit(self):
        executor = FakeWorkerExecutor(response=b"x" * 32)
        adapter = WorkerProcessObservationAdapter(
            self.manifest,
            WorkerHost(executor, max_response_bytes=16),
        )
        with self.assertRaisesRegex(WorkerExecutionError, "size limit"):
            adapter.observe(self.request)

    def test_adapter_rejects_evidence_for_another_platform_or_target(self):
        for changes, message in (
            ({"platform": "other-platform"}, "platform"),
            ({"external_ref": "other-target"}, "target"),
        ):
            executor = self.make_executor(self.make_evidence(**changes))
            adapter = WorkerProcessObservationAdapter(self.manifest, WorkerHost(executor))
            with self.subTest(message=message):
                with self.assertRaisesRegex(WorkerExecutionError, message):
                    adapter.observe(self.request)


if __name__ == "__main__":
    unittest.main()
