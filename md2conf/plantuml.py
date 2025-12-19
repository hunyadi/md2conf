"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .diagram import render_diagram_subprocess

LOGGER = logging.getLogger(__name__)


@dataclass
class PlantUMLConfigProperties:
    """
    Configuration options for rendering PlantUML diagrams.

    :param scale: Scaling factor for the rendered diagram.
    """

    scale: float | None = None


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


def get_plantuml_command() -> list[str]:
    """
    Returns the command to invoke PlantUML.

    Raises RuntimeError if plantuml.jar is not found.
    """
    jar_path = get_plantuml_jar_path()

    if jar_path.is_file():
        # Direct JAR invocation
        LOGGER.debug(f"Using PlantUML JAR at: {jar_path}")
        return ["java", "-jar", str(jar_path)]

    # JAR not found - fail with helpful message
    raise RuntimeError(
        f"PlantUML JAR not found at {jar_path}. "
        f"Please download plantuml.jar from https://github.com/plantuml/plantuml/releases "
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

    # Build command for PlantUML with pipe mode
    # -pipe: read from stdin and write to stdout
    # -t<format>: output format (png or svg)
    # -charset utf-8: ensure UTF-8 encoding
    cmd = get_plantuml_command()
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

    return render_diagram_subprocess(cmd, source, "PlantUML")
