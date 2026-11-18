from __future__ import annotations

import unittest

from adapters.contracts.observation import CapabilityMode, ContentOrigin
from adapters.platforms.surfcore import (
    bilibili_manifest,
    map_surfcore_qq_batch,
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
            "cursor": 42,
            "conversation_kind": "group",
            "conversation_ref": "qq-conversation-opaque",
            "sender_ref": "qq-sender-opaque",
            "historical": False,
            "actor_role": "sender",
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
            "context_kind": "video",
            "context_ref": "BV1EPnG6DEJC",
            "actor_ref": "subtitle-contributor-opaque",
            "actor_role": "subtitle_contributor",
            "content_language": "zh-CN",
        }
    data.update(overrides)
    return data


def qq_batch(records, *, after_cursor=0, next_cursor=None):
    if next_cursor is None:
        next_cursor = records[-1]["cursor"] if records else after_cursor
    return {
        "schema_version": 1,
        "stream_ref": "qq-account-opaque",
        "after_cursor": after_cursor,
        "next_cursor": next_cursor,
        "records": records,
    }


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
        self.assertEqual(first.context_kind, "group")
        self.assertEqual(first.context_ref, "qq-conversation-opaque")
        self.assertEqual(first.actor_ref, "qq-sender-opaque")
        self.assertEqual(first.source_sequence, 42)
        self.assertFalse(first.historical)

    def test_qq_private_and_backfilled_provenance_is_preserved(self):
        mapped = map_surfcore_record(record(
            conversation_kind="private",
            conversation_ref="private-thread-opaque",
            sender_ref="owner-opaque",
            historical=True,
        ))
        self.assertEqual(mapped.context_kind, "private")
        self.assertEqual(mapped.context_ref, "private-thread-opaque")
        self.assertEqual(mapped.actor_ref, "owner-opaque")
        self.assertTrue(mapped.historical)
        event = map_surfcore_record_to_csd_event(record(
            conversation_kind="private",
            conversation_ref="private-thread-opaque",
            sender_ref="owner-opaque",
            historical=True,
        ))
        self.assertEqual(event.payload["context_kind"], "private")
        self.assertEqual(event.payload["context_ref"], "private-thread-opaque")
        self.assertEqual(event.payload["actor_ref"], "owner-opaque")
        self.assertEqual(event.payload["source_sequence"], 42)
        self.assertTrue(event.payload["historical"])

    def test_qq_requires_conversation_sender_and_history_provenance(self):
        for field in ("conversation_kind", "conversation_ref", "sender_ref", "historical", "account_ref"):
            source = record()
            del source[field]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "provenance fields"):
                map_surfcore_record(source)
        with self.assertRaisesRegex(ValueError, "conversation_kind"):
            map_surfcore_record(record(conversation_kind="channel"))
        with self.assertRaisesRegex(ValueError, "historical must be boolean"):
            map_surfcore_record(record(historical="false"))

    def test_bilibili_rejects_qq_conversation_provenance(self):
        with self.assertRaisesRegex(ValueError, "QQ-only provenance"):
            map_surfcore_record(record("bilibili", conversation_kind="group"))

    def test_historical_qq_message_remains_explicit(self):
        mapped = map_surfcore_record(record(
            observation_kind="qq.message.incoming.historical",
            historical=True,
        ))
        self.assertEqual(mapped.observation_kind, "qq.message.incoming.historical")
        self.assertTrue(mapped.historical)

    def test_bilibili_subtitle_preserves_video_contributor_and_language(self):
        mapped = map_surfcore_record(record("bilibili"))
        self.assertEqual(mapped.context_kind, "video")
        self.assertEqual(mapped.context_ref, "BV1EPnG6DEJC")
        self.assertEqual(mapped.actor_ref, "subtitle-contributor-opaque")
        self.assertEqual(mapped.actor_role, "subtitle_contributor")
        self.assertEqual(mapped.content_language, "zh-CN")
        event = map_surfcore_record_to_csd_event(record("bilibili"))
        self.assertEqual(event.payload["context_ref"], "BV1EPnG6DEJC")
        self.assertEqual(event.payload["actor_role"], "subtitle_contributor")
        self.assertEqual(event.payload["content_language"], "zh-CN")

    def test_bilibili_comment_preserves_author_and_parent_thread(self):
        source = record(
            "bilibili",
            record_id="BV1EPnG6DEJC:comment:reply-2",
            observation_kind="bilibili.video.comment",
            content="A reply in the discussion.",
            source_ref="surfcore://bilibili/BV1EPnG6DEJC/comment/reply-2",
            extraction_method="platform_comment",
            actor_ref="comment-author-opaque",
            actor_role="comment_author",
            parent_ref="root-comment-opaque",
            content_language=None,
        )
        source["coverage"]["extraction_method"] = "platform_comment"
        mapped = map_surfcore_record(source)
        self.assertEqual(mapped.context_ref, "BV1EPnG6DEJC")
        self.assertEqual(mapped.actor_ref, "comment-author-opaque")
        self.assertEqual(mapped.actor_role, "comment_author")
        self.assertEqual(mapped.parent_ref, "root-comment-opaque")
        self.assertIsNone(mapped.content_language)

    def test_bilibili_danmaku_preserves_sender_role_without_inventing_identity(self):
        source = record(
            "bilibili",
            record_id="BV1EPnG6DEJC:danmaku:100",
            observation_kind="bilibili.video.danmaku",
            content="A danmaku line.",
            source_ref="surfcore://bilibili/BV1EPnG6DEJC/danmaku/100",
            extraction_method="platform_danmaku",
            actor_ref=None,
            actor_role="danmaku_sender",
            content_language=None,
        )
        source["coverage"]["extraction_method"] = "platform_danmaku"
        mapped = map_surfcore_record(source)
        self.assertEqual(mapped.actor_role, "danmaku_sender")
        self.assertIsNone(mapped.actor_ref)

    def test_bilibili_rejects_mismatched_video_actor_language_and_parent_provenance(self):
        cases = (
            ({"context_ref": "BV1OTHER"}, "context_ref must match"),
            ({"actor_role": "comment_author"}, "actor_role must be"),
            ({"content_language": "not a language tag!"}, "BCP 47"),
            ({"parent_ref": "root-comment"}, "only valid for Bilibili comments"),
        )
        for changes, message in cases:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, message):
                map_surfcore_record(record("bilibili", **changes))
        with self.assertRaisesRegex(ValueError, "missing provenance"):
            source = record("bilibili")
            del source["context_ref"]
            map_surfcore_record(source)

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

    def test_coverage_schema_is_validated(self):
        source = record()
        source["coverage"]["unexpected"] = "not allowed"
        with self.assertRaisesRegex(ValueError, "coverage fields"):
            map_surfcore_record(source)

    def test_qq_record_requires_non_negative_integer_cursor(self):
        source = record()
        del source["cursor"]
        with self.assertRaisesRegex(ValueError, "provenance fields"):
            map_surfcore_record(source)
        source["cursor"] = True
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            map_surfcore_record(source)
        source["cursor"] = -1
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            map_surfcore_record(source)

    def test_bilibili_record_rejects_qq_cursor(self):
        with self.assertRaisesRegex(ValueError, "QQ-only provenance"):
            map_surfcore_record(record("bilibili", cursor=1))

    def test_qq_batch_maps_sorted_records_and_proposes_checkpoint(self):
        first = record(cursor=11, record_id="message:11", external_ref="11")
        second = record(cursor=18, record_id="message:18", external_ref="18")
        result = map_surfcore_qq_batch(qq_batch([first, second], after_cursor=10, next_cursor=20))
        self.assertEqual(result.stream_ref, "qq-account-opaque")
        self.assertEqual(result.after_cursor, 10)
        self.assertEqual(result.proposed_cursor, 20)
        self.assertEqual(len(result.events), 2)
        self.assertNotEqual(result.events[0].event_id, result.events[1].event_id)
        self.assertTrue(all(event.payload["untrusted"] for event in result.events))

    def test_same_source_record_id_is_scoped_by_opaque_account_reference(self):
        first = map_surfcore_record_to_csd_event(
            record(record_id="message:shared", account_ref="qq-account-a")
        )
        second = map_surfcore_record_to_csd_event(
            record(record_id="message:shared", account_ref="qq-account-b")
        )
        self.assertNotEqual(first.event_id, second.event_id)

    def test_changed_content_keeps_source_identity_for_csd_conflict_detection(self):
        original = map_surfcore_record_to_csd_event(record())
        changed = map_surfcore_record_to_csd_event(
            record(content="Different payload for the same source message ID.")
        )
        self.assertEqual(original.event_id, changed.event_id)
        self.assertNotEqual(dict(original.payload), dict(changed.payload))

    def test_qq_batch_rejects_record_from_another_account_stream(self):
        source = record(cursor=11, record_id="message:11")
        source["account_ref"] = "different-qq-account"
        with self.assertRaisesRegex(ValueError, "must match batch stream_ref"):
            map_surfcore_qq_batch(qq_batch([source], after_cursor=10, next_cursor=11))

    def test_qq_batch_requires_opaque_stream_reference(self):
        page = qq_batch([], after_cursor=0, next_cursor=0)
        del page["stream_ref"]
        with self.assertRaisesRegex(ValueError, "batch fields"):
            map_surfcore_qq_batch(page)
        page = qq_batch([], after_cursor=0, next_cursor=0)
        page["stream_ref"] = " "
        with self.assertRaisesRegex(ValueError, "stream_ref"):
            map_surfcore_qq_batch(page)

    def test_qq_batch_replay_produces_same_event_ids_and_payloads(self):
        page = qq_batch([record(cursor=11, record_id="message:11", external_ref="11")],
                        after_cursor=10, next_cursor=11)
        first = map_surfcore_qq_batch(page)
        replay = map_surfcore_qq_batch(page)
        self.assertEqual(first.proposed_cursor, replay.proposed_cursor)
        self.assertEqual([e.event_id for e in first.events], [e.event_id for e in replay.events])
        self.assertEqual([dict(e.payload) for e in first.events], [dict(e.payload) for e in replay.events])

    def test_qq_batch_rejects_out_of_order_or_repeated_cursors(self):
        a = record(cursor=12, record_id="message:12")
        b = record(cursor=11, record_id="message:11")
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            map_surfcore_qq_batch(qq_batch([a, b], after_cursor=10, next_cursor=12))
        b["cursor"] = 12
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            map_surfcore_qq_batch(qq_batch([a, b], after_cursor=10, next_cursor=12))

    def test_qq_batch_rejects_duplicate_record_ids_and_cursor_regression(self):
        a = record(cursor=11, record_id="message:same")
        b = record(cursor=12, record_id="message:same")
        with self.assertRaisesRegex(ValueError, "duplicate record_id"):
            map_surfcore_qq_batch(qq_batch([a, b], after_cursor=10, next_cursor=12))
        with self.assertRaisesRegex(ValueError, "cannot move backwards"):
            map_surfcore_qq_batch(qq_batch([], after_cursor=20, next_cursor=19))

    def test_qq_batch_rejects_records_outside_page_bounds_and_foreign_platform(self):
        future = record(cursor=21, record_id="message:21")
        with self.assertRaisesRegex(ValueError, "exceeds batch next_cursor"):
            map_surfcore_qq_batch(qq_batch([future], after_cursor=10, next_cursor=20))
        foreign = record("bilibili")
        with self.assertRaisesRegex(ValueError, "only QQ"):
            map_surfcore_qq_batch(qq_batch([foreign], after_cursor=0, next_cursor=1))

    def test_qq_batch_rejects_missing_or_duplicate_envelope_fields(self):
        page = qq_batch([], after_cursor=0, next_cursor=0)
        page["extra"] = "not allowed"
        with self.assertRaisesRegex(ValueError, "batch fields"):
            map_surfcore_qq_batch(page)

    def test_empty_qq_batch_can_advance_over_filtered_feed_entries(self):
        result = map_surfcore_qq_batch(qq_batch([], after_cursor=10, next_cursor=15))
        self.assertEqual(result.events, ())
        self.assertEqual(result.proposed_cursor, 15)


if __name__ == "__main__":
    unittest.main()
