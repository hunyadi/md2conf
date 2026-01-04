"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import tempfile
import unittest
from pathlib import Path

from md2conf.svg import get_svg_dimensions
from tests.utility import TypedTestCase


class TestSvgDimensions(TypedTestCase):
    "Unit tests for SVG dimension extraction."

    def test_explicit_dimensions(self) -> None:
        "Test SVG with explicit width and height attributes."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertEqual(width, 200)
        self.assertEqual(height, 100)

    def test_explicit_dimensions_with_px(self) -> None:
        "Test SVG with explicit width and height in px units."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="150px" height="75px"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertEqual(width, 150)
        self.assertEqual(height, 75)

    def test_viewbox_only(self) -> None:
        "Test SVG with only viewBox attribute (no explicit width/height)."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertEqual(width, 300)
        self.assertEqual(height, 200)

    def test_viewbox_with_comma_separator(self) -> None:
        "Test SVG with viewBox using comma separators."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0,0,400,250"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertEqual(width, 400)
        self.assertEqual(height, 250)

    def test_explicit_overrides_viewbox(self) -> None:
        "Test that explicit width/height take precedence over viewBox."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="100" height="50" viewBox="0 0 300 200"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertEqual(width, 100)
        self.assertEqual(height, 50)

    def test_partial_explicit_with_viewbox(self) -> None:
        "Test SVG with only width explicit, height from viewBox."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="100" viewBox="0 0 300 200"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertEqual(width, 100)
        self.assertEqual(height, 200)

    def test_pt_units(self) -> None:
        "Test SVG with pt (point) units."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="72pt" height="72pt"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        # 72pt = 1 inch = 96px
        self.assertEqual(width, 96)
        self.assertEqual(height, 96)

    def test_in_units(self) -> None:
        "Test SVG with inch units."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="2in" height="1in"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertEqual(width, 192)  # 2 * 96
        self.assertEqual(height, 96)  # 1 * 96

    def test_no_dimensions(self) -> None:
        "Test SVG with no dimension information."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertIsNone(width)
        self.assertIsNone(height)

    def test_percentage_dimensions(self) -> None:
        "Test SVG with percentage dimensions (should return None)."
        svg_content = '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertIsNone(width)
        self.assertIsNone(height)

    def test_non_svg_root(self) -> None:
        "Test file that is not a valid SVG (wrong root element)."
        xml_content = '<?xml version="1.0"?><html><body></body></html>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(xml_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertIsNone(width)
        self.assertIsNone(height)

    def test_malformed_xml(self) -> None:
        "Test malformed XML file."
        bad_content = "this is not xml at all <svg"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(bad_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertIsNone(width)
        self.assertIsNone(height)

    def test_nonexistent_file(self) -> None:
        "Test non-existent file path."
        width, height = get_svg_dimensions(Path("/nonexistent/path/to/file.svg"))
        self.assertIsNone(width)
        self.assertIsNone(height)

    def test_real_svg_file(self) -> None:
        "Test with the actual vector.svg file in the test fixtures."
        test_dir = Path(__file__).parent
        svg_path = test_dir / "source" / "figure" / "vector.svg"
        width, height = get_svg_dimensions(svg_path)
        self.assertEqual(width, 200)
        self.assertEqual(height, 200)

    def test_svg_without_namespace(self) -> None:
        "Test SVG without XML namespace."
        svg_content = '<?xml version="1.0"?><svg width="120" height="80"></svg>'
        with tempfile.NamedTemporaryFile(mode="w", suffix=".svg", delete=False) as f:
            f.write(svg_content)
            f.flush()
            width, height = get_svg_dimensions(Path(f.name))
        self.assertEqual(width, 120)
        self.assertEqual(height, 80)


if __name__ == "__main__":
    unittest.main()
