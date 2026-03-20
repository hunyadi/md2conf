"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
import unittest
import xml.etree.ElementTree as ET

from md2conf.mermaid.render import has_mmdc, render_diagram
from tests.mermaid_tree import render_mermaid_tree
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

MERMAID_SOURCE = """
graph TD
  C{ How to contribute? }
  C --> D[ Reporting bugs ]
  C --> E[ Sharing ideas ]
"""

MERMAID_CLASS_DIAGRAM = """classDiagram
Entity <|-- Product
Entity <|-- Stakeholder
Stakeholder <|-- External
External <|-- Customer
Stakeholder <|-- Internal
Entity <|-- Vendor
Vendor <|-- Store
Entity <|-- Project
"""

MERMAID_TREE_DIAGRAM = """Entity
├── Product
├── Stakeholder
│   ├── External
│   │   └── Customer
│   └── Internal
├── Vendor
│   └── Store
└── Project"""


class TestMermaidTree(TypedTestCase):
    def test_render_simple_svg(self) -> None:
        self.assertEqual(render_mermaid_tree(MERMAID_CLASS_DIAGRAM), MERMAID_TREE_DIAGRAM)


@unittest.skipUnless(has_mmdc(), "mmdc is not available")
@unittest.skipUnless(os.getenv("TEST_MERMAID"), "mermaid tests are disabled")
class TestMermaidRendering(TypedTestCase):
    def test_render_simple_svg(self) -> None:
        svg = render_diagram(MERMAID_SOURCE, output_format="svg")
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.lower() == "svg" or root.tag.endswith("}svg"))

    def test_render_simple_png(self) -> None:
        png = render_diagram(MERMAID_SOURCE)
        self.assertIn(b"PNG", png)


if __name__ == "__main__":
    unittest.main()
