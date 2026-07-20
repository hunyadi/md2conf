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
        matcher = Matcher(directory, options=options)
        actual = matcher.listing(directory)

        self.assertEqual(expected, actual)

    def test_nested(self) -> None:
        tests_dir = Path(os.path.dirname(__file__))
        source_dir = tests_dir / "source"

        options = MatcherOptions("relative.txt")
        root_matcher = Matcher(tests_dir, options=options)
        sub_matcher = Matcher(source_dir, parent=root_matcher)

        # `source/emoji.md` pattern from `relative.txt` is anchored to `tests/`: excludes `emoji.md` inside `source/`
        self.assertTrue(sub_matcher.is_excluded(Entry("emoji.md", False)))

        # the pattern must not exclude `emoji.md` at the `tests/` root level
        self.assertFalse(root_matcher.is_excluded(Entry("emoji.md", False)))

    def test_rules(self) -> None:
        directory = Path(os.path.dirname(__file__)) / "source"
        expected = sorted(Entry(entry.name, entry.is_dir()) for entry in os.scandir(directory) if entry.is_dir() or entry.name.endswith(".md"))
        expected.remove(Entry("docs", True))
        expected.remove(Entry("ignore.md", False))
        expected.remove(Entry("anchors.md", False))
        expected.remove(Entry("extension.md", False))
        expected.remove(Entry("missing.md", False))
        expected.remove(Entry("title.md", False))

        options = MatcherOptions(".mdignore", ".md")
        matcher = Matcher(directory, options=options)
        actual = matcher.listing(directory)

        self.assertEqual(expected, actual)

    def test_cascading(self) -> None:
        tests_dir = Path(os.path.dirname(__file__))
        source_dir = tests_dir / "source"

        # root matcher loads `cascading.txt` from `tests/`
        options = MatcherOptions("cascading.txt")
        root_matcher = Matcher(tests_dir, options=options)

        # child matcher inherits parent's options and `cascading.txt` rules,
        # and also loads `cascading.txt` from `source/` (local rules)
        sub_matcher = Matcher(source_dir, parent=root_matcher)

        # nested path pattern from root: `source/skip.md` must be excluded
        self.assertTrue(sub_matcher.is_excluded(Entry("skip.md", False)))

        # flat pattern from root: `excluded.md` excluded at both levels
        self.assertTrue(root_matcher.is_excluded(Entry("excluded.md", False)))
        self.assertTrue(sub_matcher.is_excluded(Entry("excluded.md", False)))

        # broad pattern from root: `*.log` files are excluded at both levels
        self.assertTrue(root_matcher.is_excluded(Entry("error.log", False)))
        self.assertTrue(sub_matcher.is_excluded(Entry("error.log", False)))

        # negation rule from root: `!important.log` un-ignores the file
        self.assertFalse(root_matcher.is_excluded(Entry("important.log", False)))
        self.assertFalse(sub_matcher.is_excluded(Entry("important.log", False)))

        # local pattern from `source/cascading.txt` only
        self.assertTrue(sub_matcher.is_excluded(Entry("local.md", False)))
        self.assertFalse(root_matcher.is_excluded(Entry("local.md", False)))

        # broad pattern from source: `*.bak` files excluded only at source level
        self.assertTrue(sub_matcher.is_excluded(Entry("temp.bak", False)))
        self.assertFalse(root_matcher.is_excluded(Entry("temp.bak", False)))

        # negation rule from source: `!keep.bak` un-ignores the file at source level
        self.assertFalse(sub_matcher.is_excluded(Entry("keep.bak", False)))
        self.assertFalse(root_matcher.is_excluded(Entry("keep.bak", False)))

        # unmatched file must not be excluded
        self.assertFalse(sub_matcher.is_excluded(Entry("keep.md", False)))


if __name__ == "__main__":
    unittest.main()
