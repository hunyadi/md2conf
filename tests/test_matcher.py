"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
import os.path
import unittest
from pathlib import Path

from md2conf.matcher import Entry, Matcher, MatcherOptions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestMatcher(unittest.TestCase):
    def test_extension(self) -> None:
        directory = Path(os.path.dirname(__file__))
        expected = [
            Entry(entry.name, entry.is_dir())
            for entry in os.scandir(directory)
            if entry.is_dir() or entry.name.endswith(".py")
        ]

        options = MatcherOptions(".mdignore", ".py")
        matcher = Matcher(options, directory)
        actual = matcher.scandir(directory)

        self.assertCountEqual(expected, actual)

    def test_rules(self) -> None:
        directory = Path(os.path.dirname(__file__)) / "source"
        expected = [
            Entry(entry.name, entry.is_dir())
            for entry in os.scandir(directory)
            if entry.name.endswith(".md")
        ]
        expected.remove(Entry("ignore.md", False))
        expected.remove(Entry("anchors.md", False))
        expected.remove(Entry("missing.md", False))
        expected.remove(Entry("title.md", False))

        options = MatcherOptions(".mdignore", ".md")
        matcher = Matcher(options, directory)
        actual = matcher.scandir(directory)

        self.assertCountEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
