import os.path
import subprocess
from typing import Literal


def render(source: str, output_format: Literal["png", "svg"] = "png") -> bytes:
    "Generates a PNG or SVG image from a Mermaid diagram source."

    filename = f"tmp_mermaid.{output_format}"
    try:
        cmd = [
            "mmdc",
            "--input",
            "-",
            "--output",
            filename,
            "--outputFormat",
            output_format,
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
        )
        proc.communicate(input=source.encode("utf-8"))
        if proc.returncode:
            raise RuntimeError(
                f"failed to convert Mermaid diagram; exit code: {proc.returncode}"
            )
        with open(filename, "rb") as image:
            return image.read()

    finally:
        if os.path.exists(filename):
            os.remove(filename)
