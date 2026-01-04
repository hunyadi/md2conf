"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import base64
import logging
import os
import shlex
import shutil
import zlib
from pathlib import Path
from typing import Literal
from urllib.parse import quote

import md2conf
from md2conf.external import execute_subprocess

from .config import PlantUMLConfigProperties

LOGGER = logging.getLogger(__name__)


def _get_plantuml_jar_path() -> Path:
    """
    Returns the expected path to `plantuml.jar`.

    Priority:

    1. value of environment variable `PLANTUML_JAR`
    2. path to `plantuml.jar` if found in parent directory of module `md2conf`
    3. path to `plantuml.jar` if found in current directory
    """

    # check environment variable
    env_jar = os.environ.get("PLANTUML_JAR")
    if env_jar:
        return Path(env_jar)

    # check parent directory of module `md2conf`
    base_path = Path(md2conf.__file__).parent.parent
    jar_path = base_path / "plantuml.jar"
    if jar_path.exists():
        return jar_path

    # check current directory
    return Path("plantuml.jar")


def _get_plantuml_command() -> list[str]:
    """
    Returns the command to invoke PlantUML.

    :raises RuntimeError: Raised when `plantuml.jar` is not found.
    """

    env_cmd = os.environ.get("PLANTUML_CMD")
    if env_cmd:
        LOGGER.debug(f"Using PlantUML command: {env_cmd}")
        return shlex.split(env_cmd)

    jar_path = _get_plantuml_jar_path()
    if jar_path.is_file():
        LOGGER.debug(f"Using PlantUML JAR at: {jar_path}")
        return ["java", "-jar", str(jar_path)]

    # JAR not found - fail with helpful message
    raise RuntimeError(
        "PlantUML JAR not found. Download `plantuml.jar` from https://github.com/plantuml/plantuml/releases and set the PLANTUML_JAR environment variable."
    )


def has_plantuml() -> bool:
    """True if PlantUML JAR is available and Java is installed."""

    jar_path = _get_plantuml_jar_path()

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

    # Build command for PlantUML with pipe mode
    # -pipe: read from stdin and write to stdout
    # -t<format>: output format (png or svg)
    # -charset utf-8: ensure UTF-8 encoding
    cmd = _get_plantuml_command()
    cmd.extend(
        [
            "-pipe",
            f"-t{output_format}",
            "-charset",
            "utf-8",
        ]
    )

    # Add scale if specified
    if config.scale is not None:
        cmd.extend(["-scale", str(config.scale)])

    return execute_subprocess(cmd, source.encode("utf-8"), application="PlantUML")


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
