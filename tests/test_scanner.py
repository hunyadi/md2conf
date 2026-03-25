"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest
from pathlib import Path

from cattrs import BaseValidationError

from md2conf.compatibility import override
from md2conf.mermaid.scanner import MermaidScanner
from md2conf.scanner import Scanner
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

id_only = """# Title

Text

<!-- confluence-page-id: 1234 -->
"""

id_space_title = """---
{ "title": "🏠 árvíztűrő tükörfúrógép" }
---

<!-- confluence-page-id: 1234567 -->
<!-- confluence-space-key: ~hunyadi -->

# Title

Text
"""

blank_document_frontmatter = """---
title: "Blank document"
---"""

comment_frontmatter = """<!--
title: 🏠 árvíztűrő tükörfúrógép
-->

Text
"""

mermaid_frontmatter = """---
title: Tiny flow diagram
config:
  scale: 1
---
flowchart LR
    A[Component A] --> B[Component B]
    B --> C[Component C]
"""

mermaid_no_frontmatter = """flowchart LR
    A[Component A] --> B[Component B]
    B --> C[Component C]
"""

mermaid_malformed_frontmatter = """---
title: Tiny flow diagram
config:
  scale: 1.2.5
---
flowchart LR
    A[Component A] --> B[Component B]
    B --> C[Component C]
"""


class TestScanner(TypedTestCase):
    test_dir: Path

    @override
    def setUp(self) -> None:
        self.maxDiff = 1024
        self.test_dir = Path(__file__).parent / "scanner"

    def test_tag(self) -> None:
        document = Scanner().parse(id_only)
        props = document.properties
        self.assertEqual(props.page_id, "1234")
        self.assertIsNone(props.space_key)
        self.assertIsNone(props.title)

    def test_json_frontmatter(self) -> None:
        document = Scanner().parse(id_space_title)
        props = document.properties
        self.assertEqual(props.page_id, "1234567")
        self.assertEqual(props.space_key, "~hunyadi")
        self.assertEqual(props.title, "🏠 árvíztűrő tükörfúrógép")

    def test_blank_document_frontmatter(self) -> None:
        document = Scanner().parse(blank_document_frontmatter)
        props = document.properties
        self.assertEqual(props.title, "Blank document")

    def test_comment_frontmatter(self) -> None:
        document = Scanner().parse(comment_frontmatter)
        props = document.properties
        self.assertEqual(props.title, "🏠 árvíztűrő tükörfúrógép")

    def test_yaml_frontmatter(self) -> None:
        document = Scanner().read(self.test_dir / "frontmatter.md")
        props = document.properties
        self.assertEqual(props.page_id, "19840101")
        self.assertIsNone(props.space_key)
        self.assertEqual(props.generated_by, "This page has been generated with md2conf.")
        self.assertEqual(props.title, "Markdown example document")
        self.assertEqual(props.tags, ["markdown", "confluence", "md", "wiki"])

    def test_mermaid_frontmatter(self) -> None:
        properties = MermaidScanner().read(mermaid_frontmatter)
        if properties.config is None:
            self.fail()
        self.assertEqual(properties.config.scale, 1)

    def test_mermaid_no_frontmatter(self) -> None:
        properties = MermaidScanner().read(mermaid_no_frontmatter)
        self.assertIsNone(properties.config)

    def test_mermaid_malformed_frontmatter(self) -> None:
        with self.assertRaises(BaseValidationError):
            MermaidScanner().read(mermaid_malformed_frontmatter)


if __name__ == "__main__":
    unittest.main()
