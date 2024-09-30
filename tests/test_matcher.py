import logging
import os
import os.path
import unittest
from pathlib import Path

from md2conf.matcher import Matcher, MatcherOptions

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestMatcher(unittest.TestCase):
    def test_extension(self) -> None:
        directory = Path(os.path.dirname(__file__))
        expected = [
            entry.name for entry in os.scandir(directory) if entry.name.endswith(".py")
        ]

        options = MatcherOptions(".mdignore", ".py")
        matcher = Matcher(options, directory)
        actual = matcher.scandir(directory)

        self.assertCountEqual(expected, actual)

    def test_rules(self) -> None:
        directory = Path(os.path.dirname(__file__)) / "source"
        expected = [
            entry.name for entry in os.scandir(directory) if entry.name.endswith(".md")
        ]
        expected.remove("ignore.md")

        options = MatcherOptions(".mdignore", ".md")
        matcher = Matcher(options, directory)
        actual = matcher.scandir(directory)

        self.assertCountEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
