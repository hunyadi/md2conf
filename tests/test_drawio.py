"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from md2conf.drawio import extract_diagram, extract_xml_from_png, extract_xml_from_svg
from md2conf.xml import compare_xml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestDrawio(unittest.TestCase):
    def test_bytes(self) -> None:
        image_dir = Path(__file__).parent / "source" / "figure"
        image_file = image_dir / "diagram.drawio.png"
        image = extract_diagram(image_file)
        self.assertGreater(len(image), 0)

    def test_xml_from_png(self) -> None:
        image_dir = Path(__file__).parent / "source" / "figure"
        with open(image_dir / "diagram.drawio", "r") as f:
            expected = ET.fromstring(f.read())

        with open(image_dir / "diagram.drawio.png", "rb") as f:
            actual = extract_xml_from_png(f.read())

        self.assertTrue(compare_xml(expected, actual))

    def test_xml_from_svg(self) -> None:
        image_dir = Path(__file__).parent / "source" / "figure"
        with open(image_dir / "diagram.drawio", "r") as f:
            expected = ET.fromstring(f.read())

        with open(image_dir / "diagram.drawio.svg", "rb") as f:
            actual = extract_xml_from_svg(f.read())

        self.assertTrue(compare_xml(expected, actual))


if __name__ == "__main__":
    unittest.main()
