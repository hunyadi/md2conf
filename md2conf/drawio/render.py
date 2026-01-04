"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import base64
import logging
import os
import shutil
import subprocess
import tempfile
import typing
import zlib
from pathlib import Path
from struct import unpack
from urllib.parse import unquote_to_bytes

import lxml.etree as ET

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]

LOGGER = logging.getLogger(__name__)


class DrawioError(ValueError):
    """
    Raised when the input does not adhere to the draw.io document format, or processing the input into a draw.io diagram fails.

    Examples include:

    * invalid or corrupt PNG file
    * PNG chunk with embedded diagram data not found
    * the structure of the outer XML does not match the expected format
    * URL decoding error
    * decompression error during INFLATE
    """


def inflate(data: bytes) -> bytes:
    """
    Decompresses (inflates) data compressed using the raw DEFLATE algorithm.

    :param data: Compressed data using raw DEFLATE format.
    :returns: Uncompressed data.
    """

    # -zlib.MAX_WBITS indicates raw DEFLATE stream (no zlib/gzip headers)
    return zlib.decompress(data, -zlib.MAX_WBITS)


def decompress_diagram(xml_data: bytes | str) -> ElementType:
    """
    Decompresses the text content of the `<diagram>` element in a draw.io XML document.

    If the data is not compressed, the de-serialized XML element tree is returned.

    Expected input (as `bytes` or `str`):
    ```
    <mxfile>
        <diagram>... ENCODED_COMPRESSED_DATA ...</diagram>
    </mxfile>
    ```

    Output (as XML element tree):
    ```
    <mxfile>
        <diagram>
            <mxGraphModel>
                <root>
                    ...
                </root>
            </mxGraphModel>
        </diagram>
    </mxfile>
    ```

    :param xml_data: The serialized XML document.
    :returns: XML element tree with the text contained within the `<diagram>` element expanded into a sub-tree.
    """

    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as e:
        raise DrawioError("invalid outer XML") from e

    if root.tag != "mxfile":
        raise DrawioError("root element is not `<mxfile>`")

    diagram_elem = root.find("diagram")
    if diagram_elem is None:
        raise DrawioError("`<diagram>` element not found")

    if len(diagram_elem) > 0:
        # already decompressed
        return root

    if diagram_elem.text is None:
        raise DrawioError("`<diagram>` element has no data")

    # reverse base64-encoding of inner data
    try:
        base64_decoded = base64.b64decode(diagram_elem.text, validate=True)
    except ValueError as e:
        raise DrawioError("raw text data in `<diagram>` element is not properly Base64-encoded") from e

    # decompress inner data
    try:
        embedded_data = inflate(base64_decoded)
    except zlib.error as e:
        raise DrawioError("`<diagram>` element text data cannot be decompressed using INFLATE") from e

    # reverse URL-encoding of inner data
    try:
        url_decoded = unquote_to_bytes(embedded_data)
    except ValueError as e:
        raise DrawioError("decompressed data in `<diagram>` element is not properly URL-encoded") from e

    # create sub-tree from decompressed data
    try:
        tree = ET.fromstring(url_decoded)
    except ET.ParseError as e:
        raise DrawioError("invalid inner XML extracted from `<diagram>` element") from e

    # update document
    diagram_elem.text = None
    diagram_elem.append(tree)

    return root


