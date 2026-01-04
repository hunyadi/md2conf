"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import uuid
from pathlib import Path

import lxml.etree as ET
from cattrs import BaseValidationError

from md2conf.attachment import EmbeddedFileData, ImageData, attachment_name
from md2conf.compatibility import override, path_relative_to
from md2conf.csf import AC_ATTR, AC_ELEM
from md2conf.extension import MarketplaceExtension
from md2conf.formatting import ImageAttributes

from .config import MermaidConfigProperties
from .render import render_diagram
from .scanner import MermaidScanner

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]

LOGGER = logging.getLogger(__name__)


class MermaidExtension(MarketplaceExtension):
    @override
    def matches_image(self, absolute_path: Path) -> bool:
        return absolute_path.name.endswith((".mmd", ".mermaid"))

    @override
    def matches_fenced(self, language: str, content: str) -> bool:
        return language == "mermaid"

    def _extract_mermaid_config(self, content: str) -> MermaidConfigProperties | None:
        """Extract scale from Mermaid YAML front matter configuration."""

        try:
            properties = MermaidScanner().read(content)
            return properties.config
        except BaseValidationError as ex:
            LOGGER.warning("Failed to extract Mermaid properties: %s", ex)
            return None

    @override
    def transform_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        relative_path = path_relative_to(absolute_path, self.base_dir)
        if self.options.render:
            with open(absolute_path, "r", encoding="utf-8") as f:
                content = f.read()

            config = self._extract_mermaid_config(content)
            image_data = render_diagram(content, self.generator.options.output_format, config=config)
            return self.generator.transform_attached_data(image_data, attrs, relative_path)
        else:
            self.attachments.add_image(ImageData(absolute_path, attrs.alt))
            mermaid_filename = attachment_name(relative_path)
            return self._create_mermaid_embed(mermaid_filename)

    @override
    def transform_fenced(self, content: str) -> ElementType:
        if self.options.render:
            config = self._extract_mermaid_config(content)
            image_data = render_diagram(content, self.generator.options.output_format, config=config)
            return self.generator.transform_attached_data(image_data, ImageAttributes.EMPTY_BLOCK)
        else:
            mermaid_data = content.encode("utf-8")
            mermaid_hash = hashlib.md5(mermaid_data).hexdigest()
            mermaid_filename = attachment_name(f"embedded_{mermaid_hash}.mmd")
            self.attachments.add_embed(mermaid_filename, EmbeddedFileData(mermaid_data))
            return self._create_mermaid_embed(mermaid_filename)

    def _create_mermaid_embed(self, filename: str) -> ElementType:
        "A Mermaid diagram, linking to an attachment that captures the Mermaid source."

        local_id = str(uuid.uuid4())
        macro_id = str(uuid.uuid4())
        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "mermaid-cloud",
                AC_ATTR("schema-version"): "1",
                "data-layout": "default",
                AC_ATTR("local-id"): local_id,
                AC_ATTR("macro-id"): macro_id,
            },
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "filename"},
                filename,
            ),
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "toolbar"},
                "bottom",
            ),
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "zoom"},
                "fit",
            ),
            AC_ELEM("parameter", {AC_ATTR("name"): "revision"}, "1"),
        )
