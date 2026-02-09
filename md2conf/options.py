"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass, field
from typing import Literal

from .clio import boolean_option, composite_option, nullable_option, value_option


@dataclass(frozen=True)
class ConfluencePageID:
    """
    Encapsulates a Confluence page ID.

    :param page_id: Confluence page ID.
    """

    page_id: str

    def __str__(self) -> str:
        return self.page_id


@dataclass(frozen=True)
class Markdown:
    """
    Encapsulates a snippet of Markdown text.

    :param string: Markdown text.
    """

    string: str

    def __str__(self) -> str:
        return self.string


@dataclass
class ImageLayoutOptions:
    """
    Image layout options on a Confluence page.

    :param alignment: Alignment for block-level images and formulas.
    :param max_width: Maximum display width for images [px]. Wider images are scaled down for page display. Original size kept for full-size viewing.
    """

    alignment: Literal["center", "left", "right", None] = field(default=None, metadata=value_option("Alignment for block-level images and formulas."))
    max_width: int | None = field(
        default=None,
        metadata=value_option("Maximum display width for images [px]. Wider images are scaled down for page display."),
    )


@dataclass
class TableLayoutOptions:
    """
    Table layout options on a Confluence page.

    :param width: Maximum table width in pixels.
    :param display_mode: Whether to use fixed or responsive column widths.
    """

    width: int | None = field(default=None, metadata=value_option("Maximum table width in pixels."))
    display_mode: Literal["responsive", "fixed"] = field(default="responsive", metadata=value_option("Set table display mode."))


@dataclass
class LayoutOptions:
    """
    Layout options for content on a Confluence page.

    Layout options can be overridden in Markdown front-matter.

    :param image: Image layout options.
    :param table: Table layout options.
    :param alignment: Default alignment (unless overridden with more specific setting).
    """

    image: ImageLayoutOptions = field(default_factory=ImageLayoutOptions, metadata=composite_option())
    table: TableLayoutOptions = field(default_factory=TableLayoutOptions, metadata=composite_option())
    alignment: Literal["center", "left", "right", None] = field(default=None, metadata=value_option("Default alignment for block-level content."))

    def get_image_alignment(self) -> Literal["center", "left", "right"]:
        return self.image.alignment or self.alignment or "center"


@dataclass
class ConverterOptions:
    """
    Options for converting an HTML tree into Confluence Storage Format.

    :param heading_anchors: When true, emit a structured macro *anchor* for each section heading using GitHub
        conversion rules for the identifier.
    :param force_valid_url: If enabled, raise an exception when relative URLs point to an invalid location. If disabled,
        ignore invalid URLs, emit a warning and replace the anchor with plain text.
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

    heading_anchors: bool = field(
        default=False,
        metadata=boolean_option(
            "Place an anchor at each section heading with GitHub-style same-page identifiers.",
            "Omit the extra anchor from section headings. (May break manually placed same-page references.)",
        ),
    )
    force_valid_url: bool = field(
        default=True,
        metadata=boolean_option(
            "Raise an error when relative URLs point to an invalid location.",
            "Emit a warning but otherwise ignore relative URLs that point to an invalid location.",
        ),
    )
    skip_title_heading: bool = field(
        default=False,
        metadata=boolean_option(
            "Remove the first heading from document body when it is used as the page title (does not apply if title comes from front-matter).",
            "Keep the first heading in document body even when used as page title.",
        ),
    )
    prefer_raster: bool = field(
        default=True,
        metadata=boolean_option(
            "Prefer PNG over SVG when both exist.",
            "Use SVG files directly instead of preferring PNG equivalents.",
        ),
    )
    render_drawio: bool = field(
        default=True,
        metadata=boolean_option(
            "Render draw.io diagrams as image files. (Installed utility required to covert.)",
            "Upload draw.io diagram sources as Confluence page attachments. (Marketplace app required to display.)",
        ),
    )
    render_mermaid: bool = field(
        default=True,
        metadata=boolean_option(
            "Render Mermaid diagrams as image files. (Installed utility required to convert.)",
            "Upload Mermaid diagram sources as Confluence page attachments. (Marketplace app required to display.)",
        ),
    )
    render_plantuml: bool = field(
        default=True,
        metadata=boolean_option(
            "Render PlantUML diagrams as image files. (Installed utility required to convert.)",
            "Upload PlantUML diagram sources as Confluence page attachments. (Marketplace app required to display.)",
        ),
    )
    render_latex: bool = field(
        default=True,
        metadata=boolean_option(
            "Render LaTeX formulas as image files. (Matplotlib required to convert.)",
            "Inline LaTeX formulas in Confluence page. (Marketplace app required to display.)",
        ),
    )
    diagram_output_format: Literal["png", "svg"] = field(
        default="png",
        metadata=value_option("Format for rendering Mermaid and draw.io diagrams."),
    )
    webui_links: bool = field(
        default=False,
        metadata=boolean_option(
            "Enable Confluence Web UI links. (Typically required for on-prem versions of Confluence.)",
            "Use hierarchical links including space and page ID.",
        ),
    )
    use_panel: bool = field(
        default=False,
        metadata=boolean_option(
            "Transform admonitions and alerts into a Confluence custom panel.",
            "Use standard Confluence macro types for admonitions and alerts (info, tip, note and warning).",
        ),
    )
    layout: LayoutOptions = field(default_factory=LayoutOptions, metadata=composite_option())


@dataclass
class ProcessorOptions:
    """
    Options that control how page content is generated and synchronized.

    :param root_page: Confluence page to assume root page role for publishing a directory of Markdown files.
    :param keep_hierarchy: Whether to maintain source directory structure when exporting to Confluence.
    :param title_prefix: String to prepend to Confluence page title for each published page.
    :param generated_by: Text to use as the generated-by prompt (or `None` to omit a prompt).
    :param skip_update: Whether to skip saving Confluence page ID in Markdown files.
    :param converter: Options for converting an HTML tree into Confluence Storage Format.
    :param line_numbers: Inject line numbers in Markdown source file to help localize conversion errors.
    """

    root_page: ConfluencePageID | None = field(
        default=None, metadata=value_option("Root Confluence page to create new pages. If omitted, will raise exception when creating new pages.")
    )
    keep_hierarchy: bool = field(
        default=False,
        metadata=boolean_option(
            "Maintain source directory structure when exporting to Confluence.",
            "Flatten directories with no `index.md` or `README.md` when exporting to Confluence.",
        ),
    )
    title_prefix: str | None = field(
        default=None,
        metadata=nullable_option(
            "String to prepend to Confluence page title for each published page.",
            "Use Markdown title to synchronize page.",
        ),
    )
    generated_by: Markdown | None = field(
        default=Markdown("This page has been generated with a tool."),
        metadata=nullable_option(
            "Add prompt to pages.",
            "Do not add 'generated by a tool' prompt to pages.",
        ),
    )
    skip_update: bool = field(
        default=False,
        metadata=boolean_option(
            "Skip saving Confluence page ID in Markdown files.",
            "Inject published Confluence page ID in Markdown files.",
        ),
    )
    converter: ConverterOptions = field(default_factory=ConverterOptions, metadata=composite_option(flatten=True))
    line_numbers: bool = field(
        default=False,
        metadata=boolean_option(
            "Inject line numbers in Markdown source file to help localize conversion errors.",
            "Leave Markdown source file unmodified.",
        ),
    )
