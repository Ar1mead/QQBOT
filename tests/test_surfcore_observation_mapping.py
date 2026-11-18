from __future__ import annotations

from copy import deepcopy
import unittest

from adapters.contracts.observation import CapabilityMode, ContentOrigin
from adapters.platforms.surfcore import (
    bilibili_manifest,
    map_surfcore_record,
    map_surfcore_record_to_csd_event,
    qq_manifest,
)


def record(platform="qq", **overrides):
    if platform == "qq":
        data = {
            "schema_version": 1,
            "platform": "qq",
            "record_id": "message:987654321",
            "external_ref": "987654321",
            "observation_kind": "qq.message.incoming",
            "content_origin": "source_provided",
            "modality": "text",
            "content": "A person asked whether the bridge is connected.",
            "source_ref": "surfcore://qq/message/987654321",
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
                "notes": ["Synthetic fixture; message content is untrusted."],
            },
            "account_ref": "qq-account-opaque",
        }
    else:
        data = {
            "schema_version": 1,
            "platform": "bilibili",
            "record_id": "BV1EPnG6DEJC:subtitle:zh-CN",
            "external_ref": "BV1EPnG6DEJC",
            "observation_kind": "bilibili.video.subtitle",
            "content_origin": "source_provided",
            "modality": "text",
            "content": "The subtitle track contains timestamped dialogue.",
            "source_ref": "surfcore://bilibili/BV1EPnG6DEJC/subtitle/zh-CN",
            "observed_at": "2026-11-18T08:00:00+00:00",
            "received_at": "2026-11-18T08:00:02+00:00",
            "extraction_method": "platform_subtitle",
            "coverage": {
                "modality": "text",
                "extraction_method": "platform_subtitle",
                "complete": False,
                "start_ms": 0,
                "end_ms": 120000,
                "missing_ranges_ms": [[45000, 50000]],
                "notes": ["One interval was unavailable; this is not complete video perception."],
            },
            "source_artifact_ref": "surfcore-artifact://bilibili/BV1EPnG6DEJC/subtitle/zh-CN",
            "account_ref": "bili-account-opaque",
        }
    data.update(overrides)
    return data


class SurfCoreMappingTests(unittest.TestCase):
    def test_qq_manifest_is_observation_only(self):
        manifest = qq_manifest()
        self.assertEqual(manifest.platform, "qq")
        self.assertEqual(manifest.adapter_id, "surfcore.qq.readonly")
        self.assertTrue(manifest.observation_only)
        self.assertEqual(manifest.capabilities[0].mode, CapabilityMode.OBSERVE)
        self.assertEqual(manifest.capabilities[0].name, "observe:text")

    def test_bilibili_manifest_is_observation_only(self):
        manifest = bilibili_manifest()
        self.assertEqual(manifest.platform, "bilibili")
        self.assertTrue(manifest.observation_only)
        self.assertEqual(manifest.capabilities[0].mode, CapabilityMode.OBSERVE)

    def test_qq_message_maps_to_untrusted_stable_evidence(self):
        source = record()
        first = map_surfcore_record(source)
        second = map_surfcore_record(source)
        self.assertEqual(first, second)
        self.assertEqual(first.platform, "qq")
        self.assertEqual(first.observation_kind, "qq.message.incoming")
        self.assertEqual(first.content_origin, ContentOrigin.SOURCE_PROVIDED)
        self.assertIs(first.untrusted, True)
        self.assertEqual(first.account_ref, "qq-account-opaque")

    def test_historical_qq_message_remains_explicit(self):
        mapped = map_surfcore_record(record(observation_kind="qq.message.incoming.historical"))
        self.assertEqual(mapped.observation_kind, "qq.message.incoming.historical")

    def test_bilibili_subtitle_preserves_partial_coverage(self):
        mapped = map_surfcore_record(record("bilibili"))
        self.assertFalse(mapped.coverage.complete)
        self.assertEqual(mapped.coverage.missing_ranges_ms, ((45000, 50000),))
        self.assertEqual(mapped.external_ref, "BV1EPnG6DEJC")
        self.assertIs(mapped.untrusted, True)

    def test_mapping_to_csd_event_has_stable_identity_and_untrusted_payload(self):
        source = record("bilibili")
        first = map_surfcore_record_to_csd_event(source)
        second = map_surfcore_record_to_csd_event(source)
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(dict(first.payload), dict(second.payload))
        self.assertEqual(first.event_type, "experience.observation_recorded.v2")
        self.assertIs(first.payload["untrusted"], True)
        self.assertEqual(first.payload["coverage"]["missing_ranges_ms"], [[45000, 50000]])

    def test_unknown_fields_fail_closed(self):
        source = record()
        source["console_token"] = "must-never-be-forwarded"
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            map_surfcore_record(source)

    def test_schema_version_and_platform_kind_are_checked(self):
        with self.assertRaisesRegex(ValueError, "schema_version"):
            map_surfcore_record(record(schema_version=2))
        with self.assertRaisesRegex(ValueError, "not allowed"):
            map_surfcore_record(record(observation_kind="bilibili.video.comment"))

    def test_non_text_modality_is_not_silently_flattened(self):
        with self.assertRaisesRegex(ValueError, "text modality only"):
            map_surfcore_record(record(modality="image"))

    def test_coverage_schema_and_digest_are_validated(self):
        source = record()
        source["coverage"]["unexpected"] = "not allowed"
        with self.assertRaisesRegex(ValueError, "coverage fields"):
            map_surfcore_record(source)
        source = record(content="Changed after source digest was supposed to be fixed.")
        mapped = map_surfcore_record(source)
        self.assertTrue(mapped.content_digest.startswith("sha256:"))

    def test_csd_event_ingestion_is_idempotent_for_repeated_record(self):
        first = map_surfcore_record_to_csd_event(record())
        second = map_surfcore_record_to_csd_event(record())
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(dict(first.payload), dict(second.payload))


if __name__ == "__main__":
    unittest.main()
