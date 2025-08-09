"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest

from md2conf.converter import attachment_name, title_to_identifier
from md2conf.latex import LATEX_ENABLED, get_png_dimensions, remove_png_chunks, render_latex
from md2conf.toc import TableOfContentsBuilder, TableOfContentsEntry
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
        data = render_latex(r"\vec{\nabla}\times\vec{H}=\vec{J}+\dfrac{\partial\vec{D}}{\partial t}")
        width, height = get_png_dimensions(data=data)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

        data = render_latex(r"\underset{S}{\int\int}\ \vec{\nabla}\times\vec{B}\cdot d\vec{S}=\underset{C}{\oint}\ \vec{B}\cdot d\vec{l}")
        width, height = get_png_dimensions(data=data)
        self.assertGreater(width, 0)
        self.assertGreater(height, 0)

        self.assertIn(b"pHYs", data)
        data = remove_png_chunks(["pHYs"], source_data=data)
        self.assertNotIn(b"pHYs", data)


if __name__ == "__main__":
    unittest.main()
