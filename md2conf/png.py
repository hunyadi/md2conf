"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from io import BytesIO
from pathlib import Path
from struct import unpack
from typing import BinaryIO, Iterable, overload


class _Chunk:
    "Data chunk in binary data as per the PNG image format."

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
        raise ValueError("expected: 4 bytes storing chunk length")

    length = int.from_bytes(length_bytes, "big")

    data_length = 4 + length + 4
    data_bytes = f.read(data_length)
    actual_length = len(data_bytes)
    if actual_length != data_length:
        raise ValueError(f"expected: {length} bytes storing chunk data; got: {actual_length}")

    chunk_type = data_bytes[0:4]
    chunk_data = data_bytes[4:-4]
    crc = data_bytes[-4:]

    return _Chunk(length, chunk_type, chunk_data, crc)


def _extract_png_dimensions(source_file: BinaryIO) -> tuple[int, int]:
    """
    Returns the width and height of a PNG image inspecting its header.

    :param source_file: A binary file opened for reading that contains PNG image data.
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
    ) = unpack(">IIBBBBB", ihdr.data)  # spellchecker:disable-line
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


def _write_chunk(f: BinaryIO, chunk: _Chunk) -> None:
    f.write(chunk.length.to_bytes(4, "big"))
    f.write(chunk.name)
    f.write(chunk.data)
    f.write(chunk.crc)


def _remove_png_chunks(names: Iterable[str], source_file: BinaryIO, target_file: BinaryIO) -> None:
    """
    Rewrites a PNG file by removing chunks with the specified names.

    :param source_file: A binary file opened for reading that contains PNG image data.
    :param target_file: A binary file opened for writing to receive PNG image data.
    """

    exclude_set = set(name.encode("ascii") for name in names)

    _read_signature(source_file)
    target_file.write(b"\x89PNG\r\n\x1a\n")

    while True:
        chunk = _read_chunk(source_file)
        if chunk is None:
            break

        if chunk.name not in exclude_set:
            _write_chunk(target_file, chunk)


@overload
def remove_png_chunks(names: Iterable[str], *, source_data: bytes) -> bytes: ...


@overload
def remove_png_chunks(names: Iterable[str], *, source_path: str | Path) -> bytes: ...


@overload
def remove_png_chunks(names: Iterable[str], *, source_data: bytes, target_path: str | Path) -> None: ...


@overload
def remove_png_chunks(names: Iterable[str], *, source_path: str | Path, target_path: str | Path) -> None: ...


def remove_png_chunks(
    names: Iterable[str], *, source_data: bytes | None = None, source_path: str | Path | None = None, target_path: str | Path | None = None
) -> bytes | None:
    """
    Rewrites a PNG file by removing chunks with the specified names.

    :param source_data: PNG image data.
    :param source_path: Path to the file to read from.
    :param target_path: Path to the file to write to.
    """

    if source_data is not None and source_path is not None:
        raise TypeError("expected: either `source_data` or `source_path`; got: both")
    elif source_data is not None:

        def source_reader() -> BinaryIO:
            return BytesIO(source_data)
    elif source_path is not None:

        def source_reader() -> BinaryIO:
            return open(source_path, "rb")
    else:
        raise TypeError("expected: either `source_data` or `source_path`; got: neither")

    if target_path is None:
        with source_reader() as source_file, BytesIO() as memory_file:
            _remove_png_chunks(names, source_file, memory_file)
            return memory_file.getvalue()
    else:
        with source_reader() as source_file, open(target_path, "wb") as target_file:
            _remove_png_chunks(names, source_file, target_file)
            return None
