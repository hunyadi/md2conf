"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import subprocess
from typing import Sequence

LOGGER = logging.getLogger(__name__)


def execute_subprocess(command: Sequence[str], data: bytes, *, application: str | None = None) -> bytes:
    """
    Executes a subprocess, feeding input to stdin, and capturing output from stdout.

    This function handles the common pattern of:

    1. executing a command with stdin/stdout/stderr pipes,
    2. passing input data as binary (e.g. UTF-8 encoded),
    3. capturing binary output,
    4. error handling with exit codes and stderr.

    :param command: Full command with arguments to execute.
    :param data: Application input as `bytes`.
    :param application: Human-readable application name for error messages (e.g., "Mermaid", "PlantUML").
    :returns: Application output as `bytes`.
    :raises RuntimeError: If the subprocess fails with non-zero exit code.
    """

    LOGGER.debug("Executing: %s", " ".join(command))

    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate(input=data)

    if proc.returncode:
        messages = [f"failed to execute {application or 'application'}; exit code: {proc.returncode}"]
        console_output = stdout.decode("utf-8")
        if console_output:
            messages.append(f"output:\n{console_output}")
        console_error = stderr.decode("utf-8")
        if console_error:
            messages.append(f"error:\n{console_error}")
        raise RuntimeError("\n".join(messages))

    return stdout
