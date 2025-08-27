"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest
from pathlib import Path

from md2conf.extra import override
from md2conf.scanner import Scanner
from tests.utility import TypedTestCase
from strong_typing.deserializer import JsonTypeError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

mermaid_front_matter = """---
title: Tiny flow diagram
config:
  scale: 1
---
flowchart LR
    A[Component A] --> B[Component B]
    B --> C[Component C]
"""
mermaid_no_front_matter = """flowchart LR
    A[Component A] --> B[Component B]
    B --> C[Component C]
"""
mermaid_malformed_front_matter = """---
title: Tiny flow diagram
config:
  scale: 1.2.5
---
flowchart LR
    A[Component A] --> B[Component B]
    B --> C[Component C]
"""

class TestScanner(TypedTestCase):
    sample_dir: Path

    @override
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

    def test_json_frontmatter(self) -> None:
        document = Scanner().read(self.sample_dir / "parent" / "index.md")
        self.assertEqual(document.page_id, "1966122")
        self.assertEqual(document.space_key, "~hunyadi")
        self.assertEqual(document.title, "🏠 Markdown parent page")

    def test_yaml_frontmatter(self) -> None:
        document = Scanner().read(self.sample_dir / "sibling.md")
        self.assertIsNotNone(document.page_id)
        self.assertIsNone(document.space_key)
        self.assertEqual(document.generated_by, "This page has been generated with md2conf.")
        self.assertEqual(document.title, "Markdown example document")
        self.assertEqual(document.tags, ["markdown", "confluence", "md", "wiki"])

    def test_mermaid_frontmatter(self) -> None:
        properties = Scanner().fetch_mermaid_properties(mermaid_front_matter)
        self.assertEqual(properties.config.scale, 1)

    def test_mermaid_no_frontmatter(self) -> None:
        properties = Scanner().fetch_mermaid_properties(mermaid_no_front_matter)
        self.assertIsNone(properties.config.scale, "No front-matter shall build a dataclass structure and return `None` to the 'scale' property.")

    def test_mermaid_malformed_frontmatter(self) -> None:
        with self.assertRaises(JsonTypeError):
            Scanner().fetch_mermaid_properties(mermaid_malformed_front_matter)

if __name__ == "__main__":
    unittest.main()
