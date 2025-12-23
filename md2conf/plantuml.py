"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import base64
import logging
import os
import shutil
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from .diagram import render_diagram_subprocess

LOGGER = logging.getLogger(__name__)


@dataclass
class PlantUMLConfigProperties:
    """
    Configuration options for rendering PlantUML diagrams.

    :param scale: Scaling factor for the rendered diagram.
    :param include_path: Include path for resolving !include directives
        (sets plantuml.include.path Java property).
    :param include_file: File to pre-include before processing diagram
        (uses -I flag).
    :param theme: Built-in PlantUML theme name (uses --theme flag).
    """

    scale: float | None = None
    include_path: str | None = None
    include_file: str | None = None
    theme: str | None = None


def get_base_path() -> Path:
    """
    Returns the base path for md2conf resources.

    Priority:
    1. MD2CONF_BASE_PATH environment variable
    2. Directory containing the md2conf package
    """
    # Check environment variable first
    env_base = os.environ.get("MD2CONF_BASE_PATH")
    if env_base:
        return Path(env_base)

    # Default: directory containing the md2conf package
    # __file__ points to md2conf/plantuml.py
    # Parent is md2conf/, parent.parent is project root
    return Path(__file__).parent.parent


def get_plantuml_jar_path() -> Path:
    """
    Returns the expected path to plantuml.jar.

    Priority:
    1. PLANTUML_JAR environment variable (explicit override)
    2. {base_path}/plantuml.jar (default)
    """
    # Check environment variable first
    env_jar = os.environ.get("PLANTUML_JAR")
    if env_jar:
        return Path(env_jar)

    # Default: {base_path}/plantuml.jar
    return get_base_path() / "plantuml.jar"


def get_plantuml_command(include_path: str | None = None) -> list[str]:
    """
    Returns the command to invoke PlantUML.

    :param include_path: Include path for resolving !include directives.
    Raises RuntimeError if plantuml.jar is not found.
    """
    jar_path = get_plantuml_jar_path()

    if jar_path.is_file():
        # Direct JAR invocation
        LOGGER.debug(f"Using PlantUML JAR at: {jar_path}")
        cmd = ["java"]

        # Add include path Java property if specified
        if include_path:
            cmd.extend(["-Dplantuml.include.path=.:" + include_path])

        cmd.extend(["-jar", str(jar_path)])
        return cmd

    # JAR not found - fail with helpful message
    raise RuntimeError(
        f"PlantUML JAR not found. Download `plantuml.jar` from https://github.com/plantuml/plantuml/releases "
        f"and place it at {jar_path}, or set the PLANTUML_JAR environment variable to point to it."
    )


def has_plantuml() -> bool:
    """True if PlantUML JAR is available and Java is installed."""

    jar_path = get_plantuml_jar_path()

    # Check if we have JAR file and Java is available
    return jar_path.is_file() and shutil.which("java") is not None


def render_diagram(
    source: str,
    output_format: Literal["png", "svg"] = "png",
    config: PlantUMLConfigProperties | None = None,
) -> bytes:
    "Generates a PNG or SVG image from a PlantUML diagram source."

    if config is None:
        config = PlantUMLConfigProperties()

    LOGGER.info(
        "Rendering PlantUML diagram: format=%s, theme=%s, include_path=%s, include_file=%s, scale=%s",
        output_format,
        config.theme,
        config.include_path,
        config.include_file,
        config.scale,
    )

    # Build command for PlantUML with pipe mode
    # -pipe: read from stdin and write to stdout
    # -t<format>: output format (png or svg)
    # -charset utf-8: ensure UTF-8 encoding
    cmd = get_plantuml_command(include_path=config.include_path)
    cmd.extend(
        [
            "-pipe",
            f"-t{output_format}",
            "-charset",
            "utf-8",
        ]
    )

    # Add theme if specified
    if config.theme is not None:
        cmd.extend(["--theme", config.theme])

    # Add include file if specified (resolve relative to include_path)
    if config.include_file is not None:
        if config.include_path:
            include_path_obj = Path(config.include_path)
        else:
            include_path_obj = Path.cwd()
        include_file_path = include_path_obj / config.include_file
        cmd.extend(["-I", str(include_file_path)])

    # Add scale if specified
    if config.scale is not None:
        cmd.extend(["-scale", str(config.scale)])

    return render_diagram_subprocess(cmd, source, "PlantUML")


def compress_plantuml_data(source: str) -> str:
    """
    Compress PlantUML source for embedding in plantumlcloud macro.

    Implements the encoding used by PlantUML Diagrams for Confluence:

    1. URI encode the source
    2. Deflate with raw deflate (zlib)
    3. Base64 encode

    :param source: PlantUML diagram source code.
    :returns: Compressed and encoded data suitable for macro data parameter.
    :see: https://stratus-addons.atlassian.net/wiki/spaces/PDFC/pages/1839333377
    """

    # Step 1: URI encode
    encoded = quote(source, safe="")

    # Step 2: Deflate with raw deflate (remove zlib header/trailer)
    # zlib.compress() adds 2-byte header and 4-byte trailer
    deflated = zlib.compress(encoded.encode("utf-8"))[2:-4]

    # Step 3: Base64 encode
    return base64.b64encode(deflated).decode("ascii")
