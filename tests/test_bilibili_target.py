import unittest

from adapters.contracts.observation import AdapterManifest, Capability, CapabilityMode
from adapters.platforms.bilibili import BILIBILI_MANIFEST, parse_bilibili_target
from adapters.policy import require_observation_only


class BilibiliTargetTests(unittest.TestCase):
    def test_bilibili_manifest_declares_observation_only_target_validation(self):
        require_observation_only(BILIBILI_MANIFEST)
        self.assertEqual(BILIBILI_MANIFEST.platform, "bilibili")
        self.assertEqual([c.name for c in BILIBILI_MANIFEST.capabilities], ["validate_video_target"])
        self.assertTrue(BILIBILI_MANIFEST.observation_only)

    def test_policy_rejects_presentation_and_side_effect_capabilities(self):
        for mode in (CapabilityMode.PRESENT, CapabilityMode.SIDE_EFFECT):
            manifest = AdapterManifest(
                adapter_id="test.adapter", adapter_version="1", platform="test",
                capabilities=(Capability(name="forbidden_action", mode=mode, description="not allowed"),),
            )
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(PermissionError, "restricted to observation"):
                    require_observation_only(manifest)
    def test_accepts_canonical_bvid(self):
        target = parse_bilibili_target("BV1EPnG6DEJC")
        self.assertEqual(target.bvid, "BV1EPnG6DEJC")

    def test_trims_outer_whitespace(self):
        self.assertEqual(parse_bilibili_target(" BV1EPnG6DEJC ").bvid, "BV1EPnG6DEJC")

    def test_rejects_arbitrary_urls_and_short_links(self):
        for value in (
            "https://example.com/video",
            "https://127.0.0.1/admin",
            "https://b23.tv/abc123",
            "file:///C:/Windows/win.ini",
            "C:\\Windows\\win.ini",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "only canonical BV identifiers"):
                    parse_bilibili_target(value)

    def test_rejects_malformed_bvid(self):
        for value in ("BV1", "av123", "", "BV1EPnG6DEJC?x=1"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_bilibili_target(value)


if __name__ == "__main__":
    unittest.main()
