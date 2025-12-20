"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest
from pathlib import Path

from cattrs import BaseValidationError

from md2conf.extra import override
from md2conf.scanner import MermaidScanner, Scanner
from tests.utility import TypedTestCase

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
    fixtures_dir: Path

    @override
    def setUp(self) -> None:
        self.maxDiff = 1024

        test_dir = Path(__file__).parent
        self.fixtures_dir = test_dir / "fixtures"

    def test_tag(self) -> None:
        document = Scanner().read(self.fixtures_dir / "scanner_test_tag.md")
        props = document.properties
        self.assertIsNotNone(props.page_id)
        self.assertIsNone(props.space_key)
        self.assertIsNone(props.title)

    def test_json_frontmatter(self) -> None:
        fixture_path = self.fixtures_dir / "scanner_test_json_frontmatter.md"
        document = Scanner().read(fixture_path)
        props = document.properties
        self.assertEqual(props.page_id, "1966122")
        self.assertEqual(props.space_key, "~hunyadi")
        self.assertEqual(props.title, "🏠 Markdown parent page")

    def test_yaml_frontmatter(self) -> None:
        fixture_path = self.fixtures_dir / "scanner_test_yaml_frontmatter.md"
        document = Scanner().read(fixture_path)
        props = document.properties
        self.assertIsNotNone(props.page_id)
        self.assertIsNone(props.space_key)
        self.assertEqual(props.generated_by, "This page has been generated with md2conf.")
        self.assertEqual(props.title, "Markdown example document")
        self.assertEqual(props.tags, ["markdown", "confluence", "md", "wiki"])

    def test_mermaid_frontmatter(self) -> None:
        properties = MermaidScanner().read(mermaid_front_matter)
        if properties.config is None:
            self.fail()
        self.assertEqual(properties.config.scale, 1)

    def test_mermaid_no_frontmatter(self) -> None:
        properties = MermaidScanner().read(mermaid_no_front_matter)
        self.assertIsNone(properties.config)

    def test_mermaid_malformed_frontmatter(self) -> None:
        with self.assertRaises(BaseValidationError):
            MermaidScanner().read(mermaid_malformed_front_matter)


if __name__ == "__main__":
    unittest.main()
