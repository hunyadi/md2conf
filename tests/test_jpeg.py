"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest

from md2conf.jpeg import ImageFormatError, extract_jpeg_dimensions
from tests.utility import TypedTestCase, temporary_file


class TestJpegDimensions(TypedTestCase):
    "Unit tests for JPEG dimension extraction."

    def test_jpeg_dimensions_from_data(self) -> None:
        "Test extracting dimensions from JPEG data in memory."

        # Minimal valid JPEG: 1x1 pixel
        # SOI marker + SOF0 marker + minimal data + EOI marker
        jpeg_data = (
            b"\xff\xd8"  # SOI (Start of Image)
            b"\xff\xc0"  # SOF0 (Start of Frame, Baseline DCT)
            b"\x00\x0b"  # Segment length: 11 bytes
            b"\x08"  # Precision: 8 bits
            b"\x00\x01"  # Height: 1
            b"\x00\x01"  # Width: 1
            b"\x01"  # Components: 1
            b"\x01\x11\x00"  # Component data
            b"\xff\xd9"  # EOI (End of Image)
        )
        width, height = extract_jpeg_dimensions(data=jpeg_data)
        self.assertEqual(width, 1)
        self.assertEqual(height, 1)

    def test_jpeg_dimensions_from_file(self) -> None:
        "Test extracting dimensions from JPEG file."

        # Minimal 100x50 JPEG
        jpeg_data = (
            b"\xff\xd8"  # SOI (Start of Image)
            b"\xff\xc0"  # SOF0 (Start of Frame, Baseline DCT)
            b"\x00\x0b"  # Segment length: 11 bytes
            b"\x08"  # Precision: 8 bits
            b"\x00\x32"  # Height: 50
            b"\x00\x64"  # Width: 100
            b"\x01"  # Components: 1
            b"\x01\x11\x00"  # Component data
            b"\xff\xd9"  # EOI (End of Image)
        )
        with temporary_file(jpeg_data, suffix=".jpg") as temp_path:
            width, height = extract_jpeg_dimensions(path=temp_path)
        self.assertEqual(width, 100)
        self.assertEqual(height, 50)

    def test_jpeg_invalid_signature(self) -> None:
        "Test that invalid JPEG signature raises exception."

        invalid_data = b"NOT_A_JPEG_FILE"
        with self.assertRaises(ImageFormatError):
            extract_jpeg_dimensions(data=invalid_data)

    def test_jpeg_missing_sof(self) -> None:
        "Test that JPEG without SOF marker raises exception."

        invalid_data = b"\xff\xd8"  # Valid JPEG signature but no SOF marker (truncated)
        with self.assertRaises(ImageFormatError):
            extract_jpeg_dimensions(data=invalid_data)

    def test_jpeg_with_multiple_segments(self) -> None:
        "Test extracting dimensions from JPEG with multiple segments before SOF."

        # JPEG with APP0 marker (JFIF) before SOF
        jpeg_data = (
            b"\xff\xd8"  # SOI (Start of Image)
            b"\xff\xe0"  # APP0 (JFIF marker)
            b"\x00\x10"  # Segment length: 16 bytes
            b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"  # JFIF data
            b"\xff\xc0"  # SOF0 (Start of Frame)
            b"\x00\x0b"  # Segment length: 11 bytes
            b"\x08"  # Precision: 8 bits
            b"\x00\x64"  # Height: 100
            b"\x00\xc8"  # Width: 200
            b"\x01"  # Components: 1
            b"\x01\x11\x00"  # Component data
            b"\xff\xd9"  # EOI (End of Image)
        )
        width, height = extract_jpeg_dimensions(data=jpeg_data)
        self.assertEqual(width, 200)
        self.assertEqual(height, 100)


if __name__ == "__main__":
    unittest.main()
