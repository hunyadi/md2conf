"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import lxml.etree as ET

from .attachment import AttachmentCatalog
from .formatting import ImageAlignment, ImageAttributes
from .image import ImageGenerator

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]


@dataclass
class ExtensionOptions:
    """
    Customizes how Confluence content is generated for a drawing or diagram.

    :param render: Whether to pre-render the drawing or diagram into a PNG/SVG image.
    :param output_format: Target image format for diagrams.
    :param alignment: Alignment for block-level images and formulas.
    """

    render: bool
    output_format: Literal["png", "svg"]
    alignment: ImageAlignment


class MarketplaceExtension:
    base_dir: Path
    attachments: AttachmentCatalog
    generator: ImageGenerator
    options: ExtensionOptions

    def __init__(self, base_dir: Path, attachments: AttachmentCatalog, generator: ImageGenerator, options: ExtensionOptions) -> None:
        self.base_dir = base_dir
        self.attachments = attachments
        self.generator = generator
        self.options = options

    @abstractmethod
    def transform_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for a drawing or diagram linked as an image."
        ...

    @abstractmethod
    def transform_fenced(self, content: str) -> ElementType:
        "Emits Confluence Storage Format XHTML for a drawing or diagram defined in a fenced code block."

        ...
