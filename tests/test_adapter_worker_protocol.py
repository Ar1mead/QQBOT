import hashlib
import unittest

from adapters.worker_protocol import (
    MAX_MESSAGE_BYTES,
    WorkerProtocolError,
    WorkerRequest,
    WorkerResponse,
    decode_request,
    decode_response,
    encode_request,
    encode_response,
    response_to_observation_result,
    validate_response_for_request,
)


class WorkerProtocolTests(unittest.TestCase):
    def setUp(self):
        self.request = WorkerRequest(
            request_id="req-001",
            adapter_id="bilibili.read_only",
            adapter_version="0.1.0",
            operation="observe_video",
            target_ref="BV1xx411c7mD",
            modalities=("text",),
        )

    def test_request_round_trip_is_deterministic(self):
        encoded = encode_request(self.request)
        self.assertEqual(encode_request(decode_request(encoded)), encoded)
        self.assertEqual(decode_request(encoded), self.request)

    def test_request_rejects_unknown_fields_and_wrong_message_type(self):
        raw = encode_request(self.request).decode("utf-8")
        with self.assertRaisesRegex(WorkerProtocolError, "invalid message fields"):
            decode_request(raw[:-1] + ',"extra":true}')
        with self.assertRaisesRegex(WorkerProtocolError, "unexpected worker message type"):
            decode_request(raw.replace("observation_request", "execute_command"))

    def test_request_rejects_duplicate_json_keys(self):
        raw = (
            '{"protocol_version":1,"message_type":"observation_request",'
            '"request_id":"a","request_id":"b","adapter_id":"x",'
            '"adapter_version":"1","operation":"observe","target_ref":"BV1xx411c7mD",'
            '"modalities":["text"]}'
        )
        with self.assertRaisesRegex(WorkerProtocolError, "duplicate JSON key"):
            decode_request(raw)

    def test_request_rejects_unsupported_versions_and_duplicate_modalities(self):
        with self.assertRaisesRegex(WorkerProtocolError, "unsupported"):
            WorkerRequest("r", "a", "1", "observe", "BV1xx411c7mD", ("text",), True)
        with self.assertRaisesRegex(WorkerProtocolError, "duplicates"):
            WorkerRequest("r", "a", "1", "observe", "BV1xx411c7mD", ("text", "text"))

    def test_request_rejects_oversized_messages(self):
        with self.assertRaisesRegex(WorkerProtocolError, "maximum size"):
            decode_request(b" " * (MAX_MESSAGE_BYTES + 1))

    def test_response_round_trip_and_request_binding(self):
        response = WorkerResponse(
            request_id=self.request.request_id,
            adapter_id=self.request.adapter_id,
            adapter_version=self.request.adapter_version,
            status="complete",
            evidence=({"observation_id": "obs-1"},),
        )
        encoded = encode_response(response)
        decoded = decode_response(encoded)
        self.assertEqual(encode_response(decoded), encoded)
        validate_response_for_request(decoded, self.request)

    def test_response_rejects_mismatched_request_or_adapter_identity(self):
        response = WorkerResponse(
            request_id="different",
            adapter_id=self.request.adapter_id,
            adapter_version=self.request.adapter_version,
            status="complete",
            evidence=({"observation_id": "obs-1"},),
        )
        with self.assertRaisesRegex(WorkerProtocolError, "request_id"):
            validate_response_for_request(response, self.request)
        wrong_adapter = WorkerResponse(
            request_id=self.request.request_id,
            adapter_id="other",
            adapter_version="0.1.0",
            status="complete",
            evidence=({"observation_id": "obs-1"},),
        )
        with self.assertRaisesRegex(WorkerProtocolError, "adapter identity"):
            validate_response_for_request(wrong_adapter, self.request)

    def test_response_status_shape_is_enforced(self):
        with self.assertRaisesRegex(WorkerProtocolError, "complete response"):
            WorkerResponse("r", "a", "1", "complete")
        with self.assertRaisesRegex(WorkerProtocolError, "failed response"):
            WorkerResponse("r", "a", "1", "failed")
        with self.assertRaisesRegex(WorkerProtocolError, "unavailable response"):
            WorkerResponse("r", "a", "1", "unavailable", evidence=({"x": 1},))

    def test_decoder_rejects_nonstandard_json_constants(self):
        raw = (
            '{"protocol_version":1,"message_type":"observation_response",'
            '"request_id":"r","adapter_id":"a","adapter_version":"1",'
            '"status":"unavailable","evidence":[],"warnings":[],"error_code":NaN}'
        )
        with self.assertRaisesRegex(WorkerProtocolError, "non-standard JSON constant"):
            decode_response(raw)

    def make_wire_evidence(self):
        content = "untrusted worker observation"
        return {
            "observation_id": "obs-1",
            "adapter_id": self.request.adapter_id,
            "adapter_version": self.request.adapter_version,
            "platform": "bilibili",
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

    def test_response_reconstructs_and_validates_evidence_before_csd(self):
        response = WorkerResponse(
            request_id=self.request.request_id,
            adapter_id=self.request.adapter_id,
            adapter_version=self.request.adapter_version,
            status="complete",
            evidence=(self.make_wire_evidence(),),
        )
        response = decode_response(encode_response(response))
        result = response_to_observation_result(response, self.request)
        self.assertEqual(result.status.value, "complete")
        self.assertEqual(len(result.evidence), 1)
        self.assertIs(result.evidence[0].untrusted, True)

    def test_response_rejects_evidence_outside_requested_identity_or_modality(self):
        for field, value in (("adapter_id", "spoofed"), ("modality", "audio")):
            evidence = self.make_wire_evidence()
            evidence[field] = value
            response = WorkerResponse(
                request_id=self.request.request_id,
                adapter_id=self.request.adapter_id,
                adapter_version=self.request.adapter_version,
                status="complete",
                evidence=(evidence,),
            )
            with self.subTest(field=field):
                with self.assertRaises(WorkerProtocolError):
                    response_to_observation_result(response, self.request)

    def test_response_rejects_tampered_digest_and_trusted_evidence(self):
        for field, value in (("content_digest", "sha256:" + "0" * 64), ("untrusted", False)):
            evidence = self.make_wire_evidence()
            evidence[field] = value
            response = WorkerResponse(
                request_id=self.request.request_id,
                adapter_id=self.request.adapter_id,
                adapter_version=self.request.adapter_version,
                status="complete",
                evidence=(evidence,),
            )
            with self.subTest(field=field):
                with self.assertRaisesRegex(WorkerProtocolError, "invalid observation evidence"):
                    response_to_observation_result(response, self.request)

    def test_response_rejects_unknown_fields(self):
        raw = (
            '{"protocol_version":1,"message_type":"observation_response",'
            '"request_id":"r","adapter_id":"a","adapter_version":"1",'
            '"status":"unavailable","evidence":[],"warnings":[],"error_code":null,'
            '"shell_command":"whoami"}'
        )
        with self.assertRaisesRegex(WorkerProtocolError, "invalid message fields"):
            decode_response(raw)


if __name__ == "__main__":
    unittest.main()
