"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from pathlib import Path

from md2conf.svg import get_svg_dimensions
from tests.utility import TypedTestCase


class TestSvgDimensions(TypedTestCase):
    "Unit tests for SVG dimension extraction."

    def assertDimensions(self, dimensions: tuple[int, int] | None, width: int, height: int) -> None:
        self.assertIsNotNone(dimensions)
        if dimensions is not None:
            self.assertEqual(dimensions[0], width)
            self.assertEqual(dimensions[1], height)

    def test_explicit_dimensions(self) -> None:
        "Test SVG with explicit width and height attributes."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 200, 100)

    def test_explicit_dimensions_with_px(self) -> None:
        "Test SVG with explicit width and height in px units."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="150px" height="75px"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 150, 75)

    def test_viewbox_only(self) -> None:
        "Test SVG with only viewBox attribute (no explicit width/height)."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 300, 200)

    def test_viewbox_with_comma_separator(self) -> None:
        "Test SVG with viewBox using comma separators."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0,0,400,250"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 400, 250)

    def test_width_height_viewbox(self) -> None:
        "Test that explicit width/height take precedence over viewBox."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 300 200"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 100, 50)

    def test_viewbox_no_height(self) -> None:
        "Test SVG with only width explicit, height from viewBox."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="100" viewBox="0 0 300 200"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 100, 66)

    def test_viewbox_no_width(self) -> None:
        "Test SVG with only height explicit, width from viewBox."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" height="100" viewBox="0 0 300 200"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 150, 100)

    def test_pt_units(self) -> None:
        "Test SVG with pt (point) units."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="72pt" height="72pt"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        # 72pt = 1 inch = 96px
        self.assertDimensions(dimensions, 96, 96)

    def test_in_units(self) -> None:
        "Test SVG with inch units."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="2in" height="1in"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 192, 96)

    def test_no_dimensions(self) -> None:
        "Test SVG with no dimension information."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertIsNone(dimensions)

    def test_percentage_dimensions(self) -> None:
        "Test SVG with percentage dimensions (should return None)."

        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertIsNone(dimensions)

    def test_non_svg_root(self) -> None:
        "Test file that is not a valid SVG (wrong root element)."

        xml_content = '<?xml version="1.0"?><html><body></body></html>'
        with self.assertLogs(level="WARNING"):
            dimensions = get_svg_dimensions(xml_content)
        self.assertIsNone(dimensions)

    def test_malformed_xml(self) -> None:
        "Test malformed XML file."

        bad_content = "this is not xml at all <svg"
        with self.assertLogs(level="WARNING"):
            dimensions = get_svg_dimensions(bad_content)
        self.assertIsNone(dimensions)

    def test_nonexistent_file(self) -> None:
        "Test non-existent file path."

        with self.assertLogs(level="WARNING"):
            dimensions = get_svg_dimensions(Path("/nonexistent/path/to/file.svg"))
        self.assertIsNone(dimensions)

    def test_real_svg_file(self) -> None:
        "Test with the actual vector.svg file in the test fixtures."

        test_dir = Path(__file__).parent
        svg_path = test_dir / "source" / "figure" / "vector.svg"
        dimensions = get_svg_dimensions(svg_path)
        self.assertDimensions(dimensions, 200, 200)

    def test_svg_without_namespace(self) -> None:
        "Test SVG without XML namespace."

        svg_content = '<?xml version="1.0"?><svg width="120" height="80"></svg>'
        dimensions = get_svg_dimensions(svg_content)
        self.assertDimensions(dimensions, 120, 80)


if __name__ == "__main__":
    unittest.main()
