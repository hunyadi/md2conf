"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import re
import unittest
from pathlib import Path

import lxml.etree as ET

from md2conf.drawio.render import extract_diagram, extract_xml_from_png, extract_xml_from_svg
from md2conf.xml import is_xml_equal
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestDrawio(TypedTestCase):
    def test_bytes(self) -> None:
        image_dir = Path(__file__).parent / "source" / "figure"
        image_file = image_dir / "diagram.drawio.png"
        image = extract_diagram(image_file)
        self.assertGreater(len(image), 0)
        self.assertIsNotNone(re.match(b"^<mxfile[^<>]*><diagram[^<>]*><mxGraphModel[^<>]*>.*</mxGraphModel></diagram></mxfile>$", image))

    def test_xml_from_png(self) -> None:
        image_dir = Path(__file__).parent / "source" / "figure"
        with open(image_dir / "diagram.drawio", "r") as f:
            expected = ET.fromstring(f.read())

        with open(image_dir / "diagram.drawio.png", "rb") as f:
            actual = extract_xml_from_png(f.read())

        self.assertTrue(is_xml_equal(expected, actual))

    def test_xml_from_svg(self) -> None:
        image_dir = Path(__file__).parent / "source" / "figure"
        with open(image_dir / "diagram.drawio", "r") as f:
            expected = ET.fromstring(f.read())

        with open(image_dir / "diagram.drawio.svg", "rb") as f:
            actual = extract_xml_from_svg(f.read())

        self.assertTrue(is_xml_equal(expected, actual))


if __name__ == "__main__":
    unittest.main()
