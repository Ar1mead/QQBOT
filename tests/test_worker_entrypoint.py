import hashlib
import json
import unittest

from adapters.worker_entrypoint import process_one_request
from adapters.worker_protocol import (
    WorkerProtocolError,
    WorkerRequest,
    decode_response,
    encode_request,
)


def qq_record():
    content = "A message from the isolated worker fixture."
    return {
        "schema_version": 1,
        "platform": "qq",
        "record_id": "message:1001",
        "external_ref": "1001",
        "observation_kind": "qq.message.incoming",
        "content_origin": "source_provided",
        "modality": "text",
        "content": content,
        "source_ref": "surfcore://qq/message/1001",
        "observed_at": "2026-11-18T08:00:00+00:00",
        "received_at": "2026-11-18T08:00:01+00:00",
        "extraction_method": "surfcore_qq_message_normalizer",
        "coverage": {
            "modality": "text",
            "extraction_method": "surfcore_qq_message_normalizer",
            "complete": True,
            "start_ms": None,
            "end_ms": None,
            "missing_ranges_ms": [],
            "notes": ["Fixture content is untrusted."],
        },
        "account_ref": "qq-account-opaque",
        "cursor": 42,
        "conversation_kind": "group",
        "conversation_ref": "qq-group-opaque",
        "sender_ref": "qq-sender-opaque",
        "historical": False,
        "actor_role": "sender",
    }


class WorkerEntrypointTests(unittest.TestCase):
    def request(self, batch, *, target_ref="qq-account-opaque"):
        return WorkerRequest(
            request_id="worker-entry-001",
            adapter_id="surfcore.qq.readonly",
            adapter_version="0.1.0",
            operation="observe_batch",
            target_ref=target_ref,
            modalities=("text",),
            input_payload=json.dumps(batch, separators=(",", ":")).encode("utf-8"),
        )

    def batch(self, records=None, **changes):
        value = {
            "schema_version": 1,
            "stream_ref": "qq-account-opaque",
            "after_cursor": 0,
            "next_cursor": 42 if records else 0,
            "records": [qq_record()] if records is None else records,
        }
        value.update(changes)
        return value

    def test_fixed_dispatch_returns_v4_evidence_and_cursor_metadata(self):
        request = self.request(self.batch())
        response = decode_response(
            process_one_request(encode_request(request), "surfcore_qq_batch")
        )
        self.assertEqual(response.status, "complete")
        self.assertEqual(len(response.evidence), 1)
        evidence = response.evidence[0]
        self.assertEqual(evidence["context_kind"], "group")
        self.assertEqual(evidence["actor_ref"], "qq-sender-opaque")
        self.assertEqual(evidence["source_sequence"], 42)
        self.assertIs(evidence["historical"], False)
        self.assertIs(evidence["untrusted"], True)
        self.assertEqual(dict(response.result_metadata), {
            "stream_ref": "qq-account-opaque",
            "after_cursor": 0,
            "proposed_cursor": 42,
        })

    def test_empty_batch_is_unavailable_but_preserves_cursor_checkpoint(self):
        batch = self.batch(records=[], next_cursor=42)
        response = decode_response(
            process_one_request(encode_request(self.request(batch)), "surfcore_qq_batch")
        )
        self.assertEqual(response.status, "unavailable")
        self.assertEqual(response.evidence, ())
        self.assertEqual(dict(response.result_metadata)["proposed_cursor"], 42)

    def test_invalid_payload_is_returned_as_stable_failed_response(self):
        batch = self.batch()
        batch["records"][0]["historical"] = "false"
        response = decode_response(
            process_one_request(encode_request(self.request(batch)), "surfcore_qq_batch")
        )
        self.assertEqual(response.status, "failed")
        self.assertEqual(response.error_code, "invalid_adapter_input")
        self.assertEqual(response.evidence, ())

    def test_target_mismatch_fails_closed(self):
        response = decode_response(
            process_one_request(
                encode_request(self.request(self.batch(), target_ref="other-stream")),
                "surfcore_qq_batch",
            )
        )
        self.assertEqual(response.status, "failed")
        self.assertEqual(response.error_code, "invalid_adapter_input")

    def test_dispatch_key_and_request_binding_are_not_dynamic(self):
        request = self.request(self.batch())
        with self.assertRaisesRegex(WorkerProtocolError, "not allowlisted"):
            process_one_request(encode_request(request), "adapters.module:run")
        wrong_binding = WorkerRequest(
            request_id=request.request_id,
            adapter_id="other.adapter",
            adapter_version=request.adapter_version,
            operation=request.operation,
            target_ref=request.target_ref,
            modalities=request.modalities,
            input_payload=request.input_payload,
        )
        response = decode_response(
            process_one_request(encode_request(wrong_binding), "surfcore_qq_batch")
        )
        self.assertEqual(response.status, "failed")

    def test_duplicate_json_keys_are_rejected(self):
        request = WorkerRequest(
            request_id="worker-entry-duplicate",
            adapter_id="surfcore.qq.readonly",
            adapter_version="0.1.0",
            operation="observe_batch",
            target_ref="qq-account-opaque",
            modalities=("text",),
            input_payload=b'{"schema_version":1,"schema_version":1}',
        )
        response = decode_response(
            process_one_request(encode_request(request), "surfcore_qq_batch")
        )
        self.assertEqual(response.status, "failed")


if __name__ == "__main__":
    unittest.main()