def extract_xml_from_png(png_data: bytes) -> ElementType:
    """
    Extracts an editable draw.io diagram from a PNG file.

    :param png_data: PNG binary data, with an embedded draw.io diagram.
    :returns: XML element tree of a draw.io diagram.
    """

    # PNG signature is always the first 8 bytes
    png_signature = b"\x89PNG\r\n\x1a\n"
    if not png_data.startswith(png_signature):
        raise DrawioError("not a valid PNG file")

    offset = len(png_signature)
    while offset < len(png_data):
        if offset + 8 > len(png_data):
            raise DrawioError("corrupted PNG: incomplete chunk header")

        # read chunk length (4 bytes) and type (4 bytes)
        (length,) = unpack(">I", png_data[offset : offset + 4])
        chunk_type = png_data[offset + 4 : offset + 8]
        offset += 8

        if offset + length + 4 > len(png_data):
            chunk_name = chunk_type.decode("ascii", errors="replace")
            raise DrawioError(f"corrupted PNG: incomplete data for chunk {chunk_name}")

        # read chunk data
        chunk_data = png_data[offset : offset + length]
        offset += length

        # skip CRC (4 bytes)
        offset += 4

        # extracts draw.io diagram data from a `tEXt` chunk with the keyword `mxfile` embedded in a PNG
        if chunk_type != b"tEXt":
            continue

        # format: keyword\0text
        null_pos = chunk_data.find(b"\x00")
        if null_pos < 0:
            raise DrawioError("corrupted PNG: `tEXt` chunk missing keyword or data")

        keyword = chunk_data[:null_pos].decode("latin1")
        if keyword != "mxfile":
            continue

        textual_data = chunk_data[null_pos + 1 :]

        try:
            url_decoded = unquote_to_bytes(textual_data)
        except ValueError as e:
            raise DrawioError("data in `tEXt` chunk is not properly URL-encoded") from e

        # decompress data embedded in the outer XML wrapper
        return decompress_diagram(url_decoded)

    # matching `tEXt` chunk not found
    raise DrawioError("not a PNG file made with draw.io")


def extract_xml_from_svg(svg_data: bytes) -> ElementType:
    """
    Extracts an editable draw.io diagram from an SVG file.

    :param svg_data: SVG XML data, with an embedded draw.io diagram.
    :returns: XML element tree of a draw.io diagram.
    """

    try:
        root = ET.fromstring(svg_data)
    except ET.ParseError as e:
        raise DrawioError("invalid SVG XML") from e

    content = root.attrib.get("content")
    if content is None:
        raise DrawioError("SVG root element has no attribute `content`")

    return decompress_diagram(content)


def extract_diagram(path: Path) -> bytes:
    """
    Extracts an editable draw.io diagram from a PNG file.

    :param path: Path to a PNG or SVG file with an embedded draw.io diagram.
    :returns: XML data of a draw.io diagram as bytes.
    """

    if path.name.endswith(".drawio.png"):
        with open(path, "rb") as png_file:
            root = extract_xml_from_png(png_file.read())
    elif path.name.endswith(".drawio.svg"):
        with open(path, "rb") as svg_file:
            root = extract_xml_from_svg(svg_file.read())
    else:
        raise DrawioError(f"unrecognized file type for {path.name}")

    return ET.tostring(root, encoding="utf8", method="xml")


def render_diagram(source: Path, output_format: typing.Literal["png", "svg"] = "png") -> bytes:
    "Generates a PNG or SVG image from a draw.io diagram source."

    executable = shutil.which("draw.io")
    if executable is None:
        raise DrawioError("draw.io executable not found")

    # create a temporary file and get its file descriptor and path
    fd, target = tempfile.mkstemp(prefix="drawio_", suffix=f".{output_format}")

    try:
        # close the descriptor, just use the filename
        os.close(fd)

        cmd = [executable, "--export", "--format", output_format, "--output", target]
        if output_format == "png":
            cmd.extend(["--scale", "2", "--transparent"])
        elif output_format == "svg":
            cmd.append("--embed-svg-images")
        cmd.append(str(source))

        LOGGER.debug("Executing: %s", " ".join(cmd))
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        stdout, stderr = proc.communicate()
        if proc.returncode:
            messages = [f"failed to convert draw.io diagram; exit code: {proc.returncode}"]
            console_output = stdout.decode("utf-8")
            if console_output:
                messages.append(f"output:\n{console_output}")
            console_error = stderr.decode("utf-8")
            if console_error:
                messages.append(f"error:\n{console_error}")
            raise DrawioError("\n".join(messages))
        with open(target, "rb") as f:
            return f.read()

    finally:
        os.remove(target)
