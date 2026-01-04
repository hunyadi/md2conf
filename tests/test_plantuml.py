"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
import unittest
import xml.etree.ElementTree as ET

from md2conf.plantuml.render import has_plantuml, render_diagram
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

PLANTUML_SOURCE = """
@startuml
abstract class Animal {
  +name: String
  +age: int
  +makeSound(): void
}

class Dog {
  +breed: String
  +bark(): void
  +makeSound(): void
}

class Cat {
  +color: String
  +meow(): void
  +makeSound(): void
}

Animal <|-- Dog
Animal <|-- Cat
@enduml
"""


@unittest.skipUnless(has_plantuml(), "plantuml is not available")
@unittest.skipUnless(os.getenv("TEST_PLANTUML"), "plantuml tests are disabled")
class TestPlantumlRendering(TypedTestCase):
    def test_render_simple_svg(self) -> None:
        svg = render_diagram(PLANTUML_SOURCE, output_format="svg")
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.lower() == "svg" or root.tag.endswith("}svg"))

    def test_render_simple_png(self) -> None:
        png = render_diagram(PLANTUML_SOURCE)
        self.assertIn(b"PNG", png)


if __name__ == "__main__":
    unittest.main()
