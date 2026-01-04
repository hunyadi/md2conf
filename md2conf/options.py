"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import dataclasses
from dataclasses import dataclass
from typing import Literal


@dataclass
class ConfluencePageID:
    page_id: str


@dataclass
class ImageLayoutOptions:
    """
    Image layout options on a Confluence page.

    :param alignment: Alignment for block-level images and formulas.
    :param max_width: Maximum display width for images [px]. Wider images are scaled down for page display. Original size kept for full-size viewing.
    """

    alignment: Literal["center", "left", "right"] | None = None
    max_width: int | None = None


@dataclass
class TableLayoutOptions:
    """
    Table layout options on a Confluence page.

    :param width: Maximum table width in pixels.
    :param display_mode: Whether to use fixed or responsive column widths.
    """

    width: int | None = None
    display_mode: Literal["fixed", "responsive"] | None = None


@dataclass
class LayoutOptions:
    """
    Layout options for content on a Confluence page.

    Layout options can be overridden in Markdown front-matter.

    :param image: Image layout options.
    :param table: Table layout options.
    :param alignment: Default alignment (unless overridden with more specific setting).
    """

    image: ImageLayoutOptions = dataclasses.field(default_factory=ImageLayoutOptions)
    table: TableLayoutOptions = dataclasses.field(default_factory=TableLayoutOptions)
    alignment: Literal["center", "left", "right"] | None = None

    def get_image_alignment(self) -> Literal["center", "left", "right"]:
        return self.image.alignment or self.alignment or "center"


@dataclass
class ConverterOptions:
    """
    Options for converting an HTML tree into Confluence Storage Format.

    :param heading_anchors: When true, emit a structured macro *anchor* for each section heading using GitHub
        conversion rules for the identifier.
    :param ignore_invalid_url: When true, ignore invalid URLs in input, emit a warning and replace the anchor with
        plain text; when false, raise an exception.
    :param skip_title_heading: Whether to remove the first heading from document body when used as page title.
    :param prefer_raster: Whether to choose PNG files over SVG files when available.
    :param render_drawio: Whether to pre-render (or use the pre-rendered version of) draw.io diagrams.
    :param render_mermaid: Whether to pre-render Mermaid diagrams into PNG/SVG images.
    :param render_plantuml: Whether to pre-render PlantUML diagrams into PNG/SVG images.
    :param render_latex: Whether to pre-render LaTeX formulas into PNG/SVG images.
    :param diagram_output_format: Target image format for diagrams.
    :param webui_links: When true, convert relative URLs to Confluence Web UI links.
    :param use_panel: Whether to transform admonitions and alerts into a Confluence custom panel.
    :param layout: Layout options for content on a Confluence page.
    """

    heading_anchors: bool = False
    ignore_invalid_url: bool = False
    skip_title_heading: bool = False
    prefer_raster: bool = True
    render_drawio: bool = False
    render_mermaid: bool = False
    render_plantuml: bool = False
    render_latex: bool = False
    diagram_output_format: Literal["png", "svg"] = "png"
    webui_links: bool = False
    use_panel: bool = False
    layout: LayoutOptions = dataclasses.field(default_factory=LayoutOptions)


@dataclass
class DocumentOptions:
    """
    Options that control the generated page content.

    :param root_page_id: Confluence page to assume root page role for publishing a directory of Markdown files.
    :param keep_hierarchy: Whether to maintain source directory structure when exporting to Confluence.
    :param title_prefix: String to prepend to Confluence page title for each published page.
    :param generated_by: Text to use as the generated-by prompt (or `None` to omit a prompt).
    :param converter: Options for converting an HTML tree into Confluence Storage Format.
    """

    root_page_id: ConfluencePageID | None = None
    keep_hierarchy: bool = False
    title_prefix: str | None = None
    generated_by: str | None = "This page has been generated with a tool."
    converter: ConverterOptions = dataclasses.field(default_factory=ConverterOptions)
