"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest
from pathlib import Path

from md2conf.scanner import Scanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestScanner(unittest.TestCase):
    sample_dir: Path

    def setUp(self) -> None:
        self.maxDiff = 1024

        test_dir = Path(__file__).parent
        parent_dir = test_dir.parent

        self.sample_dir = parent_dir / "sample"

    def test_tag(self) -> None:
        document = Scanner().read(self.sample_dir / "index.md")
        self.assertIsNotNone(document.page_id)
        self.assertIsNone(document.space_key)
        self.assertIsNone(document.title)

    def test_frontmatter(self) -> None:
        document = Scanner().read(self.sample_dir / "sibling.md")
        self.assertIsNotNone(document.page_id)
        self.assertIsNone(document.space_key)
        self.assertEqual(document.title, "Markdown example document")


if __name__ == "__main__":
    unittest.main()
