"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass


@dataclass
class MermaidConfigProperties:
    """
    Configuration options for rendering Mermaid diagrams.

    :param scale: Scaling factor for the rendered diagram.
    """

    scale: float | None = None
