"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

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
from md2conf.formatting import FormattingContext, ImageAttributes
from md2conf.svg import fix_svg_dimensions, get_svg_dimensions_from_bytes

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
            image_data = render_diagram(content, self.options.output_format, config=config)

            # Post-process SVG and update attributes
            image_data, attrs = self._post_process_svg_diagram(image_data, attrs)

            image_filename = attachment_name(relative_path.with_suffix(f".{self.options.output_format}"))
            self.attachments.add_embed(image_filename, EmbeddedFileData(image_data, attrs.alt))

            return self.generator.create_attached_image(image_filename, attrs)
        else:
            self.attachments.add_image(ImageData(absolute_path, attrs.alt))
            mermaid_filename = attachment_name(relative_path)
            return self._create_mermaid_embed(mermaid_filename)

    @override
    def transform_fenced(self, content: str) -> ElementType:
        if self.options.render:
            config = self._extract_mermaid_config(content)
            image_data = render_diagram(content, self.options.output_format, config=config)

            # Extract dimensions and fix SVG if that's the output format
            attrs = ImageAttributes.EMPTY_BLOCK
            if self.options.output_format == "svg":
                # Fix SVG to have explicit width/height instead of percentages
                image_data = fix_svg_dimensions(image_data)

                svg_width, svg_height = get_svg_dimensions_from_bytes(image_data)
                if svg_width is not None or svg_height is not None:
                    attrs = ImageAttributes(
                        context=FormattingContext.BLOCK,
                        width=svg_width,
                        height=svg_height,
                        alt=None,
                        title=None,
                        caption=None,
                        alignment=self.options.alignment,
                    )

            image_hash = hashlib.md5(image_data).hexdigest()
            image_filename = attachment_name(f"embedded_{image_hash}.{self.options.output_format}")
            self.attachments.add_embed(image_filename, EmbeddedFileData(image_data))

            return self.generator.create_attached_image(image_filename, attrs)
        else:
            mermaid_data = content.encode("utf-8")
            mermaid_hash = hashlib.md5(mermaid_data).hexdigest()
            mermaid_filename = attachment_name(f"embedded_{mermaid_hash}.mmd")
            self.attachments.add_embed(mermaid_filename, EmbeddedFileData(mermaid_data))
            return self._create_mermaid_embed(mermaid_filename)

    def _post_process_svg_diagram(self, image_data: bytes, base_attrs: ImageAttributes) -> tuple[bytes, ImageAttributes]:
        """
        Post-processes SVG diagram data by fixing dimensions and extracting metadata.

        This handles the common pattern for SVG diagrams:
        1. Fixes SVG dimensions (converts percentage-based to explicit pixels)
        2. Extracts width/height from the SVG
        3. Creates updated ImageAttributes with extracted dimensions and calculated display width

        :param image_data: Raw SVG data as bytes
        :param base_attrs: Base attributes to use if dimensions cannot be extracted
        :returns: Tuple of (processed_image_data, updated_attributes)
        """

        if self.options.output_format != "svg":
            return image_data, base_attrs

        # Fix SVG to have explicit width/height instead of percentages
        image_data = fix_svg_dimensions(image_data)

        # Extract dimensions from the fixed SVG
        svg_width, svg_height = get_svg_dimensions_from_bytes(image_data)

        # Only update attributes if we successfully extracted dimensions
        # and the base attributes don't already have explicit dimensions
        if (svg_width is not None or svg_height is not None) and (base_attrs.width is None and base_attrs.height is None):
            attrs = ImageAttributes(
                context=base_attrs.context,
                width=svg_width,
                height=svg_height,
                alt=base_attrs.alt,
                title=base_attrs.title,
                caption=base_attrs.caption,
                alignment=base_attrs.alignment,
            )
            return image_data, attrs

        return image_data, base_attrs

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
