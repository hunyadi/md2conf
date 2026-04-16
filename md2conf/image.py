"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, overload

from .attachment import AttachmentCatalog, EmbeddedFileData, ImageData, attachment_name
from .compatibility import path_relative_to
from .csf import AC_ATTR, AC_ELEM, RI_ATTR, RI_ELEM, ElementType
from .formatting import FormattingContext, ImageAlignment, ImageAttributes, display_width
from .jpeg import extract_jpeg_dimensions
from .png import extract_png_dimensions
from .svg import fix_svg_get_dimensions, get_svg_dimensions


def to_element_attrs(attrs: ImageAttributes, *, max_width: int | None) -> dict[str, str]:
    """
    Produces a key-value store of element attributes.

    :param max_width: The desired maximum width of the image in pixels.
    """

    attributes: dict[str, str] = {}
    match attrs.context:
        case FormattingContext.BLOCK:
            match attrs.alignment:
                case ImageAlignment.LEFT:
                    align = "left"
                    layout = "align-start"
                case ImageAlignment.RIGHT:
                    align = "right"
                    layout = "align-end"
                case ImageAlignment.CENTER:
                    align = "center"
                    layout = "center"
            attributes[AC_ATTR("align")] = align
            attributes[AC_ATTR("layout")] = layout

            if attrs.width is not None:
                attributes[AC_ATTR("original-width")] = str(attrs.width)
            if attrs.height is not None:
                attributes[AC_ATTR("original-height")] = str(attrs.height)
            if attrs.width is not None:
                attributes[AC_ATTR("custom-width")] = "true"
                # Use display_width if set, otherwise use natural width
                effective_width = display_width(width=attrs.width, max_width=max_width) or attrs.width
                attributes[AC_ATTR("width")] = str(effective_width)

        case FormattingContext.INLINE:
            if attrs.width is not None:
                attributes[AC_ATTR("width")] = str(attrs.width)
            if attrs.height is not None:
                attributes[AC_ATTR("height")] = str(attrs.height)

    if attrs.alt is not None:
        attributes.update({AC_ATTR("alt"): attrs.alt})
    if attrs.title is not None:
        attributes.update({AC_ATTR("title"): attrs.title})
    return attributes


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
            if png_file.is_file():
                absolute_path = png_file

        # infer SVG dimensions if not already specified
        if attrs.width is None and attrs.height is None:
            match absolute_path.suffix:
                case ".svg":
                    dimensions = get_svg_dimensions(absolute_path)
                case ".png":
                    dimensions = extract_png_dimensions(path=absolute_path)
                case ".jpg" | ".jpeg":
                    dimensions = extract_jpeg_dimensions(path=absolute_path)
                case _:
                    dimensions = None
            if dimensions is not None:
                width, height = dimensions
                attrs = attrs.with_dimensions(width, height)

        self.attachments.add_image(ImageData(absolute_path, attrs.alt))
        image_name = attachment_name(path_relative_to(absolute_path, self.base_dir))
        return self.create_attached_image(image_name, attrs)

    @overload
    def transform_attached_data(self, image_data: bytes, attrs: ImageAttributes, *, relative_path: Path, image_type: str = "embedded") -> ElementType: ...

    @overload
    def transform_attached_data(self, image_data: bytes, attrs: ImageAttributes, *, content: str, image_type: str = "embedded") -> ElementType: ...

    def transform_attached_data(
        self, image_data: bytes, attrs: ImageAttributes, relative_path: Path | None = None, content: str | None = None, *, image_type: str = "embedded"
    ) -> ElementType:
        "Emits Confluence Storage Format XHTML for an attached raster or vector image."

        # extract dimensions and update attributes based on format
        dimensions: tuple[int, int] | None
        match self.options.output_format:
            case "svg":
                image_data, dimensions = fix_svg_get_dimensions(image_data)
            case "png":
                dimensions = extract_png_dimensions(data=image_data)

        # only update attributes if we successfully extracted dimensions and the base attributes don't already have explicit dimensions
        if dimensions is not None and (attrs.width is None and attrs.height is None):
            # create updated image attributes with extracted dimensions
            width, height = dimensions
            attrs = attrs.with_dimensions(width, height)

        # generate filename
        if relative_path is not None:
            image_filename = attachment_name(relative_path.with_suffix(f".{self.options.output_format}"))
        elif content is not None:
            image_hash = hashlib.md5(content.encode()).hexdigest()
            image_filename = attachment_name(f"{image_type}_{image_hash}.{self.options.output_format}")
        else:
            image_hash = hashlib.md5(image_data).hexdigest()
            image_filename = attachment_name(f"{image_type}_{image_hash}.{self.options.output_format}")

        # add as attachment
        self.attachments.add_embed(image_filename, EmbeddedFileData(image_data, attrs.alt))
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
        caption = attrs.get_caption()
        if caption:
            elements.append(AC_ELEM("caption", caption))

        return AC_ELEM("image", to_element_attrs(attrs, max_width=self.options.max_width), *elements)
