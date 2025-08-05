"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest

import lxml.etree as ET

from md2conf.converter import attachment_name, title_to_identifier
from md2conf.csf import elements_from_string
from md2conf.latex import LATEX_ENABLED, render_latex
from md2conf.toc import TableOfContentsBuilder, TableOfContentsEntry
from md2conf.xml import is_xml_equal, unwrap_substitute
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestUnit(TypedTestCase):
    "Simple unit tests without set-up or tear-down requirements."

    def test_attachment(self) -> None:
        self.assertEqual(attachment_name("image"), "image")
        self.assertEqual(attachment_name("a.png"), "a.png")
        self.assertEqual(attachment_name("a/b.png"), "a_b.png")
        self.assertEqual(attachment_name("../a.png"), "PAR_a.png")
        with self.assertRaises(ValueError):
            _ = attachment_name("/path/to/image.png")

    def test_xml_entities(self) -> None:
        tree1 = ET.fromstring('<body><p>to be, or "not" to be 😉</p></body>')
        tree2 = ET.fromstring("<body><p>to be, or &quot;not&quot; to be &#128521;</p></body>")
        self.assertTrue(is_xml_equal(tree1, tree2))

    def test_xml_skip_attribute(self) -> None:
        tree1 = ET.fromstring('<body><p class="paragraph" data-skip="..." style="display: none;">to be, or not to be</p></body>')
        tree2 = ET.fromstring('<body><p style="display: none;" class="paragraph">to be, or not to be</p></body>')
        self.assertFalse(is_xml_equal(tree1, tree2))
        self.assertTrue(is_xml_equal(tree1, tree2, skip_attributes={"data-skip"}))

    def test_unwrap(self) -> None:
        xml1 = (
            '<root xmlns:ac="http://atlassian.com/content"><p>'
            "Lorem <mark>ipsum</mark> dolor sit amet, "
            "<mark><em>consectetur</em> adipiscing elit</mark>, "
            "sed do eiusmod tempor incididunt ut <mark><b>labore</b> et <b>dolore</b></mark> "
            "<mark>magna <em>aliqua</em></mark>."
            "</p></root>"
        )
        xml2 = (
            '<root xmlns:ac="http://atlassian.com/content"><p>'
            "Lorem ipsum dolor sit amet, <em>consectetur</em> adipiscing elit, "
            "sed do eiusmod tempor incididunt ut <b>labore</b> et <b>dolore</b> magna <em>aliqua</em>."
            "</p></root>"
        )
        tree1 = elements_from_string(xml1)
        unwrap_substitute("mark", tree1)
        tree2 = elements_from_string(xml2)
        self.assertTrue(is_xml_equal(tree1, tree2))

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

    @unittest.skipUnless(LATEX_ENABLED, "matplotlib not installed")
    def test_formula(self) -> None:
        self.assertTrue(render_latex(r"\vec{\nabla}\times\vec{H}=\vec{J}+\dfrac{\partial\vec{D}}{\partial t}"))
        self.assertTrue(render_latex(r"\underset{S}{\int\int}\ \vec{\nabla}\times\vec{B}\cdot d\vec{S}=\underset{C}{\oint}\ \vec{B}\cdot d\vec{l}"))


if __name__ == "__main__":
    unittest.main()
