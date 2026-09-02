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

from md2conf.drawio.render import extract_diagram, extract_xml_from_png, extract_xml_from_svg, normalize_svg_ids
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
        expected = ET.fromstring((image_dir / "diagram.drawio").read_text(encoding="utf-8"))
        actual = extract_xml_from_png((image_dir / "diagram.drawio.png").read_bytes())
        self.assertTrue(is_xml_equal(expected, actual))

    def test_xml_from_svg(self) -> None:
        image_dir = Path(__file__).parent / "source" / "figure"
        expected = ET.fromstring((image_dir / "diagram.drawio").read_text(encoding="utf-8"))
        actual = extract_xml_from_svg((image_dir / "diagram.drawio.svg").read_bytes())
        self.assertTrue(is_xml_equal(expected, actual))

    def test_normalize_svg_ids(self) -> None:
        template = (
            b'<svg xmlns="http://www.w3.org/2000/svg" id="ge-svg-%(id)s">'
            b"<style>@supports (color: light-dark(#000, #fff)) "
            b"{ #ge-svg-%(id)s { --ge-adaptive-bg: light-dark(#ffffff, #121212); } }</style>"
            b"</svg>"
        )
        first = normalize_svg_ids(template % {b"id": b"1vCaTWRffH3CVbDsn_Bi"})
        second = normalize_svg_ids(template % {b"id": b"ho60hhIV57KdgwCItvaR"})

        self.assertEqual(first, second)
        self.assertNotIn(b"1vCaTWRffH3CVbDsn_Bi", first)
        self.assertEqual(first.count(b"ge-svg-"), 2)

    def test_normalize_svg_ids_distinct_diagrams(self) -> None:
        svg = b'<svg xmlns="http://www.w3.org/2000/svg" id="ge-svg-1vCaTWRffH3CVbDsn_Bi"><rect width="%d"/></svg>'
        self.assertNotEqual(normalize_svg_ids(svg % 10), normalize_svg_ids(svg % 20))

    def test_normalize_svg_ids_without_identifier(self) -> None:
        svg = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="10"/></svg>'
        self.assertEqual(normalize_svg_ids(svg), svg)


if __name__ == "__main__":
    unittest.main()
