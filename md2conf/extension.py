"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, overload

from .attachment import AttachmentCatalog
from .formatting import ImageAttributes
from .xml import ElementType


class ExtensionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ImageGeneratorOptions:
    """
    Configures how images are pre-rendered and what Confluence Storage Format output they produce.

    :param output_format: Target image format for diagrams.
    :param prefer_raster: Whether to choose PNG files over SVG files when available.
    :param max_width: Maximum display width for images [px]. Wider images are scaled down for page display. Original size kept for full-size viewing.
    """

    output_format: Literal["png", "svg"]
    prefer_raster: bool
    max_width: int | None


class ImageGenerator(ABC):
    base_dir: Path
    attachments: AttachmentCatalog
    options: ImageGeneratorOptions

    def __init__(self, base_dir: Path, attachments: AttachmentCatalog, options: ImageGeneratorOptions) -> None:
        self.base_dir = base_dir
        self.attachments = attachments
        self.options = options

    @abstractmethod
    def transform_attached_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for an attached raster or vector image."
        ...

    @overload
    def transform_attached_data(self, image_data: bytes, attrs: ImageAttributes, *, relative_path: Path, image_type: str = "embedded") -> ElementType: ...

    @overload
    def transform_attached_data(self, image_data: bytes, attrs: ImageAttributes, *, content: str, image_type: str = "embedded") -> ElementType: ...

    @abstractmethod
    def transform_attached_data(
        self, image_data: bytes, attrs: ImageAttributes, relative_path: Path | None = None, content: str | None = None, *, image_type: str = "embedded"
    ) -> ElementType:
        "Emits Confluence Storage Format XHTML for an attached raster or vector image."
        ...


@dataclass(frozen=True)
class ExtensionOptions:
    """
    Customizes how Confluence content is generated for a drawing or diagram.

    :param render: Whether to pre-render the drawing or diagram into a PNG/SVG image.
    """

    render: bool


class MarketplaceExtension(ABC):
    """
    Base class for integrating third-party Atlassian Marketplace extensions.

    Derive from this class to generate custom Confluence Storage Format output for Markdown image references and fenced code blocks.
    """

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


class MarketplaceExtensionFactory(ABC):
    @abstractmethod
    def create(self, generator: ImageGenerator, options: ExtensionOptions) -> MarketplaceExtension:
        "Creates an instance for integrating a third-party Atlassian Marketplace extension."
        ...
