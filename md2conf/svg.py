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

        # Handle namespaced and non-namespaced SVG
        if root.tag != f"{{{SVG_NAMESPACE}}}svg" and root.tag != "svg":
            LOGGER.warning("SVG file %s does not have an <svg> root element", path)
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

    except ET.XMLSyntaxError as ex:
        LOGGER.warning("Failed to parse SVG file %s: %s", path, ex)
        return None, None
    except Exception as ex:
        LOGGER.warning("Unexpected error reading SVG dimensions from %s: %s", path, ex)
        return None, None


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
