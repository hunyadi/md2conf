"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest

import lxml.etree as ET

from md2conf.converter import attachment_name
from md2conf.xml import is_xml_equal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestUnit(unittest.TestCase):
    "Simple unit tests without set-up or tear-down requirements."

    def test_attachment(self) -> None:
        self.assertEqual(attachment_name("image"), "image")
        self.assertEqual(attachment_name("a.png"), "a.png")
        self.assertEqual(attachment_name("a/b.png"), "a_b.png")
        self.assertEqual(attachment_name("../a.png"), "PAR_a.png")
        with self.assertRaises(ValueError):
            _ = attachment_name("/path/to/image.png")

    def test_xml(self) -> None:
        tree1 = ET.fromstring('<body><p class="paragraph" data-skip="..." style="display: none;">to be, or not to be</p></body>')
        tree2 = ET.fromstring('<body><p style="display: none;" class="paragraph">to be, or not to be</p></body>')
        self.assertFalse(is_xml_equal(tree1, tree2))
        self.assertTrue(is_xml_equal(tree1, tree2, skip_attributes={"data-skip"}))


if __name__ == "__main__":
    unittest.main()
