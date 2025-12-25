"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from pathlib import Path

import lxml.etree as ET

from .attachment import AttachmentCatalog, ImageData, attachment_name
from .csf import AC_ELEM, RI_ATTR, RI_ELEM
from .extra import path_relative_to
from .formatting import ImageAttributes
from .svg import get_svg_dimensions

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]


class ImageGenerator:
    base_dir: Path
    attachments: AttachmentCatalog
    prefer_raster: bool
    max_image_width: int | None

    def __init__(self, base_dir: Path, attachments: AttachmentCatalog, prefer_raster: bool, max_image_width: int | None) -> None:
        self.base_dir = base_dir
        self.attachments = attachments
        self.prefer_raster = prefer_raster
        self.max_image_width = max_image_width

    def create_attached_image(self, image_name: str, attrs: ImageAttributes) -> ElementType:
        "An image embedded into the page, linking to an attachment."

        elements: list[ElementType] = []
        elements.append(
            RI_ELEM(
                "attachment",
                # refers to an attachment uploaded alongside the page
                {RI_ATTR("filename"): image_name},
            )
        )
        if attrs.caption:
            elements.append(AC_ELEM("caption", attrs.caption))

        return AC_ELEM("image", attrs.as_dict(max_width=self.max_image_width), *elements)

    def transform_attached_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for an attached raster or vector image."

        if self.prefer_raster and absolute_path.suffix == ".svg":
            # prefer PNG over SVG; Confluence displays SVG in wrong size, and text labels are truncated
            png_file = absolute_path.with_suffix(".png")
            if png_file.exists():
                absolute_path = png_file

        # infer SVG dimensions if not already specified
        if absolute_path.suffix == ".svg" and attrs.width is None and attrs.height is None:
            svg_width, svg_height = get_svg_dimensions(absolute_path)
            if svg_width is not None:
                attrs = ImageAttributes(
                    context=attrs.context,
                    width=svg_width,
                    height=svg_height,
                    alt=attrs.alt,
                    title=attrs.title,
                    caption=attrs.caption,
                    alignment=attrs.alignment,
                )

        self.attachments.add_image(ImageData(absolute_path, attrs.alt))
        image_name = attachment_name(path_relative_to(absolute_path, self.base_dir))
        return self.create_attached_image(image_name, attrs)
