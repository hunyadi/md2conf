"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from md2conf.plantuml import PlantUMLConfigProperties, has_plantuml, render_diagram
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

PLANTUML_WITH_INCLUDE = """
@startuml
!include common.puml
Alice -> Bob: Hello
@enduml
"""

COMMON_PUML = """
!define PRIMARY_COLOR #FF6B6B
skinparam backgroundColor white
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

    def test_render_with_include_path(self) -> None:
        """Test that include_path enables !include directives"""
        with tempfile.TemporaryDirectory() as tmpdir:
            common_file = Path(tmpdir) / "common.puml"
            common_file.write_text(COMMON_PUML)

            config = PlantUMLConfigProperties(include_path=tmpdir)
            svg = render_diagram(PLANTUML_WITH_INCLUDE, output_format="svg", config=config)
            root = ET.fromstring(svg)
            self.assertTrue(root.tag.lower() == "svg" or root.tag.endswith("}svg"))

    def test_render_with_include_file(self) -> None:
        """Test that include_file pre-includes content"""
        with tempfile.TemporaryDirectory() as tmpdir:
            theme_file = Path(tmpdir) / "theme.puml"
            theme_file.write_text(COMMON_PUML)

            config = PlantUMLConfigProperties(include_path=tmpdir, include_file="theme.puml")
            svg = render_diagram(PLANTUML_SOURCE, output_format="svg", config=config)
            root = ET.fromstring(svg)
            self.assertTrue(root.tag.lower() == "svg" or root.tag.endswith("}svg"))

    def test_render_with_theme(self) -> None:
        """Test that theme applies built-in PlantUML theme"""
        config = PlantUMLConfigProperties(theme="cerulean")
        svg = render_diagram(PLANTUML_SOURCE, output_format="svg", config=config)
        root = ET.fromstring(svg)
        self.assertTrue(root.tag.lower() == "svg" or root.tag.endswith("}svg"))


if __name__ == "__main__":
    unittest.main()
