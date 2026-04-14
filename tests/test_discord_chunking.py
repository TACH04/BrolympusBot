"""Tests for Discord-oriented text splitting (no Discord client)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bot.text_chunking import split_text


class TestSplitText(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(split_text("", max_len=50), ("", ""))
        self.assertEqual(split_text("", max_len=2000), ("", ""))

    def test_under_limit_unchanged(self):
        s = "hello world"
        self.assertEqual(split_text(s, max_len=50), (s, ""))

    def test_exact_boundary_no_tail(self):
        s = "x" * 50
        h, t = split_text(s, max_len=50)
        self.assertEqual(h, s)
        self.assertEqual(t, "")

    def test_prefers_newline(self):
        s = "a" * 30 + "\n" + "b" * 40
        h, t = split_text(s, max_len=50)
        self.assertEqual(h, "a" * 30 + "\n")
        self.assertEqual(t, "b" * 40)
        self.assertEqual(h + t, s)

    def test_prefers_space_when_no_newline(self):
        s = "short words " + "x" * 80
        h, t = split_text(s, max_len=40)
        self.assertTrue(h.endswith(" "))
        self.assertLessEqual(len(h), 40)
        self.assertEqual(h + t, s)

    def test_hard_split_long_token(self):
        s = "n" * 100
        h, t = split_text(s, max_len=50)
        self.assertEqual(h, "n" * 50)
        self.assertEqual(t, "n" * 50)
        self.assertEqual(h + t, s)

    def test_iterative_chunks_cover_string(self):
        max_len = 50
        s = "line0\n" + "y" * 120 + "\n" + "tail"
        parts = []
        rest = s
        while rest:
            h, rest = split_text(rest, max_len)
            parts.append(h)
        self.assertEqual("".join(parts), s)
        self.assertTrue(all(len(p) <= max_len for p in parts))


if __name__ == "__main__":
    unittest.main()
