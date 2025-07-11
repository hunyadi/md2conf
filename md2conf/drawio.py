"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import base64
import typing
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path
from struct import unpack
from urllib.parse import unquote_to_bytes


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


def decompress_diagram(xml_bytes: bytes) -> ET.Element:
    """
    Decompresses the text content of the `<diagram>` element in a draw.io XML document.

    Expected input (as `bytes`):
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

    :param xml_bytes: The XML document as a `bytes` object.
    :returns: XML element tree with the text contained within the `<diagram>` element expanded into a sub-tree.
    """

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise DrawioError("invalid outer XML") from e

    if root.tag != "mxfile":
        raise DrawioError("root element is not `<mxfile>`")

    diagram_elem = root.find("diagram")
    if diagram_elem is None:
        raise DrawioError("`<diagram>` element not found")

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


def extract_xml(png_data: bytes) -> ET.Element:
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
            raise DrawioError(f"corrupted PNG: incomplete data for chunk {chunk_type.decode('ascii')}")

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
            raise DrawioError("corrupted PNG: tEXt chunk missing keyword")

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


def extract_diagram(png_path: Path) -> bytes:
    """
    Extracts an editable draw.io diagram from a PNG file.

    :param png_path: Path to a PNG file.
    :returns: XML data of a draw.io diagram as bytes.
    """

    with open(png_path, "rb") as f:
        root = extract_xml(f.read())

    return typing.cast(bytes, ET.tostring(root, encoding="utf8", method="xml"))
