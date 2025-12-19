"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import Literal

LOGGER = logging.getLogger(__name__)


@dataclass
class PlantUMLConfigProperties:
    """
    Configuration options for rendering PlantUML diagrams.

    :param scale: Scaling factor for the rendered diagram.
    """

    scale: float | None = None


def get_plantuml() -> str:
    "Path to the PlantUML command-line tool."

    # Check for plantuml.sh first (custom wrapper), then plantuml
    for cmd in ["plantuml.sh", "plantuml"]:
        if shutil.which(cmd):
            return cmd
    return "plantuml"


def has_plantuml() -> bool:
    "True if PlantUML command-line tool is available on the OS."

    executable = get_plantuml()
    return shutil.which(executable) is not None


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
    cmd = [
        get_plantuml(),
        "-pipe",
        f"-t{output_format}",
        "-charset",
        "utf-8",
    ]

    # Add scale if specified
    if config.scale is not None:
        cmd.extend(["-scale", str(config.scale)])

    LOGGER.debug("Executing: %s", " ".join(cmd))

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    stdout, stderr = proc.communicate(input=source.encode("utf-8"))
    if proc.returncode:
        messages = [
            f"failed to convert PlantUML diagram; "
            f"exit code: {proc.returncode}"
        ]
        console_output = stdout.decode("utf-8")
        if console_output:
            messages.append(f"output:\n{console_output}")
        console_error = stderr.decode("utf-8")
        if console_error:
            messages.append(f"error:\n{console_error}")
        raise RuntimeError("\n".join(messages))

    return stdout
