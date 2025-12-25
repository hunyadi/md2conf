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
from md2conf.csf import AC_ATTR, AC_ELEM
from md2conf.extension import MarketplaceExtension
from md2conf.extra import override, path_relative_to
from md2conf.formatting import ImageAttributes
from md2conf.png import extract_png_dimensions
from md2conf.svg import get_svg_dimensions_from_bytes

from .config import PlantUMLConfigProperties
from .render import compress_plantuml_data, has_plantuml, render_diagram
from .scanner import PlantUMLScanner

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]

LOGGER = logging.getLogger(__name__)


class PlantUMLExtension(MarketplaceExtension):
    def _extract_plantuml_config(self, content: str) -> PlantUMLConfigProperties | None:
        "Extract config from PlantUML YAML front matter configuration."

        try:
            properties = PlantUMLScanner().read(content)
            return properties.config
        except BaseValidationError as ex:
            LOGGER.warning("Failed to extract PlantUML properties: %s", ex)
            return None

    @override
    def transform_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        relative_path = path_relative_to(absolute_path, self.base_dir)

        # read PlantUML source
        with open(absolute_path, "r", encoding="utf-8") as f:
            content = f.read()

        return self._transform_plantuml(content, attrs, relative_path)

    @override
    def transform_fenced(self, content: str) -> ElementType:
        return self._transform_plantuml(content, ImageAttributes.EMPTY_BLOCK)

    def _transform_plantuml(self, content: str, attrs: ImageAttributes, relative_path: Path | None = None) -> ElementType:
        """
        Emits Confluence Storage Format XHTML for a PlantUML diagram read from an external file or defined in a fenced code block.

        When `render_plantuml` is enabled, renders as an image attachment. Otherwise, uses the macro `plantumlcloud`
        with embedded SVG and compressed source.
        """

        if self.options.render:
            # render diagram as image file (PNG or SVG based on diagram output format)
            config = self._extract_plantuml_config(content)
            image_data = render_diagram(content, self.options.output_format, config=config)

            # extract dimensions and update attributes based on format
            width: int | None
            height: int | None
            match self.options.output_format:
                case "svg":
                    width, height = get_svg_dimensions_from_bytes(image_data)
                case "png":
                    width, height = extract_png_dimensions(data=image_data)

            if width is not None or height is not None:
                attrs = ImageAttributes(
                    context=attrs.context,
                    width=width,
                    height=height,
                    alt=attrs.alt,
                    title=attrs.title,
                    caption=attrs.caption,
                    alignment=attrs.alignment,
                )

            # generate filename and add as attachment
            if relative_path is not None:
                image_filename = attachment_name(relative_path.with_suffix(f".{self.options.output_format}"))
                self.attachments.add_embed(image_filename, EmbeddedFileData(image_data, attrs.alt))
            else:
                image_hash = hashlib.md5(image_data).hexdigest()
                image_filename = attachment_name(f"embedded_{image_hash}.{self.options.output_format}")
                self.attachments.add_embed(image_filename, EmbeddedFileData(image_data))

            return self.generator.create_attached_image(image_filename, attrs)
        else:
            if relative_path is not None:
                absolute_path = self.base_dir / relative_path
                self.attachments.add_image(ImageData(absolute_path, attrs.alt))

            # use macro `plantumlcloud` with SVG attachment
            if has_plantuml():
                # render to SVG for macro `plantumlcloud` (macro requires SVG)
                config = self._extract_plantuml_config(content)
                image_data = render_diagram(content, "svg", config=config)

                # extract dimensions from SVG
                width, height = get_svg_dimensions_from_bytes(image_data)

                # generate SVG filename and add as attachment
                if relative_path is not None:
                    svg_filename = attachment_name(relative_path.with_suffix(".svg"))
                    self.attachments.add_embed(svg_filename, EmbeddedFileData(image_data, attrs.alt))
                else:
                    plantuml_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
                    svg_filename = attachment_name(f"embedded_{plantuml_hash}.svg")
                    self.attachments.add_embed(svg_filename, EmbeddedFileData(image_data))

                return self._create_plantuml_macro(content, svg_filename, width, height)
            else:
                return self._create_plantuml_macro(content)

    def _create_plantuml_macro(self, source: str, filename: str | None = None, width: int | None = None, height: int | None = None) -> ElementType:
        """
        A PlantUML diagram using the macro `plantumlcloud` with embedded data.

        Generates a macro compatible with PlantUML Diagrams for Confluence app.

        :see: https://stratus-addons.atlassian.net/wiki/spaces/PDFC/pages/1839333377
        """

        local_id = str(uuid.uuid4())
        macro_id = str(uuid.uuid4())

        # Compress PlantUML source for embedding
        compressed_data = compress_plantuml_data(source)

        # Build mandatory parameters
        parameters: list[ElementType] = [
            AC_ELEM("parameter", {AC_ATTR("name"): "data"}, compressed_data),
            AC_ELEM("parameter", {AC_ATTR("name"): "compressed"}, "true"),
            AC_ELEM("parameter", {AC_ATTR("name"): "revision"}, "1"),
            AC_ELEM("parameter", {AC_ATTR("name"): "toolbar"}, "bottom"),
        ]
        if filename is not None:
            parameters.append(AC_ELEM("parameter", {AC_ATTR("name"): "filename"}, filename))

        # add optional dimension parameters if available
        if width is not None:
            parameters.append(
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): "originalWidth"},
                    str(width),
                )
            )
        if height is not None:
            parameters.append(
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): "originalHeight"},
                    str(height),
                )
            )

        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "plantumlcloud",
                AC_ATTR("schema-version"): "1",
                "data-layout": "default",
                AC_ATTR("local-id"): local_id,
                AC_ATTR("macro-id"): macro_id,
            },
            *parameters,
        )
