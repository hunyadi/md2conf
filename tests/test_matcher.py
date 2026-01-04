"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
import os.path
import unittest
from pathlib import Path
from random import shuffle

from md2conf.matcher import Entry, Matcher, MatcherOptions
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestMatcher(TypedTestCase):
    def test_ordering(self) -> None:
        ordered = [
            Entry("0.md", True),
            Entry("9.md", True),
            Entry("A.md", True),
            Entry("a.md", True),
            Entry("Z.md", True),
            Entry("z.md", True),
            Entry("0.md", False),
            Entry("9.md", False),
            Entry("A.md", False),
            Entry("a.md", False),
            Entry("Z.md", False),
            Entry("z.md", False),
        ]
        unordered: list[Entry] = []
        unordered.extend(ordered)
        shuffle(unordered)
        self.assertNotEqual(ordered, unordered)
        self.assertEqual(ordered, sorted(unordered))

    def test_extension(self) -> None:
        directory = Path(os.path.dirname(__file__))
        expected = sorted(Entry(entry.name, entry.is_dir()) for entry in os.scandir(directory) if entry.is_dir() or entry.name.endswith(".py"))

        options = MatcherOptions(".mdignore", ".py")
        matcher = Matcher(options, directory)
        actual = matcher.listing(directory)

        self.assertEqual(expected, actual)

    def test_nested(self) -> None:
        directory = Path(os.path.dirname(__file__))
        options = MatcherOptions("relative.txt")
        with self.assertRaises(ValueError):
            Matcher(options, directory)

    def test_rules(self) -> None:
        directory = Path(os.path.dirname(__file__)) / "source"
        expected = sorted(Entry(entry.name, entry.is_dir()) for entry in os.scandir(directory) if entry.is_dir() or entry.name.endswith(".md"))
        expected.remove(Entry("docs", True))
        expected.remove(Entry("ignore.md", False))
        expected.remove(Entry("anchors.md", False))
        expected.remove(Entry("missing.md", False))
        expected.remove(Entry("title.md", False))

        options = MatcherOptions(".mdignore", ".md")
        matcher = Matcher(options, directory)
        actual = matcher.listing(directory)

        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
