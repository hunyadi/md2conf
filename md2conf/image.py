"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import lxml.etree as ET

from .attachment import AttachmentCatalog, EmbeddedFileData, ImageData, attachment_name
from .compatibility import path_relative_to
from .csf import AC_ELEM, RI_ATTR, RI_ELEM
from .formatting import ImageAttributes
from .png import extract_png_dimensions
from .svg import fix_svg_get_dimensions, get_svg_dimensions

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]


@dataclass
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


class ImageGenerator:
    base_dir: Path
    attachments: AttachmentCatalog

    def __init__(self, base_dir: Path, attachments: AttachmentCatalog, options: ImageGeneratorOptions) -> None:
        self.base_dir = base_dir
        self.attachments = attachments
        self.options = options

    def transform_attached_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for an attached raster or vector image."

        if self.options.prefer_raster and absolute_path.suffix == ".svg":
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

    def transform_attached_data(self, image_data: bytes, attrs: ImageAttributes, relative_path: Path | None = None) -> ElementType:
        "Emits Confluence Storage Format XHTML for an attached raster or vector image."

        # extract dimensions and update attributes based on format
        width: int | None
        height: int | None
        match self.options.output_format:
            case "svg":
                image_data, width, height = fix_svg_get_dimensions(image_data)
            case "png":
                width, height = extract_png_dimensions(data=image_data)

        # only update attributes if we successfully extracted dimensions and the base attributes don't already have explicit dimensions
        if (width is not None or height is not None) and (attrs.width is None and attrs.height is None):
            # create updated image attributes with extracted dimensions
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

        return self.create_attached_image(image_filename, attrs)

    def create_attached_image(self, image_name: str, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for an image embedded into the page, linking to an attachment."

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

        return AC_ELEM("image", attrs.as_dict(max_width=self.options.max_width), *elements)
