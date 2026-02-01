"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import re
from pathlib import Path
from typing import overload

import lxml.etree as ET

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]

LOGGER = logging.getLogger(__name__)

SVG_NAMESPACE = "http://www.w3.org/2000/svg"


class SVGParseError(RuntimeError):
    pass


def _check_svg(root: ElementType) -> bool:
    "Tests if the element is a plain or scoped SVG element."

    root_tag = root.tag
    if not isinstance(root_tag, str):
        raise TypeError("expected: tag names as `str`")

    # Handle namespaced and non-namespaced SVG
    qname = ET.QName(root_tag)
    return qname.localname == "svg" and (not qname.namespace or qname.namespace == SVG_NAMESPACE)


def _extract_dimensions_from_root(root: ElementType) -> tuple[int, int] | None:
    """
    Extracts width and height from an SVG root element.

    Attempts to read dimensions from:
    1. Explicit width/height attributes on the root <svg> element
    2. The viewBox attribute if width/height are not specified

    :param root: The root element of the SVG document.
    :returns: A tuple of (width, height) in pixels, or `None` if dimensions cannot be determined.
    """

    if not _check_svg(root):
        raise SVGParseError("SVG file does not have an <svg> root element")

    width_attr = root.get("width")
    height_attr = root.get("height")

    width = _parse_svg_length(width_attr) if width_attr else None
    height = _parse_svg_length(height_attr) if height_attr else None

    # if width/height not specified, try to derive from view-box
    if width is None or height is None:
        viewbox_attr = root.get("viewBox")
        if viewbox_attr:
            viewbox = _parse_viewbox(viewbox_attr)
            if viewbox is not None:
                vb_width, vb_height = viewbox
                if width is not None:
                    height = width * vb_height // vb_width
                elif height is not None:
                    width = height * vb_width // vb_height
                else:
                    width = vb_width
                    height = vb_height

    if width is None or height is None:
        return None

    return width, height


@overload
def get_svg_dimensions(svg: Path) -> tuple[int, int] | None:
    """
    Extracts width and height from an SVG file.

    Attempts to read dimensions from:

    1. Explicit `width` and `height` attributes on the root `<svg>` element
    2. The `viewBox` attribute if `width` or `height` is not specified

    :param svg: Path to the SVG file.
    :returns: A tuple of (width, height) in pixels, or `None` if dimensions cannot be determined.
    """
    ...


@overload
def get_svg_dimensions(svg: bytes | str) -> tuple[int, int] | None:
    """
    Extracts width and height from SVG data in memory.

    Attempts to read dimensions from:

    1. Explicit `width` and `height` attributes on the root `<svg>` element
    2. The `viewBox` attribute if `width` or `height` is not specified

    :param svg: The SVG content as bytes.
    :returns: A tuple of (width, height) in pixels, or `None` if dimensions cannot be determined.
    """
    ...


def get_svg_dimensions(svg: Path | bytes | str) -> tuple[int, int] | None:
    if isinstance(svg, Path):
        path = svg
        try:
            tree = ET.parse(path)
            root = tree.getroot()
            return _extract_dimensions_from_root(root)
        except OSError as ex:
            LOGGER.warning("Failed to open SVG file: %s", path, exc_info=ex)
            return None
        except ET.XMLSyntaxError as ex:
            LOGGER.warning("Failed to parse SVG file: %s", path, exc_info=ex)
            return None
        except SVGParseError as ex:
            LOGGER.warning("Failed to extract dimensions from SVG file: %s", path, exc_info=ex)
            return None
    else:
        data = svg
        try:
            root = ET.fromstring(data)
            return _extract_dimensions_from_root(root)
        except ET.XMLSyntaxError as ex:
            LOGGER.warning("Failed to parse SVG data", exc_info=ex)
            return None
        except SVGParseError as ex:
            LOGGER.warning("Failed to extract dimensions from SVG data", exc_info=ex)
            return None


def _serialize_svg_opening_tag(root: ElementType) -> str:
    """
    Serializes just the opening tag of an SVG element (without children or closing tag).

    :param root: The root SVG element.
    :returns: The opening tag string, e.g., '<svg width="100" height="200" ...>'.
    """

    # Build the opening tag from element name and attributes
    root_tag = root.tag
    if not isinstance(root_tag, str):
        raise SVGParseError("expected: tag names as `str`")
    tag_name = ET.QName(root_tag).localname
    parts = [f"<{tag_name}"]

    # Add namespace declarations (nsmap)
    for prefix, uri in root.nsmap.items():
        if prefix is None:
            parts.append(f' xmlns="{uri}"')
        else:
            parts.append(f' xmlns:{prefix}="{uri}"')

    # Add attributes
    for name, value in root.attrib.items():
        qname = ET.QName(name)

        # Handle namespaced attributes
        if qname.namespace:
            # Find prefix for this namespace
            prefix = None
            for p, u in root.nsmap.items():
                if u == qname.namespace and p is not None:
                    prefix = p
                    break
            if prefix:
                parts.append(f' {prefix}:{qname.localname}="{value}"')
            else:
                parts.append(f' {qname.localname}="{value}"')
        else:
            parts.append(f' {name}="{value}"')

    parts.append(">")
    return "".join(parts)


