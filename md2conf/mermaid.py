"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
import os.path
import shutil
import subprocess
from typing import Literal

LOGGER = logging.getLogger(__name__)


def is_docker() -> bool:
    "True if the application is running in a Docker container."

    return (
        os.environ.get("CHROME_BIN") == "/usr/bin/chromium-browser"
        and os.environ.get("PUPPETEER_SKIP_DOWNLOAD") == "true"
    )


def get_mmdc() -> str:
    "Path to the Mermaid diagram converter."

    if is_docker():
        full_path = "/home/md2conf/node_modules/.bin/mmdc"
        if os.path.exists(full_path):
            return full_path
        else:
            return "mmdc"
    elif os.name == "nt":
        return "mmdc.cmd"
    else:
        return "mmdc"


def has_mmdc() -> bool:
    "True if Mermaid diagram converter is available on the OS."

    executable = get_mmdc()
    return shutil.which(executable) is not None


def render_diagram(source: str, output_format: Literal["png", "svg"] = "png") -> bytes:
    "Generates a PNG or SVG image from a Mermaid diagram source."

    filename = f"tmp_mermaid.{output_format}"

    cmd = [
        get_mmdc(),
        "--input",
        "-",
        "--output",
        filename,
        "--outputFormat",
        output_format,
        "--backgroundColor",
        "transparent",
        "--scale",
        "2",
    ]
    root = os.path.dirname(__file__)
    if is_docker():
        cmd.extend(["-p", os.path.join(root, "puppeteer-config.json")])
    LOGGER.debug("Executing: %s", " ".join(cmd))
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        stdout, stderr = proc.communicate(input=source.encode("utf-8"))
        if proc.returncode:
            raise RuntimeError(
                f"failed to convert Mermaid diagram; exit code: {proc.returncode}, "
                f"output:\n{stdout.decode('utf-8')}\n{stderr.decode('utf-8')}"
            )
        with open(filename, "rb") as image:
            return image.read()

    finally:
        if os.path.exists(filename):
            os.remove(filename)
