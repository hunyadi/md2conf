"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
import os.path
import shlex
from typing import Literal

from md2conf.external import cached_which, execute_subprocess

from .config import MermaidConfigProperties

LOGGER = logging.getLogger(__name__)


def _is_docker() -> bool:
    "True if the application is running in a Docker container."

    return os.environ.get("CHROME_BIN") == "/usr/bin/chromium-browser" and os.environ.get("PUPPETEER_SKIP_DOWNLOAD") == "true"


def get_mmdc() -> str:
    "Path to the Mermaid diagram converter."

    if _is_docker():
        full_path = "/home/md2conf/node_modules/.bin/mmdc"
        if os.path.exists(full_path):
            return full_path
        else:
            return "mmdc"
    elif os.name == "nt":
        return "mmdc.cmd"
    else:
        return "mmdc"

def _get_mmdc_command() -> list[str]:
    """
    Returns the command to invoke Mermaid diagram converter.

    :raises RuntimeError: Raised when `Mermaid CLI` is not found.
    """

    env_cmd = os.environ.get("MERMAID_CMD")
    if env_cmd:
        LOGGER.debug(f"Using Mermaid command: {env_cmd}")
        return shlex.split(env_cmd)

    executable = get_mmdc()
    if cached_which(executable) is None:
        raise RuntimeError("Mermaid CLI not found. Install Mermaid CLI from <https://github.com/mermaid-js/mermaid-cli>.")

    cmd = [executable]
    if _is_docker():
        root = os.path.dirname(__file__)
        cmd.extend(["-p", os.path.join(root, "puppeteer-config.json")])
    return cmd


def has_mmdc() -> bool:
    "True if Mermaid diagram converter is available on the OS."

    executable = get_mmdc()
    return cached_which(executable) is not None


def render_diagram(source: str, output_format: Literal["png", "svg"] = "png", config: MermaidConfigProperties | None = None) -> bytes:
    "Generates a PNG or SVG image from a Mermaid diagram source."

    if config is None:
        config = MermaidConfigProperties()

    cmd = _get_mmdc_command()
    cmd.extend(
        [
            "--input",
            "-",
            "--output",
            "-",
            "--outputFormat",
            output_format,
            "--backgroundColor",
            "transparent",
            "--scale",
            str(config.scale or 2),
        ]
    )
    return execute_subprocess(cmd, source.encode(), application="Mermaid")