def fix_svg_dimensions(data: bytes) -> bytes:
    """
    Fixes SVG data by setting explicit width/height attributes based on viewBox.

    Mermaid generates SVGs with width="100%" which Confluence doesn't handle well.
    This function replaces percentage-based dimensions with explicit pixel values
    derived from the viewBox.

    Note: SVGs containing foreignObject elements are NOT modified, as Confluence
    has rendering issues with foreignObject when explicit dimensions are set.

    Uses lxml to parse and modify the root element's attributes, then replaces
    just the opening tag in the original document to preserve the rest exactly.

    :param data: The SVG content as bytes.
    :returns: The modified SVG content with explicit dimensions, or original data if modification fails.
    """

    # Skip SVGs with foreignObject - Confluence has issues rendering
    # foreignObject content when explicit width/height are set on the SVG
    if b"<foreignObject" in data:
        LOGGER.debug("Skipping dimension fix for SVG with foreignObject elements")
        return data

    # Parse the SVG to extract root element attributes
    root = ET.fromstring(data)

    # Verify it's an SVG element
    if not _check_svg(root):
        return data

    # Check if we need to fix (has width="100%" or similar percentage)
    width_attr = root.get("width")
    if width_attr != "100%":
        # Check if it already has a valid numeric width
        if width_attr is not None and _parse_svg_length(width_attr) is not None:
            return data  # Already has numeric width

    # Get viewBox dimensions
    viewbox_attr = root.get("viewBox")
    if not viewbox_attr:
        return data

    viewbox = _parse_viewbox(viewbox_attr)
    if viewbox is None:
        return data
    vb_width, vb_height = viewbox

    # Extract the original opening tag from the text
    svg_tag_match = re.search(rb"<svg\b[^>]*>", data)
    if not svg_tag_match:
        return data

    original_tag = svg_tag_match.group(0)

    # Modify the root element's attributes
    root.set("width", str(vb_width))

    # Set height if missing or if it's a percentage
    height_attr = root.get("height")
    if height_attr is None or height_attr == "100%":
        root.set("height", str(vb_height))

    # Serialize just the opening tag with modified attributes
    new_tag = _serialize_svg_opening_tag(root).encode("utf-8")

    # Replace the original opening tag with the new one
    return data.replace(original_tag, new_tag, 1)


_MEASURE_REGEXP = re.compile(r"^([+-]?(?:\d+\.?\d*|\.\d+))(%|px|pt|em|ex|in|cm|mm|pc)?$", re.IGNORECASE)


def _parse_svg_length(value: str) -> int | None:
    """
    Parses an SVG length value and converts it to pixels.

    Supports: px, pt, em, ex, in, cm, mm, pc, and unit-less values.
    For simplicity, assumes 96 DPI and 16px base font size.

    :param value: The SVG length string (e.g., "100", "100px", "10em").
    :returns: The length in pixels as an integer, or None if parsing fails.
    """

    if not value:
        return None

    value = value.strip()

    # Match number with optional unit
    match = _MEASURE_REGEXP.match(value)
    if not match:
        return None

    num_str, unit = match.groups()
    try:
        num = float(num_str)
    except ValueError:
        return None

    # Convert to pixels (assuming 96 DPI, 16px base font)
    match unit.lower() if unit else None:
        case None | "px":
            pixels = num
        case "pt":
            pixels = num * 96 / 72  # 1pt = 1/72 inch
        case "in":
            pixels = num * 96
        case "cm":
            pixels = num * 96 / 2.54
        case "mm":
            pixels = num * 96 / 25.4
        case "pc":
            pixels = num * 96 / 6  # 1pc = 12pt = 1/6 inch
        case "em":
            pixels = num * 16  # assume 16px base font
        case "ex":
            pixels = num * 8  # assume ex ≈ 0.5em
        case "%":
            # Percentage values can't be resolved without a container; skip
            return None
        case _:
            return None

    return int(round(pixels))


def _parse_viewbox(viewbox: str) -> tuple[int, int] | None:
    """
    Parses an SVG viewBox attribute and extracts width and height.

    :param viewbox: The viewBox string (e.g., "0 0 100 200").
    :returns: A tuple of (width, height) in pixels, or `None` if parsing fails.
    """

    if not viewbox:
        return None

    # viewBox format: "min-x min-y width height"
    # Values can be separated by whitespace and/or commas
    parts = re.split(r"\s*,\s*|\s+", viewbox.strip())
    if len(parts) != 4:
        return None

    try:
        width = int(round(float(parts[2])))
        height = int(round(float(parts[3])))
        return width, height
    except ValueError:
        return None


def fix_svg_get_dimensions(data: bytes) -> tuple[bytes, tuple[int, int] | None]:
    """
    Post-processes SVG diagram data by fixing dimensions and extracting metadata.

    This handles the common pattern for SVG diagrams:

    1. fixes SVG dimensions (converts percentage-based to explicit pixels), and
    2. extracts width/height from the SVG.

    :param data: Raw SVG data as bytes.
    :returns: Tuple of update raw data, image width, image height.
    """

    try:
        # fix SVG to have explicit width/height instead of percentages
        data = fix_svg_dimensions(data)

        # extract dimensions from the fixed SVG
        return data, get_svg_dimensions(data)
    except ET.XMLSyntaxError as ex:
        LOGGER.warning("Failed to parse SVG data", exc_info=ex)
        return data, None
    except SVGParseError as ex:
        LOGGER.warning("Failed to extract dimensions from SVG data", exc_info=ex)
        return data, None
