"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import uuid
from pathlib import Path

import lxml.etree as ET

from md2conf.attachment import EmbeddedFileData, ImageData, attachment_name
from md2conf.compatibility import override, path_relative_to
from md2conf.csf import AC_ATTR, AC_ELEM
from md2conf.extension import MarketplaceExtension
from md2conf.formatting import ImageAlignment, ImageAttributes

from .render import extract_diagram, render_diagram

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]


class DrawioExtension(MarketplaceExtension):
    @override
    def matches_image(self, absolute_path: Path) -> bool:
        return absolute_path.name.endswith((".drawio", ".drawio.png", ".drawio.svg", ".drawio.xml"))

    @override
    def matches_fenced(self, language: str, content: str) -> bool:
        return False

    @override
    def transform_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        if absolute_path.name.endswith((".drawio.png", ".drawio.svg")):
            return self._transform_drawio_image(absolute_path, attrs)
        elif absolute_path.name.endswith((".drawio", ".drawio.xml")):
            return self._transform_drawio(absolute_path, attrs)
        else:
            raise RuntimeError(f"unrecognized image format: {absolute_path.suffix}")

    @override
    def transform_fenced(self, content: str) -> ElementType:
        raise RuntimeError("draw.io diagrams cannot be defined in fenced code blocks")

    def _transform_drawio(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        relative_path = path_relative_to(absolute_path, self.base_dir)
        if self.options.render:
            image_data = render_diagram(absolute_path, self.generator.options.output_format)
            return self.generator.transform_attached_data(image_data, attrs, relative_path)
        else:
            self.attachments.add_image(ImageData(absolute_path, attrs.alt))
            image_filename = attachment_name(relative_path)
            return self._create_drawio(image_filename, attrs)

    def _transform_drawio_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        if self.options.render:
            # already a PNG or SVG file (with embedded draw.io content)
            return self.generator.transform_attached_image(absolute_path, attrs)
        else:
            # extract embedded editable diagram and upload as *.drawio
            image_data = extract_diagram(absolute_path)
            image_filename = attachment_name(path_relative_to(absolute_path.with_suffix(".xml"), self.base_dir))
            self.attachments.add_embed(image_filename, EmbeddedFileData(image_data, attrs.alt))

            return self._create_drawio(image_filename, attrs)

    def _create_drawio(self, filename: str, attrs: ImageAttributes) -> ElementType:
        "A draw.io diagram embedded into the page, linking to an attachment."

        parameters: list[ElementType] = [
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "diagramName"},
                filename,
            ),
        ]
        if attrs.width is not None:
            parameters.append(
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): "width"},
                    str(attrs.width),
                ),
            )
        if attrs.height is not None:
            parameters.append(
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): "height"},
                    str(attrs.height),
                ),
            )
        if attrs.alignment is ImageAlignment.CENTER:
            parameters.append(
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): "pCenter"},
                    str(1),
                ),
            )

        local_id = str(uuid.uuid4())
        macro_id = str(uuid.uuid4())
        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "drawio",
                AC_ATTR("schema-version"): "1",
                "data-layout": "default",
                AC_ATTR("local-id"): local_id,
                AC_ATTR("macro-id"): macro_id,
            },
            *parameters,
        )
