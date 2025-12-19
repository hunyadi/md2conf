"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import subprocess
from typing import Sequence

LOGGER = logging.getLogger(__name__)


def render_diagram_subprocess(
    command: Sequence[str],
    source: str,
    diagram_type: str,
) -> bytes:
    """
    Executes a subprocess to render a diagram from source text.

    This function handles the common pattern of:
    - Executing a command with stdin/stdout/stderr pipes
    - Passing source as UTF-8 encoded input
    - Capturing binary output
    - Error handling with exit codes and stderr

    :param command: Full command with arguments to execute
    :param source: Diagram source code as string
    :param diagram_type: Human-readable diagram type name for error messages (e.g., "Mermaid", "PlantUML")
    :returns: Rendered diagram as bytes
    :raises RuntimeError: If the subprocess fails with non-zero exit code
    """

    LOGGER.debug("Executing: %s", " ".join(command))

    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stdin=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )
    stdout, stderr = proc.communicate(input=source.encode("utf-8"))

    if proc.returncode:
        messages = [
            f"failed to convert {diagram_type} diagram; "
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
