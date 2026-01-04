"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest

from md2conf.text import wrap_text
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestText(TypedTestCase):
    def test_basic_wrap(self) -> None:
        text = "This is a simple test sentence that should wrap nicely with no issues whatsoever."
        wrapped = wrap_text(text, line_length=20)
        self.assertTrue(all(0 < len(line.encode("utf-8")) <= 20 for line in wrapped.split("\n")))
        self.assertNotIn("\0", wrapped)

    def test_multibyte_utf8(self) -> None:
        text = "Unicode test: árvíztűrő tükörfúrógép 😊🚀🔥 followed by normal text."
        wrapped = wrap_text(text, line_length=30)
        self.assertTrue(all(0 < len(line.encode("utf-8")) <= 30 for line in wrapped.split("\n")))
        self.assertNotIn("\0", wrapped)

    def test_no_whitespace(self) -> None:
        text = "a-very-long-word-that-exceeds-the-line-length-should-not-break"
        wrapped = wrap_text(text, line_length=1)
        self.assertEqual(wrapped, text)
        self.assertNotIn("\0", wrapped)

    def test_exact_boundary(self) -> None:
        text = "word1 word2 word3 word4 word5"
        wrapped = wrap_text(text, line_length=len(text.encode("utf-8")))
        self.assertEqual(wrapped, text)
        self.assertNotIn("\0", wrapped)

    def test_space_preservation(self) -> None:
        text = "   word1   word2   word3   "
        wrapped = wrap_text(text, line_length=10)
        self.assertIn("\n", wrapped)
        self.assertEqual(wrapped.count("\n"), 2)
        self.assertTrue(all(0 < len(line.encode("utf-8")) <= 10 for line in wrapped.split("\n")))
        self.assertNotIn("\0", wrapped)

    def test_linefeed(self) -> None:
        text = "\nword1\nword2\nword3\nword4\nword5\n"
        wrapped = wrap_text(text, line_length=len(text.encode("utf-8")))
        lines = wrapped.split("\n")
        self.assertEqual(len(lines), 7)
        self.assertEqual(len(lines[0]), 0)
        self.assertEqual(len(lines[3]), 5)
        self.assertEqual(len(lines[6]), 0)
        self.assertNotIn("\0", wrapped)


if __name__ == "__main__":
    unittest.main()
