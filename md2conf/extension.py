"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass
from pathlib import Path

from .attachment import AttachmentCatalog
from .image import ImageGenerator
from .options_converter import MarketplaceExtension


class ExtensionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExtensionOptions:
    """
    Customizes how Confluence content is generated for a drawing or diagram.

    :param render: Whether to pre-render the drawing or diagram into a PNG/SVG image.
    """

    render: bool


class DiagramExtension(MarketplaceExtension):
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
