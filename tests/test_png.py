"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import tempfile
import unittest

from md2conf.png import extract_png_dimensions
from tests.utility import TypedTestCase


class TestPngDimensions(TypedTestCase):
    "Unit tests for PNG dimension extraction."

    def test_png_dimensions_from_data(self) -> None:
        "Test extracting dimensions from PNG data in memory."

        # Minimal valid PNG: 1x1 pixel, 8-bit grayscale
        # PNG signature + IHDR chunk with width=1, height=1
        png_data = (
            b"\x89PNG\r\n\x1a\n"  # PNG signature
            b"\x00\x00\x00\x0d"  # IHDR length (13 bytes)
            b"IHDR"  # IHDR chunk type
            b"\x00\x00\x00\x01"  # Width: 1
            b"\x00\x00\x00\x01"  # Height: 1
            b"\x08"  # Bit depth: 8
            b"\x00"  # Color type: grayscale
            b"\x00"  # Compression: deflate
            b"\x00"  # Filter: adaptive
            b"\x00"  # Interlace: none
            b"\x00\x00\x00\x00"  # CRC (simplified for test)
        )
        width, height = extract_png_dimensions(data=png_data)
        self.assertEqual(width, 1)
        self.assertEqual(height, 1)

    def test_png_dimensions_from_file(self) -> None:
        "Test extracting dimensions from PNG file."

        # Create a minimal 100x50 PNG
        png_data = (
            b"\x89PNG\r\n\x1a\n"  # PNG signature
            b"\x00\x00\x00\x0d"  # IHDR length (13 bytes)
            b"IHDR"  # IHDR chunk type
            b"\x00\x00\x00\x64"  # Width: 100
            b"\x00\x00\x00\x32"  # Height: 50
            b"\x08"  # Bit depth: 8
            b"\x02"  # Color type: RGB
            b"\x00"  # Compression: deflate
            b"\x00"  # Filter: adaptive
            b"\x00"  # Interlace: none
            b"\x00\x00\x00\x00"  # CRC (simplified for test)
        )
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".png", delete=False) as f:
            f.write(png_data)
            f.flush()
            width, height = extract_png_dimensions(path=f.name)
        self.assertEqual(width, 100)
        self.assertEqual(height, 50)

    def test_png_invalid_signature(self) -> None:
        "Test that invalid PNG signature raises ValueError."

        invalid_data = b"NOT_A_PNG_FILE"
        with self.assertRaises(ValueError) as context:
            extract_png_dimensions(data=invalid_data)
        self.assertIn("not a valid PNG file", str(context.exception))

    def test_png_missing_ihdr(self) -> None:
        "Test that PNG without IHDR chunk raises ValueError."

        invalid_data = b"\x89PNG\r\n\x1a\n"  # Valid PNG signature but no IHDR chunk (truncated)
        with self.assertRaises(ValueError) as context:
            extract_png_dimensions(data=invalid_data)
        self.assertIn("ihdr", str(context.exception).lower())


if __name__ == "__main__":
    unittest.main()
