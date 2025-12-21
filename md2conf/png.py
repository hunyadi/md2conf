"""
PNG dimension extraction utilities.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from io import BytesIO
from pathlib import Path
from struct import unpack
from typing import BinaryIO, overload


class _Chunk:
    __slots__ = ("length", "name", "data", "crc")

    length: int
    name: bytes
    data: bytes
    crc: bytes

    def __init__(self, length: int, name: bytes, data: bytes, crc: bytes):
        self.length = length
        self.name = name
        self.data = data
        self.crc = crc


def _read_signature(f: BinaryIO) -> None:
    "Reads and checks PNG signature (first 8 bytes)."

    signature = f.read(8)
    if signature != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a valid PNG file")


def _read_chunk(f: BinaryIO) -> _Chunk | None:
    "Reads and parses a PNG chunk such as `IHDR` or `tEXt`."

    length_bytes = f.read(4)
    if not length_bytes:
        return None

    if len(length_bytes) != 4:
        raise ValueError("insufficient bytes to read chunk length")

    length = int.from_bytes(length_bytes, "big")

    data_length = 4 + length + 4
    data_bytes = f.read(data_length)
    if len(data_bytes) != data_length:
        raise ValueError(f"insufficient bytes to read chunk data of length {length}")

    chunk_type = data_bytes[0:4]
    chunk_data = data_bytes[4:-4]
    crc = data_bytes[-4:]

    return _Chunk(length, chunk_type, chunk_data, crc)


def _extract_png_dimensions(source_file: BinaryIO) -> tuple[int, int]:
    """
    Returns the width and height of a PNG image inspecting its header.

    :param source_file: A binary file opened for reading that contains
        PNG image data.
    :returns: A tuple of the image's width and height in pixels.
    """

    _read_signature(source_file)

    # validate IHDR (Image Header) chunk
    ihdr = _read_chunk(source_file)
    if ihdr is None:
        raise ValueError("missing IHDR chunk")

    if ihdr.length != 13:
        raise ValueError("invalid chunk length")
    if ihdr.name != b"IHDR":
        raise ValueError(f"expected: IHDR chunk; got: {ihdr.name!r}")

    (
        width,
        height,
        bit_depth,  # pyright: ignore[reportUnusedVariable]
        color_type,  # pyright: ignore[reportUnusedVariable]
        compression,  # pyright: ignore[reportUnusedVariable]
        filter,  # pyright: ignore[reportUnusedVariable]
        interlace,  # pyright: ignore[reportUnusedVariable]
    ) = unpack(">IIBBBBB", ihdr.data)
    return width, height


@overload
def extract_png_dimensions(*, data: bytes) -> tuple[int, int]: ...


@overload
def extract_png_dimensions(*, path: str | Path) -> tuple[int, int]: ...


def extract_png_dimensions(*, data: bytes | None = None, path: str | Path | None = None) -> tuple[int, int]:
    """
    Returns the width and height of a PNG image inspecting its header.

    :param data: PNG image data.
    :param path: Path to the PNG image file.
    :returns: A tuple of the image's width and height in pixels.
    """

    if data is not None and path is not None:
        raise TypeError("expected: either `data` or `path`; got: both")
    elif data is not None:
        with BytesIO(data) as f:
            return _extract_png_dimensions(f)
    elif path is not None:
        with open(path, "rb") as f:
            return _extract_png_dimensions(f)
    else:
        raise TypeError("expected: either `data` or `path`; got: neither")
