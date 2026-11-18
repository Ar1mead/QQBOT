import unittest

from adapters.platforms.surfcore.worker_result import (
    SurfCoreQQResultMetadata,
    validate_surfcore_qq_result_metadata,
)


class SurfCoreQQResultMetadataTests(unittest.TestCase):
    def setUp(self):
        self.metadata = (
            ("stream_ref", "opaque-stream-1"),
            ("after_cursor", 12),
            ("proposed_cursor", 19),
        )

    def validate(self, metadata=None, **overrides):
        values = {
            "expected_stream_ref": "opaque-stream-1",
            "expected_after_cursor": 12,
        }
        values.update(overrides)
        return validate_surfcore_qq_result_metadata(
            self.metadata if metadata is None else metadata,
            **values,
        )

    def test_accepts_exact_metadata_bound_to_host_checkpoint(self):
        result = self.validate()
        self.assertEqual(
            result,
            SurfCoreQQResultMetadata("opaque-stream-1", 12, 19),
        )

    def test_accepts_empty_page_cursor_advance(self):
        result = self.validate((("stream_ref", "opaque-stream-1"), ("after_cursor", 12), ("proposed_cursor", 16)))
        self.assertEqual(result.proposed_cursor, 16)

    def test_rejects_missing_or_unknown_fields(self):
        for metadata in (
            (("stream_ref", "opaque-stream-1"), ("after_cursor", 12)),
            self.metadata + (("unexpected", "value"),),
        ):
            with self.subTest(metadata=metadata):
                with self.assertRaisesRegex(ValueError, "exact schema"):
                    self.validate(metadata)

    def test_rejects_stream_or_checkpoint_mismatch(self):
        with self.assertRaisesRegex(ValueError, "stream_ref"):
            self.validate((("stream_ref", "other"), ("after_cursor", 12), ("proposed_cursor", 19)))
        with self.assertRaisesRegex(ValueError, "host checkpoint"):
            self.validate(expected_after_cursor=11)

    def test_rejects_boolean_negative_and_backward_cursors(self):
        invalid_values = (
            (True, 19),
            (-1, 19),
            (12, True),
            (12, -1),
            (13, 12),
        )
        for after, proposed in invalid_values:
            metadata = (
                ("stream_ref", "opaque-stream-1"),
                ("after_cursor", after),
                ("proposed_cursor", proposed),
            )
            with self.subTest(after=after, proposed=proposed):
                with self.assertRaises(ValueError):
                    self.validate(metadata)

    def test_rejects_duplicate_keys_in_immutable_pairs(self):
        metadata = self.metadata + (("after_cursor", 12),)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.validate(metadata)


if __name__ == "__main__":
    unittest.main()
