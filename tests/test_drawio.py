"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from md2conf.drawio import extract_diagram
from md2conf.xml import compare_xml

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestDrawio(unittest.TestCase):
    def test_extract(self) -> None:
        image_dir = Path(__file__).parent / "images"
        with open(image_dir / "diagram.drawio", "r") as f:
            expected = ET.fromstring(f.read())

        with open(image_dir / "diagram.png", "rb") as f:
            actual = extract_diagram(f.read())

        self.assertTrue(compare_xml(expected, actual))


if __name__ == "__main__":
    unittest.main()
