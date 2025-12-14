"""
SVG dimension extraction utilities.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import re
from pathlib import Path

import lxml.etree as ET

LOGGER = logging.getLogger(__name__)

SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def _extract_dimensions_from_root(root: ET._Element) -> tuple[int | None, int | None]:
    """
    Extracts width and height from an SVG root element.

    Attempts to read dimensions from:
    1. Explicit width/height attributes on the root <svg> element
    2. The viewBox attribute if width/height are not specified

    :param root: The root element of the SVG document.
    :returns: A tuple of (width, height) in pixels, or (None, None) if dimensions cannot be determined.
    """

    # Handle namespaced and non-namespaced SVG
    if root.tag != f"{{{SVG_NAMESPACE}}}svg" and root.tag != "svg":
        return None, None

    width_attr = root.get("width")
    height_attr = root.get("height")

    width = _parse_svg_length(width_attr) if width_attr else None
    height = _parse_svg_length(height_attr) if height_attr else None

    # If width/height not specified, try to derive from viewBox
    if width is None or height is None:
        viewbox = root.get("viewBox")
        if viewbox:
            vb_width, vb_height = _parse_viewbox(viewbox)
            if width is None:
                width = vb_width
            if height is None:
                height = vb_height

    return width, height


def get_svg_dimensions(path: Path) -> tuple[int | None, int | None]:
    """
    Extracts width and height from an SVG file.

    Attempts to read dimensions from:
    1. Explicit width/height attributes on the root <svg> element
    2. The viewBox attribute if width/height are not specified

    :param path: Path to the SVG file.
    :returns: A tuple of (width, height) in pixels, or (None, None) if dimensions cannot be determined.
    """

    try:
        tree = ET.parse(str(path))
        root = tree.getroot()
        width, height = _extract_dimensions_from_root(root)
        if width is None and height is None:
            LOGGER.warning("SVG file %s does not have an <svg> root element", path)
        return width, height

    except ET.XMLSyntaxError as ex:
        LOGGER.warning("Failed to parse SVG file %s: %s", path, ex)
        return None, None
    except Exception as ex:
        LOGGER.warning("Unexpected error reading SVG dimensions from %s: %s", path, ex)
        return None, None


def get_svg_dimensions_from_bytes(data: bytes) -> tuple[int | None, int | None]:
    """
    Extracts width and height from SVG data in memory.

    Attempts to read dimensions from:
    1. Explicit width/height attributes on the root <svg> element
    2. The viewBox attribute if width/height are not specified

    :param data: The SVG content as bytes.
    :returns: A tuple of (width, height) in pixels, or (None, None) if dimensions cannot be determined.
    """

    try:
        root = ET.fromstring(data)
        return _extract_dimensions_from_root(root)

    except ET.XMLSyntaxError as ex:
        LOGGER.warning("Failed to parse SVG data: %s", ex)
        return None, None
    except Exception as ex:
        LOGGER.warning("Unexpected error reading SVG dimensions from data: %s", ex)
        return None, None


def fix_svg_dimensions(data: bytes) -> bytes:
    """
    Fixes SVG data by setting explicit width/height attributes based on viewBox.

    Mermaid generates SVGs with width="100%" which Confluence doesn't handle well.
    This function replaces percentage-based dimensions with explicit pixel values
    derived from the viewBox.

    Note: SVGs containing foreignObject elements are NOT modified, as Confluence
    has rendering issues with foreignObject when explicit dimensions are set.

    Uses regex replacement to preserve the original SVG structure exactly,
    avoiding potential issues from XML re-serialization.

    :param data: The SVG content as bytes.
    :returns: The modified SVG content with explicit dimensions, or original data if modification fails.
    """

    try:
        text = data.decode("utf-8")

        # Skip SVGs with foreignObject - Confluence has issues rendering
        # foreignObject content when explicit width/height are set on the SVG
        if "<foreignObject" in text:
            LOGGER.debug("Skipping dimension fix for SVG with foreignObject elements")
            return data

        # Extract the SVG opening tag
        svg_tag_match = re.search(r"<svg\b[^>]+>", text)
        if not svg_tag_match:
            return data

        svg_tag = svg_tag_match.group(0)

        # Check if we need to fix (has width="100%" or similar percentage)
        if 'width="100%"' not in svg_tag:
            # Check if it already has a valid numeric width
            if re.search(r'\swidth="\d+(?:\.\d+)?"', svg_tag):
                return data  # Already has numeric width

        # Extract viewBox dimensions
        viewbox_match = re.search(r'viewBox="([^"]+)"', svg_tag)
        if not viewbox_match:
            return data

        vb_width, vb_height = _parse_viewbox(viewbox_match.group(1))
        if vb_width is None or vb_height is None:
            return data

        # Replace width="100%" with explicit width
        text = re.sub(r'(<svg[^>]*)\swidth="100%"', rf'\1 width="{vb_width}"', text)

        # Re-extract the SVG tag after width replacement
        svg_tag_match = re.search(r"<svg[^>]+>", text)
        svg_tag = svg_tag_match.group(0) if svg_tag_match else ""

        # Add height attribute if missing from SVG tag, or replace percentage height
        if not re.search(r'\sheight="', svg_tag):
            # Add height after width in SVG tag only
            text = re.sub(r'(<svg[^>]*\swidth="\d+(?:\.\d+)?")', rf'\1 height="{vb_height}"', text)
        elif 'height="100%"' in svg_tag:
            # Replace percentage height in SVG tag
            def replace_svg_height(m: re.Match[str]) -> str:
                return re.sub(r'height="100%"', f'height="{vb_height}"', m.group(0))

            text = re.sub(r"<svg[^>]+>", replace_svg_height, text, count=1)

        return text.encode("utf-8")

    except Exception as ex:
        LOGGER.warning("Unexpected error fixing SVG dimensions: %s", ex)
        return data


def _parse_svg_length(value: str) -> int | None:
    """
    Parses an SVG length value and converts it to pixels.

    Supports: px, pt, em, ex, in, cm, mm, pc, and unitless values.
    For simplicity, assumes 96 DPI and 16px base font size.

    :param value: The SVG length string (e.g., "100", "100px", "10em").
    :returns: The length in pixels as an integer, or None if parsing fails.
    """

    if not value:
        return None

    value = value.strip()

    # Match number with optional unit
    match = re.match(r"^([+-]?(?:\d+\.?\d*|\.\d+))(%|px|pt|em|ex|in|cm|mm|pc)?$", value, re.IGNORECASE)
    if not match:
        return None

    num_str, unit = match.groups()
    try:
        num = float(num_str)
    except ValueError:
        return None

    # Convert to pixels (assuming 96 DPI, 16px base font)
    if unit is None or unit.lower() == "px":
        pixels = num
    elif unit.lower() == "pt":
        pixels = num * 96 / 72  # 1pt = 1/72 inch
    elif unit.lower() == "in":
        pixels = num * 96
    elif unit.lower() == "cm":
        pixels = num * 96 / 2.54
    elif unit.lower() == "mm":
        pixels = num * 96 / 25.4
    elif unit.lower() == "pc":
        pixels = num * 96 / 6  # 1pc = 12pt = 1/6 inch
    elif unit.lower() == "em":
        pixels = num * 16  # assume 16px base font
    elif unit.lower() == "ex":
        pixels = num * 8  # assume ex ≈ 0.5em
    elif unit == "%":
        # Percentage values can't be resolved without a container; skip
        return None
    else:
        return None

    return int(round(pixels))


def _parse_viewbox(viewbox: str) -> tuple[int | None, int | None]:
    """
    Parses an SVG viewBox attribute and extracts width and height.

    :param viewbox: The viewBox string (e.g., "0 0 100 200").
    :returns: A tuple of (width, height) in pixels, or (None, None) if parsing fails.
    """

    if not viewbox:
        return None, None

    # viewBox format: "min-x min-y width height"
    # Values can be separated by whitespace and/or commas
    parts = re.split(r"[\s,]+", viewbox.strip())
    if len(parts) != 4:
        return None, None

    try:
        width = int(round(float(parts[2])))
        height = int(round(float(parts[3])))
        return width, height
    except ValueError:
        return None, None
