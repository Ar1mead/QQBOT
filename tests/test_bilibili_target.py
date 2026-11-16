import unittest

from adapters.platforms.bilibili import parse_bilibili_target


class BilibiliTargetTests(unittest.TestCase):
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
