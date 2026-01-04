"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from abc import abstractmethod
from dataclasses import dataclass
from pathlib import Path

import lxml.etree as ET

from .attachment import AttachmentCatalog
from .formatting import ImageAttributes
from .image import ImageGenerator

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]


@dataclass
class ExtensionOptions:
    """
    Customizes how Confluence content is generated for a drawing or diagram.

    :param render: Whether to pre-render the drawing or diagram into a PNG/SVG image.
    """

    render: bool


class MarketplaceExtension:
    """
    Base class for integrating third-party Atlassian Marketplace extensions.

    Derive from this class to generate custom Confluence Storage Format output for Markdown image references and fenced code blocks.
    """

    generator: ImageGenerator
    options: ExtensionOptions

    def __init__(self, generator: ImageGenerator, options: ExtensionOptions) -> None:
        self.generator = generator
        self.options = options

    @property
    def base_dir(self) -> Path:
        "Base directory for resolving relative links."

        return self.generator.base_dir

    @property
    def attachments(self) -> AttachmentCatalog:
        "Maintains a list of files and binary data to be uploaded to Confluence as attachments."

        return self.generator.attachments

    @abstractmethod
    def matches_image(self, absolute_path: Path) -> bool:
        "True if the extension is able to process the external file."
        ...

    @abstractmethod
    def matches_fenced(self, language: str, content: str) -> bool:
        "True if the extension can process the fenced code block."
        ...

    @abstractmethod
    def transform_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for a drawing or diagram linked as an image."
        ...

    @abstractmethod
    def transform_fenced(self, content: str) -> ElementType:
        "Emits Confluence Storage Format XHTML for a drawing or diagram defined in a fenced code block."

        ...
