"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest

import lxml.etree as ET

from md2conf.converter import attachment_name, title_to_identifier
from md2conf.toc import TableOfContentsBuilder, TableOfContentsEntry
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

    def test_title_to_identifier(self) -> None:
        self.assertEqual(title_to_identifier("This is  a Heading  "), "this-is-a-heading")
        self.assertEqual(title_to_identifier("What's New in v2.0?"), "whats-new-in-v20")
        self.assertEqual(title_to_identifier("C++ & C# Comparison"), "c-c-comparison")
        self.assertEqual(title_to_identifier("Hello -- World!!"), "hello----world")
        self.assertEqual(title_to_identifier("árvíztűrő tükörfúrógép"), "rvztr-tkrfrgp")

    def test_toc(self) -> None:
        builder = TableOfContentsBuilder()
        sections = [
            (2, "Section 1"),
            (3, "Section 1.1"),
            (3, "Section 1.2"),
            (6, "Section 1.2.1"),  # test skipping levels
            (6, "Section 1.2.2"),
            (3, "Section 1.3"),
            (4, "Section 1.3.1"),
            (2, "Section 2"),
        ]
        for level, text in sections:
            builder.add(level, text)
        expected = [
            TableOfContentsEntry(
                2,
                "Section 1",
                [
                    TableOfContentsEntry(3, "Section 1.1"),
                    TableOfContentsEntry(
                        3,
                        "Section 1.2",
                        [
                            TableOfContentsEntry(6, "Section 1.2.1"),
                            TableOfContentsEntry(6, "Section 1.2.2"),
                        ],
                    ),
                    TableOfContentsEntry(
                        3,
                        "Section 1.3",
                        [
                            TableOfContentsEntry(4, "Section 1.3.1"),
                        ],
                    ),
                ],
            ),
            TableOfContentsEntry(2, "Section 2"),
        ]
        self.assertEqual(expected, builder.tree)
        self.assertIsNone(builder.get_title())

    def test_toc_title(self) -> None:
        builder = TableOfContentsBuilder()
        sections = [
            (2, "Title"),
            (3, "Section 1"),
            (3, "Section 2"),
            (4, "Section 2.1"),
        ]
        for level, text in sections:
            builder.add(level, text)
        expected = [
            TableOfContentsEntry(
                2,
                "Title",
                [
                    TableOfContentsEntry(3, "Section 1"),
                    TableOfContentsEntry(
                        3,
                        "Section 2",
                        [
                            TableOfContentsEntry(4, "Section 2.1"),
                        ],
                    ),
                ],
            ),
        ]
        self.assertEqual(expected, builder.tree)
        self.assertEqual(builder.get_title(), "Title")


if __name__ == "__main__":
    unittest.main()
