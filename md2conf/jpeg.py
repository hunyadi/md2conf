"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from io import BytesIO
from pathlib import Path
from typing import BinaryIO, overload


class ImageFormatError(RuntimeError):
    pass


def _extract_jpeg_dimensions(source_file: BinaryIO) -> tuple[int, int]:
    """
    Returns the width and height of a JPEG image inspecting its header.

    :param source_file: A binary file opened for reading that contains JPEG image data.
    :returns: A tuple of the image's width and height in pixels.
    """

    # Read and validate SOI (Start of Image) marker
    soi = source_file.read(2)
    if soi != b"\xff\xd8":
        raise ImageFormatError("not a valid JPEG file")

    # Scan for Start of Frame (SOF) marker
    while True:
        marker = source_file.read(1)
        if not marker:
            raise ImageFormatError("SOF marker not found in JPEG file")

        if marker != b"\xff":
            continue

        marker_type = source_file.read(1)
        if not marker_type:
            raise ImageFormatError("unexpected end of JPEG file")

        marker_byte = ord(marker_type)

        # SOF markers are in ranges: 0xC0-0xC3, 0xC5-0xC7, 0xC9-0xCB, 0xCD-0xCF
        is_sof = (0xC0 <= marker_byte <= 0xC3) or (0xC5 <= marker_byte <= 0xC7) or (0xC9 <= marker_byte <= 0xCB) or (0xCD <= marker_byte <= 0xCF)

        if is_sof:
            # Read segment length (2 bytes, big-endian)
            length_bytes = source_file.read(2)
            if len(length_bytes) != 2:
                raise ImageFormatError("invalid segment length in JPEG file")

            # Read precision (1 byte)
            source_file.read(1)

            # Read height and width (2 bytes each, big-endian)
            height_bytes = source_file.read(2)
            width_bytes = source_file.read(2)

            if len(height_bytes) != 2 or len(width_bytes) != 2:
                raise ImageFormatError("invalid height/width data in JPEG file")

            height = int.from_bytes(height_bytes, "big")
            width = int.from_bytes(width_bytes, "big")

            return width, height
        else:
            # Skip this segment
            length_bytes = source_file.read(2)
            if len(length_bytes) != 2:
                raise ImageFormatError("invalid segment length in JPEG file")

            segment_length = int.from_bytes(length_bytes, "big") - 2
            source_file.read(segment_length)


@overload
def extract_jpeg_dimensions(*, data: bytes) -> tuple[int, int]: ...


@overload
def extract_jpeg_dimensions(*, path: str | Path) -> tuple[int, int]: ...


def extract_jpeg_dimensions(*, data: bytes | None = None, path: str | Path | None = None) -> tuple[int, int]:
    """
    Returns the width and height of a JPEG image inspecting its header.

    :param data: JPEG image data.
    :param path: Path to the JPEG image file.
    :returns: A tuple of the image's width and height in pixels.
    """

    if data is not None and path is not None:
        raise TypeError("expected: either `data` or `path`; got: both")
    elif data is not None:
        with BytesIO(data) as f:
            return _extract_jpeg_dimensions(f)
    elif path is not None:
        with open(path, "rb") as f:
            return _extract_jpeg_dimensions(f)
    else:
        raise TypeError("expected: either `data` or `path`; got: neither")
