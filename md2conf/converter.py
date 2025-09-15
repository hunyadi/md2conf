"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import dataclasses
import enum
import hashlib
import logging
import os.path
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal, Optional, Union
from urllib.parse import ParseResult, quote_plus, urlparse

import lxml.etree as ET
from strong_typing.core import JsonType
from strong_typing.exception import JsonTypeError

from . import drawio, mermaid
from .collection import ConfluencePageCollection
from .csf import AC_ATTR, AC_ELEM, HTML, RI_ATTR, RI_ELEM, ParseError, elements_from_strings, elements_to_string, normalize_inline
from .domain import ConfluenceDocumentOptions, ConfluencePageID
from .emoticon import emoji_to_emoticon
from .environment import PageError
from .extra import override, path_relative_to
from .latex import get_png_dimensions, remove_png_chunks, render_latex
from .markdown import markdown_to_html
from .mermaid import MermaidConfigProperties
from .metadata import ConfluenceSiteMetadata
from .scanner import MermaidScanner, ScannedDocument, Scanner
from .toc import TableOfContentsBuilder
from .uri import is_absolute_url, to_uuid_urn
from .xml import element_to_text

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]


def get_volatile_attributes() -> list[str]:
    "Returns a list of volatile attributes that frequently change as a Confluence storage format XHTML document is updated."

    return [
        AC_ATTR("local-id"),
        AC_ATTR("macro-id"),
        RI_ATTR("version-at-save"),
    ]


def get_volatile_elements() -> list[str]:
    "Returns a list of volatile elements whose content frequently changes as a Confluence storage format XHTML document is updated."

    return [AC_ATTR("task-uuid")]


status_images: dict[str, str] = {
    to_uuid_urn(f'<svg height="10" width="10" xmlns="http://www.w3.org/2000/svg"><circle r="5" cx="5" cy="5" fill="{color}" /></svg>'): color
    for color in ["gray", "purple", "blue", "red", "yellow", "green"]
}

LOGGER = logging.getLogger(__name__)


def starts_with_any(text: str, prefixes: list[str]) -> bool:
    "True if text starts with any of the listed prefixes."

    for prefix in prefixes:
        if text.startswith(prefix):
            return True
    return False


def is_directory_within(absolute_path: Path, base_path: Path) -> bool:
    "True if the absolute path is nested within the base path."

    return absolute_path.as_posix().startswith(base_path.as_posix())


def encode_title(text: str) -> str:
    "Converts a title string such that it is safe to embed into a Confluence URL."

    # replace unsafe characters with space
    text = re.sub(r"[^A-Za-z0-9._~()'!*:@,;+?-]+", " ", text)

    # replace multiple consecutive spaces with single space
    text = re.sub(r"\s\s+", " ", text)

    # URL-encode
    return quote_plus(text.strip())


# supported code block languages, for which syntax highlighting is available
_LANGUAGES = {
    "abap": "abap",
    "actionscript3": "actionscript3",
    "ada": "ada",
    "applescript": "applescript",
    "arduino": "arduino",
    "autoit": "autoit",
    "bash": "bash",
    "c": "c",
    "c#": "c#",
    "clojure": "clojure",
    "coffeescript": "coffeescript",
    "coldfusion": "coldfusion",
    "cpp": "cpp",
    "csharp": "c#",
    "css": "css",
    "cuda": "cuda",
    "d": "d",
    "dart": "dart",
    "delphi": "delphi",
    "diff": "diff",
    "elixir": "elixir",
    "erl": "erl",
    "erlang": "erl",
    "fortran": "fortran",
    "foxpro": "foxpro",
    "go": "go",
    "graphql": "graphql",
    "groovy": "groovy",
    "haskell": "haskell",
    "haxe": "haxe",
    "html": "html",
    "java": "java",
    "javafx": "javafx",
    "javascript": "js",
    "js": "js",
    "json": "json",
    "jsx": "jsx",
    "julia": "julia",
    "kotlin": "kotlin",
    "livescript": "livescript",
    "lua": "lua",
    "mermaid": "mermaid",
    "mathematica": "mathematica",
    "matlab": "matlab",
    "objectivec": "objectivec",
    "objectivej": "objectivej",
    "ocaml": "ocaml",
    "octave": "octave",
    "pascal": "pascal",
    "perl": "perl",
    "php": "php",
    "powershell": "powershell",
    "prolog": "prolog",
    "puppet": "puppet",
    "py": "py",
    "python": "py",
    "qml": "qml",
    "r": "r",
    "racket": "racket",
    "rst": "rst",
    "ruby": "ruby",
    "rust": "rust",
    "sass": "sass",
    "scala": "scala",
    "scheme": "scheme",
    "shell": "shell",
    "smalltalk": "smalltalk",
    "splunk": "splunk",
    "sql": "sql",
    "standardml": "standardml",
    "swift": "swift",
    "tcl": "tcl",
    "tex": "tex",
    "tsx": "tsx",
    "typescript": "typescript",
    "vala": "vala",
    "vb": "vb",
    "verilog": "verilog",
    "vhdl": "vhdl",
    "xml": "xml",
    "xquery": "xquery",
    "yaml": "yaml",
}


class NodeVisitor(ABC):
    def visit(self, node: ElementType) -> None:
        "Recursively visits all descendants of this node."

        if len(node) < 1:
            return

        for index in range(len(node)):
            source = node[index]
            target = self.transform(source)
            if target is not None:
                # chain sibling text node that immediately follows original element
                target.tail = source.tail
                source.tail = None

                # replace original element with transformed element
                node[index] = target
            else:
                self.visit(source)

    @abstractmethod
    def transform(self, child: ElementType) -> Optional[ElementType]: ...


def title_to_identifier(title: str) -> str:
    "Converts a section heading title to a GitHub-style Markdown same-page anchor."

    s = title.strip().lower()
    s = re.sub(r"[^\sA-Za-z0-9_\-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


def element_text_starts_with_any(node: ElementType, prefixes: list[str]) -> bool:
    "True if the text contained in an element starts with any of the specified prefix strings."

    if node.text is None:
        return False
    return starts_with_any(node.text, prefixes)


def is_placeholder_for(node: ElementType, name: str) -> bool:
    """
    Identifies a Confluence widget placeholder, e.g. `[[_TOC_]]` or `[[_LISTING_]]`.

    :param node: The element to check.
    :param name: The placeholder name.
    """

    # `[[_TOC_]]` is represented in HTML as <p>[[<em>TOC</em>]]</p>
    if node.text != "[[" or len(node) != 1:
        return False

    child = node[0]
    if child.tag != "em" or child.text != name or child.tail != "]]":
        return False

    return True


@enum.unique
class FormattingContext(enum.Enum):
    "Identifies the formatting context for the element."

    BLOCK = "block"
    INLINE = "inline"


@enum.unique
class ImageAlignment(enum.Enum):
    "Determines whether to align block-level images to center, left or right."

    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"


@dataclass
class ImageAttributes:
    """
    Attributes applied to an `<img>` element.

    :param context: Identifies the formatting context for the element (block or inline).
    :param width: Natural image width in pixels.
    :param height: Natural image height in pixels.
    :param alt: Alternate text.
    :param title: Title text (a.k.a. image tooltip).
    :param caption: Caption text (shown below figure).
    :param alignment: Alignment for block-level images.
    """

    context: FormattingContext
    width: Optional[int]
    height: Optional[int]
    alt: Optional[str]
    title: Optional[str]
    caption: Optional[str]
    alignment: ImageAlignment = ImageAlignment.CENTER

    def __post_init__(self) -> None:
        if self.caption is None and self.context is FormattingContext.BLOCK:
            self.caption = self.title or self.alt

    def as_dict(self) -> dict[str, str]:
        attributes: dict[str, str] = {}
        if self.context is FormattingContext.BLOCK:
            if self.alignment is ImageAlignment.LEFT:
                attributes[AC_ATTR("align")] = "left"
                attributes[AC_ATTR("layout")] = "align-start"
            elif self.alignment is ImageAlignment.RIGHT:
                attributes[AC_ATTR("align")] = "right"
                attributes[AC_ATTR("layout")] = "align-end"
            else:
                attributes[AC_ATTR("align")] = "center"
                attributes[AC_ATTR("layout")] = "center"

            if self.width is not None:
                attributes[AC_ATTR("original-width")] = str(self.width)
            if self.height is not None:
                attributes[AC_ATTR("original-height")] = str(self.height)
            if self.width is not None:
                attributes[AC_ATTR("custom-width")] = "true"
                attributes[AC_ATTR("width")] = str(self.width)

        elif self.context is FormattingContext.INLINE:
            if self.width is not None:
                attributes[AC_ATTR("width")] = str(self.width)
            if self.height is not None:
                attributes[AC_ATTR("height")] = str(self.height)
        else:
            raise NotImplementedError("match not exhaustive for enumeration")

        if self.alt is not None:
            attributes.update({AC_ATTR("alt"): self.alt})
        if self.title is not None:
            attributes.update({AC_ATTR("title"): self.title})
        return attributes

    EMPTY_BLOCK: ClassVar["ImageAttributes"]
    EMPTY_INLINE: ClassVar["ImageAttributes"]

    @classmethod
    def empty(cls, context: FormattingContext) -> "ImageAttributes":
        if context is FormattingContext.BLOCK:
            return cls.EMPTY_BLOCK
        elif context is FormattingContext.INLINE:
            return cls.EMPTY_INLINE
        else:
            raise NotImplementedError("match not exhaustive for enumeration")


ImageAttributes.EMPTY_BLOCK = ImageAttributes(
    FormattingContext.BLOCK, width=None, height=None, alt=None, title=None, caption=None, alignment=ImageAlignment.CENTER
)
ImageAttributes.EMPTY_INLINE = ImageAttributes(
    FormattingContext.INLINE, width=None, height=None, alt=None, title=None, caption=None, alignment=ImageAlignment.CENTER
)


@dataclass
class ConfluenceConverterOptions:
    """
    Options for converting an HTML tree into Confluence storage format.

    :param ignore_invalid_url: When true, ignore invalid URLs in input, emit a warning and replace the anchor with
        plain text; when false, raise an exception.
    :param heading_anchors: When true, emit a structured macro *anchor* for each section heading using GitHub
        conversion rules for the identifier.
    :param prefer_raster: Whether to choose PNG files over SVG files when available.
    :param render_drawio: Whether to pre-render (or use the pre-rendered version of) draw.io diagrams.
    :param render_mermaid: Whether to pre-render Mermaid diagrams into PNG/SVG images.
    :param render_latex: Whether to pre-render LaTeX formulas into PNG/SVG images.
    :param diagram_output_format: Target image format for diagrams.
    :param webui_links: When true, convert relative URLs to Confluence Web UI links.
    :param alignment: Alignment for block-level images and formulas.
    :param use_panel: Whether to transform admonitions and alerts into a Confluence custom panel.
    """

    ignore_invalid_url: bool = False
    heading_anchors: bool = False
    prefer_raster: bool = True
    render_drawio: bool = False
    render_mermaid: bool = False
    render_latex: bool = False
    diagram_output_format: Literal["png", "svg"] = "png"
    webui_links: bool = False
    alignment: Literal["center", "left", "right"] = "center"
    use_panel: bool = False


@dataclass
class ImageData:
    path: Path
    description: Optional[str] = None


@dataclass
class EmbeddedFileData:
    data: bytes
    description: Optional[str] = None


@dataclass
class ConfluencePanel:
    emoji: str
    emoji_shortname: str
    background_color: str
    from_class: ClassVar[dict[str, "ConfluencePanel"]]

    def __init__(self, emoji: str, emoji_shortname: str, background_color: str) -> None:
        self.emoji = emoji
        self.emoji_shortname = emoji_shortname
        self.background_color = background_color

    @property
    def emoji_unicode(self) -> str:
        return "-".join(f"{ord(ch):x}" for ch in self.emoji)

    @property
    def emoji_html(self) -> str:
        return "".join(f"&#{ord(ch)};" for ch in self.emoji)


ConfluencePanel.from_class = {
    "attention": ConfluencePanel("❗", "exclamation", "#F9F9F9"),  # rST admonition
    "caution": ConfluencePanel("❌", "x", "#FFEBE9"),
    "danger": ConfluencePanel("☠️", "skull_crossbones", "#FFE5E5"),  # rST admonition
    "disclaimer": ConfluencePanel("❗", "exclamation", "#F9F9F9"),  # GitLab
    "error": ConfluencePanel("❌", "x", "#FFEBE9"),  # rST admonition
    "flag": ConfluencePanel("🚩", "triangular_flag_on_post", "#FDECEA"),  # GitLab
    "hint": ConfluencePanel("💡", "bulb", "#DAFBE1"),  # rST admonition
    "info": ConfluencePanel("ℹ️", "information_source", "#DDF4FF"),
    "note": ConfluencePanel("📝", "pencil", "#DDF4FF"),
    "tip": ConfluencePanel("💡", "bulb", "#DAFBE1"),
    "important": ConfluencePanel("❗", "exclamation", "#FBEFFF"),
    "warning": ConfluencePanel("⚠️", "warning", "#FFF8C5"),
}


class ConfluenceStorageFormatConverter(NodeVisitor):
    "Transforms a plain HTML tree into Confluence Storage Format."

    options: ConfluenceConverterOptions
    path: Path
    base_dir: Path
    root_dir: Path
    toc: TableOfContentsBuilder
    links: list[str]
    images: list[ImageData]
    embedded_files: dict[str, EmbeddedFileData]
    site_metadata: ConfluenceSiteMetadata
    page_metadata: ConfluencePageCollection

    def __init__(
        self,
        options: ConfluenceConverterOptions,
        path: Path,
        root_dir: Path,
        site_metadata: ConfluenceSiteMetadata,
        page_metadata: ConfluencePageCollection,
    ) -> None:
        super().__init__()

        path = path.resolve(True)
        root_dir = root_dir.resolve(True)

        self.options = options
        self.path = path
        self.base_dir = path.parent
        self.root_dir = root_dir
        self.toc = TableOfContentsBuilder()
        self.links = []
        self.images = []
        self.embedded_files = {}
        self.site_metadata = site_metadata
        self.page_metadata = page_metadata

    def _transform_heading(self, heading: ElementType) -> None:
        """
        Adds anchors to headings in the same document (if *heading anchors* is enabled).

        Original:
        ```
        <h1>Heading text</h1>
        ```

        Transformed:
        ```
        <h1><structured-macro name="anchor">...</structured-macro>Heading text</h1>
        ```
        """

        for e in heading:
            self.visit(e)

        anchor = AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "anchor",
                AC_ATTR("schema-version"): "1",
            },
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): ""},
                title_to_identifier(element_to_text(heading)),
            ),
        )

        # insert anchor as first child, pushing any text nodes
        heading.insert(0, anchor)
        anchor.tail = heading.text
        heading.text = None

    def _anchor_warn_or_raise(self, anchor: ElementType, msg: str) -> None:
        "Emit a warning or raise an exception when a path points to a resource that doesn't exist or is outside of the permitted hierarchy."

        if self.options.ignore_invalid_url:
            LOGGER.warning(msg)
            if anchor.text:
                anchor.text = "❌ " + anchor.text
            elif len(anchor) > 0:
                anchor.text = "❌ "
        else:
            raise DocumentError(msg)

    def _transform_link(self, anchor: ElementType) -> Optional[ElementType]:
        """
        Transforms links (HTML anchor `<a>`).

        * Absolute URLs are left intact.
        * Links to headings in the same document are transformed into `<ac:link>` (if *heading anchors* is enabled).
        * Links to documents in the source hierarchy are mapped into full Confluence URLs.
        """

        # Confluence doesn't support `title` attribute on `<a>` elements
        anchor.attrib.pop("title", None)

        url = anchor.get("href")
        if url is None or is_absolute_url(url):
            return None

        LOGGER.debug("Found link %s relative to %s", url, self.path)
        relative_url: ParseResult = urlparse(url)

        if not relative_url.scheme and not relative_url.netloc and not relative_url.path and not relative_url.params and not relative_url.query:
            LOGGER.debug("Found same-page URL: %s", url)
            if self.options.heading_anchors:
                # <ac:link ac:anchor="anchor"><ac:link-body>...</ac:link-body></ac:link>
                target = relative_url.fragment.lstrip("#")
                link_body = AC_ELEM("link-body", {}, *list(anchor))
                link_body.text = anchor.text
                link_wrapper = AC_ELEM(
                    "link",
                    {
                        AC_ATTR("anchor"): target,
                    },
                    link_body,
                )
                return link_wrapper
            else:
                return None

        # discard original value: relative links always require transformation
        anchor.attrib.pop("href")

        # convert the relative URL to absolute path based on the base path value
        absolute_path = (self.base_dir / relative_url.path).resolve()

        # look up the absolute path in the page metadata dictionary to discover the relative path within Confluence that should be used
        if not is_directory_within(absolute_path, self.root_dir):
            self._anchor_warn_or_raise(anchor, f"relative URL {url} points to outside root path: {self.root_dir}")
            return None

        if absolute_path.suffix == ".md":
            return self._transform_page_link(anchor, relative_url, absolute_path)
        else:
            return self._transform_attachment_link(anchor, absolute_path)

    def _transform_page_link(self, anchor: ElementType, relative_url: ParseResult, absolute_path: Path) -> Optional[ElementType]:
        """
        Transforms links to other Markdown documents (Confluence pages).
        """

        link_metadata = self.page_metadata.get(absolute_path)
        if link_metadata is None:
            self._anchor_warn_or_raise(anchor, f"unable to find matching page for URL: {relative_url.geturl()}")
            return None

        relative_path = os.path.relpath(absolute_path, self.base_dir)
        LOGGER.debug("Found link to page %s with metadata: %s", relative_path, link_metadata)
        self.links.append(relative_url.geturl())

        if self.options.webui_links:
            page_url = f"{self.site_metadata.base_path}pages/viewpage.action?pageId={link_metadata.page_id}"
        else:
            space_key = link_metadata.space_key or self.site_metadata.space_key

            if space_key is None:
                raise DocumentError("Confluence space key required for building full web URLs")

            page_url = f"{self.site_metadata.base_path}spaces/{space_key}/pages/{link_metadata.page_id}/{encode_title(link_metadata.title)}"

        transformed_url = ParseResult(
            scheme="https",
            netloc=self.site_metadata.domain,
            path=page_url,
            params="",
            query="",
            fragment=relative_url.fragment,
        )

        LOGGER.debug("Transformed relative URL: %s to URL: %s", relative_url.geturl(), transformed_url.geturl())
        anchor.set("href", transformed_url.geturl())
        return None

    def _transform_attachment_link(self, anchor: ElementType, absolute_path: Path) -> Optional[ElementType]:
        """
        Transforms links to document binaries such as PDF, DOCX or XLSX.
        """

        if not absolute_path.exists():
            self._anchor_warn_or_raise(anchor, f"relative URL points to non-existing file: {absolute_path}")
            return None

        file_name = attachment_name(path_relative_to(absolute_path, self.base_dir))
        self.images.append(ImageData(absolute_path))

        link_body = AC_ELEM("link-body", {}, *list(anchor))
        link_body.text = anchor.text
        link_wrapper = AC_ELEM(
            "link",
            {},
            RI_ELEM("attachment", {RI_ATTR("filename"): file_name}),
            link_body,
        )
        return link_wrapper

    def _transform_status(self, color: str, caption: str) -> ElementType:
        macro_id = str(uuid.uuid4())
        attributes = {
            AC_ATTR("name"): "status",
            AC_ATTR("schema-version"): "1",
            AC_ATTR("macro-id"): macro_id,
        }
        if color != "gray":
            return AC_ELEM(
                "structured-macro",
                attributes,
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): "colour"},
                    color.title(),
                ),
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): "title"},
                    caption,
                ),
            )
        else:
            return AC_ELEM(
                "structured-macro",
                attributes,
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): "title"},
                    caption,
                ),
            )

    def _transform_image(self, context: FormattingContext, image: ElementType) -> ElementType:
        "Inserts an attached or external image."

        src = image.get("src")
        if not src:
            raise DocumentError("image lacks `src` attribute")

        alt = image.get("alt")
        if alt is not None and src.startswith("urn:uuid:") and (color := status_images.get(src)) is not None:
            return self._transform_status(color, alt)

        title = image.get("title")
        width = image.get("width")
        height = image.get("height")
        pixel_width = int(width) if width is not None and width.isdecimal() else None
        pixel_height = int(height) if height is not None and height.isdecimal() else None
        attrs = ImageAttributes(
            context, width=pixel_width, height=pixel_height, alt=alt, title=title, caption=None, alignment=ImageAlignment(self.options.alignment)
        )

        if is_absolute_url(src):
            return self._transform_external_image(src, attrs)
        else:
            path = Path(src)

            absolute_path = self._verify_image_path(path)
            if absolute_path is None:
                return self._create_missing(path, attrs)

            if absolute_path.name.endswith(".drawio.png") or absolute_path.name.endswith(".drawio.svg"):
                return self._transform_drawio_image(absolute_path, attrs)
            elif absolute_path.name.endswith(".drawio.xml") or absolute_path.name.endswith(".drawio"):
                return self._transform_drawio(absolute_path, attrs)
            elif absolute_path.name.endswith(".mmd") or absolute_path.name.endswith(".mermaid"):
                return self._transform_external_mermaid(absolute_path, attrs)
            else:
                return self._transform_attached_image(absolute_path, attrs)

    def _transform_external_image(self, url: str, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for an external image."

        elements: list[ElementType] = []
        elements.append(
            RI_ELEM(
                "url",
                # refers to an external image
                {RI_ATTR("value"): url},
            )
        )
        if attrs.caption:
            elements.append(AC_ELEM("caption", attrs.caption))

        return AC_ELEM("image", attrs.as_dict(), *elements)

    def _warn_or_raise(self, msg: str) -> None:
        "Emit a warning or raise an exception when a path points to a resource that doesn't exist or is outside of the permitted hierarchy."

        if self.options.ignore_invalid_url:
            LOGGER.warning(msg)
        else:
            raise DocumentError(msg)

    def _verify_image_path(self, path: Path) -> Optional[Path]:
        "Checks whether an image path is safe to use."

        # resolve relative path into absolute path w.r.t. base dir
        absolute_path = (self.base_dir / path).resolve()

        if not absolute_path.exists():
            self._warn_or_raise(f"path to image {path} does not exist")
            return None

        if not is_directory_within(absolute_path, self.root_dir):
            self._warn_or_raise(f"path to image {path} points to outside root path {self.root_dir}")
            return None

        return absolute_path

    def _transform_attached_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for an attached raster or vector image."

        if self.options.prefer_raster and absolute_path.suffix == ".svg":
            # prefer PNG over SVG; Confluence displays SVG in wrong size, and text labels are truncated
            png_file = absolute_path.with_suffix(".png")
            if png_file.exists():
                absolute_path = png_file

        self.images.append(ImageData(absolute_path, attrs.alt))
        image_name = attachment_name(path_relative_to(absolute_path, self.base_dir))
        return self._create_attached_image(image_name, attrs)

    def _transform_drawio(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for a draw.io diagram."

        if not absolute_path.name.endswith(".drawio.xml") and not absolute_path.name.endswith(".drawio"):
            raise DocumentError("invalid image format; expected: `*.drawio.xml` or `*.drawio`")

        relative_path = path_relative_to(absolute_path, self.base_dir)
        if self.options.render_drawio:
            image_data = drawio.render_diagram(absolute_path, self.options.diagram_output_format)
            image_filename = attachment_name(relative_path.with_suffix(f".{self.options.diagram_output_format}"))
            self.embedded_files[image_filename] = EmbeddedFileData(image_data, attrs.alt)
            return self._create_attached_image(image_filename, attrs)
        else:
            self.images.append(ImageData(absolute_path, attrs.alt))
            image_filename = attachment_name(relative_path)
            return self._create_drawio(image_filename, attrs)

    def _transform_drawio_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for a draw.io diagram embedded in a PNG or SVG image."

        if not absolute_path.name.endswith(".drawio.png") and not absolute_path.name.endswith(".drawio.svg"):
            raise DocumentError("invalid image format; expected: `*.drawio.png` or `*.drawio.svg`")

        if self.options.render_drawio:
            return self._transform_attached_image(absolute_path, attrs)
        else:
            # extract embedded editable diagram and upload as *.drawio
            image_data = drawio.extract_diagram(absolute_path)
            image_filename = attachment_name(path_relative_to(absolute_path.with_suffix(".xml"), self.base_dir))
            self.embedded_files[image_filename] = EmbeddedFileData(image_data, attrs.alt)

            return self._create_drawio(image_filename, attrs)

    def _create_attached_image(self, image_name: str, attrs: ImageAttributes) -> ElementType:
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

        return AC_ELEM("image", attrs.as_dict(), *elements)

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

    def _create_missing(self, path: Path, attrs: ImageAttributes) -> ElementType:
        "A warning panel for a missing image."

        if attrs.context is FormattingContext.BLOCK:
            message = HTML.p("❌ Missing image: ", HTML.code(path.as_posix()))
            if attrs.caption is not None:
                content = [
                    AC_ELEM(
                        "parameter",
                        {AC_ATTR("name"): "title"},
                        attrs.caption,
                    ),
                    AC_ELEM("rich-text-body", {}, message),
                ]
            else:
                content = [AC_ELEM("rich-text-body", {}, message)]

            return AC_ELEM(
                "structured-macro",
                {
                    AC_ATTR("name"): "warning",
                    AC_ATTR("schema-version"): "1",
                },
                *content,
            )
        else:
            return HTML.span({"style": "color: rgb(255,86,48);"}, "❌ ", HTML.code(path.as_posix()))

    def _transform_code_block(self, code: ElementType) -> ElementType:
        "Transforms a code block."

        if language_class := code.get("class"):
            if m := re.match("^language-(.*)$", language_class):
                language_name = m.group(1)
            else:
                language_name = None
        else:
            language_name = None

        # translate name to standard name for (programming) language
        if language_name is not None:
            language_id = _LANGUAGES.get(language_name)
        else:
            language_id = None

        content: str = code.text or ""
        content = content.rstrip()

        if language_id == "mermaid":
            return self._transform_fenced_mermaid(content)

        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "code",
                AC_ATTR("schema-version"): "1",
            },
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "language"},
                language_id or "none",
            ),
            AC_ELEM("plain-text-body", ET.CDATA(content)),
        )

    def _extract_mermaid_config(self, content: str) -> Optional[MermaidConfigProperties]:
        """Extract scale from Mermaid YAML front matter configuration."""
        try:
            properties = MermaidScanner().read(content)
            return properties.config
        except JsonTypeError as ex:
            LOGGER.warning("Failed to extract Mermaid properties: %s", ex)
            return None

    def _transform_external_mermaid(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        "Emits Confluence Storage Format XHTML for a Mermaid diagram read from an external file."

        if not absolute_path.name.endswith(".mmd") and not absolute_path.name.endswith(".mermaid"):
            raise DocumentError("invalid image format; expected: `*.mmd` or `*.mermaid`")

        relative_path = path_relative_to(absolute_path, self.base_dir)
        if self.options.render_mermaid:
            with open(absolute_path, "r", encoding="utf-8") as f:
                content = f.read()
            config = self._extract_mermaid_config(content)
            image_data = mermaid.render_diagram(content, self.options.diagram_output_format, config=config)
            image_filename = attachment_name(relative_path.with_suffix(f".{self.options.diagram_output_format}"))
            self.embedded_files[image_filename] = EmbeddedFileData(image_data, attrs.alt)
            return self._create_attached_image(image_filename, attrs)
        else:
            self.images.append(ImageData(absolute_path, attrs.alt))
            mermaid_filename = attachment_name(relative_path)
            return self._create_mermaid_embed(mermaid_filename)

    def _transform_fenced_mermaid(self, content: str) -> ElementType:
        "Emits Confluence Storage Format XHTML for a Mermaid diagram defined in a fenced code block."

        if self.options.render_mermaid:
            config = self._extract_mermaid_config(content)
            image_data = mermaid.render_diagram(content, self.options.diagram_output_format, config=config)
            image_hash = hashlib.md5(image_data).hexdigest()
            image_filename = attachment_name(f"embedded_{image_hash}.{self.options.diagram_output_format}")
            self.embedded_files[image_filename] = EmbeddedFileData(image_data)
            return self._create_attached_image(image_filename, ImageAttributes.EMPTY_BLOCK)
        else:
            mermaid_data = content.encode("utf-8")
            mermaid_hash = hashlib.md5(mermaid_data).hexdigest()
            mermaid_filename = attachment_name(f"embedded_{mermaid_hash}.mmd")
            self.embedded_files[mermaid_filename] = EmbeddedFileData(mermaid_data)
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

    def _transform_toc(self, code: ElementType) -> ElementType:
        "Creates a table of contents, constructed from headings in the document."

        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "toc",
                AC_ATTR("schema-version"): "1",
                "data-layout": "default",
            },
            AC_ELEM("parameter", {AC_ATTR("name"): "outline"}, "clear"),
            AC_ELEM("parameter", {AC_ATTR("name"): "style"}, "default"),
        )

    def _transform_listing(self, code: ElementType) -> ElementType:
        "Creates a list of child pages."

        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "children",
                AC_ATTR("schema-version"): "2",
                "data-layout": "default",
            },
            AC_ELEM("parameter", {AC_ATTR("name"): "allChildren"}, "true"),
        )

    def _transform_admonition(self, elem: ElementType) -> ElementType:
        """
        Creates an info, tip, note or warning panel from a Markdown admonition.

        Transforms [Python-Markdown admonition](https://python-markdown.github.io/extensions/admonition/)
        syntax into one of the Confluence structured macros *info*, *tip*, *note*, or *warning*.
        """

        if len(elem) < 1:
            raise DocumentError("empty admonition")

        # <div class="admonition note">
        class_list = elem.get("class", "").split(" ")
        class_list.remove("admonition")
        if len(class_list) > 1:
            raise DocumentError(f"too many admonition types: {class_list}")
        elif len(class_list) < 1:
            raise DocumentError("missing specific admonition type")
        admonition = class_list[0]

        for e in elem:
            self.visit(e)

        # <p class="admonition-title">Note</p>
        if "admonition-title" in elem[0].get("class", "").split(" "):
            content = [HTML.p(HTML.strong(elem[0].text or "")), *list(elem[1:])]
        else:
            content = list(elem)

        if self.options.use_panel:
            return self._transform_panel(content, admonition)
        else:
            admonition_to_csf = {
                "attention": "note",
                "caution": "warning",
                "danger": "warning",
                "error": "warning",
                "hint": "tip",
                "important": "note",
                "info": "info",
                "note": "info",
                "tip": "tip",
                "warning": "note",
            }
            class_name = admonition_to_csf.get(admonition)
            if class_name is None:
                raise DocumentError(f"unsupported admonition type: {admonition}")

            return AC_ELEM(
                "structured-macro",
                {
                    AC_ATTR("name"): class_name,
                    AC_ATTR("schema-version"): "1",
                },
                AC_ELEM("rich-text-body", {}, *content),
            )

    def _transform_github_alert(self, blockquote: ElementType) -> ElementType:
        """
        Creates a GitHub-style panel, normally triggered with a block-quote starting with a capitalized string such as `[!TIP]`.
        """

        if len(blockquote) < 1:
            raise DocumentError("empty GitHub alert")

        content = blockquote[0]
        if content.text is None:
            raise DocumentError("empty content")

        pattern = re.compile(r"^\[!([A-Z]+)\]\s*")
        match = pattern.match(content.text)
        if not match:
            raise DocumentError("not a GitHub alert")

        # remove alert indicator prefix
        content.text = content.text[len(match.group(0)) :]

        for e in blockquote:
            self.visit(e)

        alert = match.group(1)
        if self.options.use_panel:
            return self._transform_panel(list(blockquote), alert.lower())
        else:
            alert_to_csf = {"NOTE": "info", "TIP": "tip", "IMPORTANT": "note", "WARNING": "note", "CAUTION": "warning"}
            class_name = alert_to_csf.get(alert)
            if class_name is None:
                raise DocumentError(f"unsupported GitHub alert: {alert}")

            return self._transform_alert(blockquote, class_name)

    def _transform_gitlab_alert(self, blockquote: ElementType) -> ElementType:
        """
        Creates a classic GitLab-style panel.

        Classic panels are defined with a block-quote and text starting with a capitalized string such as `DISCLAIMER:`.
        This syntax does not use Hugo shortcode.
        """

        if len(blockquote) < 1:
            raise DocumentError("empty GitLab alert")

        content = blockquote[0]
        if content.text is None:
            raise DocumentError("empty content")

        pattern = re.compile(r"^(FLAG|NOTE|WARNING|DISCLAIMER):\s*")
        match = pattern.match(content.text)
        if not match:
            raise DocumentError("not a GitLab alert")

        # remove alert indicator prefix
        content.text = content.text[len(match.group(0)) :]

        for e in blockquote:
            self.visit(e)

        alert = match.group(1)
        if self.options.use_panel:
            return self._transform_panel(list(blockquote), alert.lower())
        else:
            alert_to_csf = {"FLAG": "note", "NOTE": "info", "WARNING": "note", "DISCLAIMER": "info"}
            class_name = alert_to_csf.get(alert)
            if class_name is None:
                raise DocumentError(f"unsupported GitLab alert: {alert}")

            return self._transform_alert(blockquote, class_name)

    def _transform_alert(self, blockquote: ElementType, class_name: str) -> ElementType:
        """
        Creates an `info`, `tip`, `note` or `warning` panel from a GitHub or GitLab alert.

        Transforms GitHub alert or GitLab alert syntax into one of the Confluence structured macros `info`, `tip`, `note`, or `warning`.

        Confusingly, these structured macros have completely different alternate names on the UI, namely: *Info*, *Success*, *Warning* and *Error* (in this
        order). In other words, to get what is shown as *Error* on the UI, you have to pass `warning` in CSF, and to get *Success*, you have to pass `tip`.

        Confluence UI also has an additional panel type called *Note*. *Note* is not a structured macro but corresponds to a different element tree, wrapped in
        an element `ac:adf-extension`:

        ```
        <ac:adf-node type="panel">
            <ac:adf-attribute key="panel-type">note</ac:adf-attribute>
            <ac:adf-content>
                <p><strong>A note</strong></p>
                <p>This is a panel showing a note.</p>
            </ac:adf-content>
        </ac:adf-node>
        ```

        As of today, *md2conf* does not generate `ac:adf-extension` output, including *Note* and *Custom panel* (which shows an emoji selected by the user).

        :param blockquote: HTML element tree to transform to Confluence Storage Format (CSF).
        :param class_name: Corresponds to `name` attribute for CSF `structured-macro`.

        :see: https://docs.github.com/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts
        :see: https://docs.gitlab.com/ee/development/documentation/styleguide/#alert-boxes
        """

        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): class_name,
                AC_ATTR("schema-version"): "1",
            },
            AC_ELEM("rich-text-body", {}, *list(blockquote)),
        )

    def _transform_panel(self, content: list[ElementType], class_name: str) -> ElementType:
        "Transforms a blockquote into a themed panel."

        panel = ConfluencePanel.from_class.get(class_name)
        if panel is None:
            raise DocumentError(f"unsupported panel class: {class_name}")

        macro_id = str(uuid.uuid4())
        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "panel",
                AC_ATTR("schema-version"): "1",
                AC_ATTR("macro-id"): macro_id,
            },
            AC_ELEM("parameter", {AC_ATTR("name"): "panelIcon"}, f":{panel.emoji_shortname}:"),
            AC_ELEM("parameter", {AC_ATTR("name"): "panelIconId"}, panel.emoji_unicode),
            AC_ELEM("parameter", {AC_ATTR("name"): "panelIconText"}, panel.emoji),
            AC_ELEM("parameter", {AC_ATTR("name"): "bgColor"}, panel.background_color),
            AC_ELEM("rich-text-body", {}, *content),
        )

    def _transform_collapsed(self, details: ElementType) -> ElementType:
        """
        Creates a collapsed section.

        Transforms a GitHub collapsed section syntax into the Confluence structured macro *expand*.

        :see: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections
        """

        summary = details[0]
        if summary.tag != "summary":
            raise DocumentError("expected: `<summary>` as first direct child of `<details>`")
        if details.text is not None or summary.tail is not None:
            # when `<details>` has attribute `markdown=1`, content is parsed as Markdown:
            # ```
            # <details>
            #   <summary>...</summary>
            #   <p>Text with <em>emphasis</em>.</p>
            # </details>
            # ```
            #
            # when `<details>` lacks attribute `markdown=1`, content is passed down as raw HTML, partly as `text` of `<detail>` or `tail` of `<summary>`:
            # ```
            # <details>
            #   <summary>...</summary>
            #   Text with *emphasis*.
            # </details>
            raise DocumentError('expected: attribute `markdown="1"` on `<details>`')

        summary_text = element_to_text(summary)
        details.remove(summary)

        # transform Markdown to Confluence within collapsed section content
        self.visit(details)

        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "expand",
                AC_ATTR("schema-version"): "1",
            },
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "title"},
                summary_text,
            ),
            AC_ELEM("rich-text-body", {}, *list(details)),
        )

    def _transform_emoji(self, elem: ElementType) -> ElementType:
        """
        Inserts an inline emoji character.
        """

        shortname = elem.get("data-shortname", "")
        unicode = elem.get("data-unicode", None)
        alt = elem.text or ""

        # emoji with a matching emoticon:
        # <ac:emoticon ac:name="wink" ac:emoji-shortname=":wink:" ac:emoji-id="1f609" ac:emoji-fallback="&#128521;"/>
        #
        # emoji without a corresponding emoticon:
        # <ac:emoticon ac:name="blue-star" ac:emoji-shortname=":shield:" ac:emoji-id="1f6e1" ac:emoji-fallback="&#128737;"/>
        return AC_ELEM(
            "emoticon",
            {
                AC_ATTR("name"): emoji_to_emoticon(shortname),
                AC_ATTR("emoji-shortname"): f":{shortname}:",
                AC_ATTR("emoji-id"): unicode,
                AC_ATTR("emoji-fallback"): alt,
            },
        )

    def _transform_mark(self, mark: ElementType) -> ElementType:
        """
        Adds inline highlighting to text.
        """

        attrs = dict(mark.items())
        old_style = attrs.get("style")
        new_style = "background-color: rgb(254,222,200);"
        if old_style is not None:
            new_style += f" {old_style}"
        attrs["style"] = new_style
        span = HTML("span", attrs, *list(mark))
        span.text = mark.text
        return span

    def _transform_latex(self, elem: ElementType, context: FormattingContext) -> ElementType:
        """
        Creates an image rendering of a LaTeX formula with Matplotlib.
        """

        content = elem.text
        if not content:
            raise DocumentError("empty LaTeX formula")

        image_data = render_latex(content, format=self.options.diagram_output_format)
        if self.options.diagram_output_format == "png":
            width, height = get_png_dimensions(data=image_data)
            image_data = remove_png_chunks(["pHYs"], source_data=image_data)
            attrs = ImageAttributes(context, width=width, height=height, alt=content, title=None, caption="", alignment=ImageAlignment(self.options.alignment))
        else:
            attrs = ImageAttributes.empty(context)

        image_hash = hashlib.md5(image_data).hexdigest()
        image_filename = attachment_name(f"formula_{image_hash}.{self.options.diagram_output_format}")
        self.embedded_files[image_filename] = EmbeddedFileData(image_data, content)
        image = self._create_attached_image(image_filename, attrs)
        return image

    def _transform_inline_math(self, elem: ElementType) -> ElementType:
        """
        Creates an inline LaTeX formula using the Confluence extension "LaTeX Math for Confluence - Math Formula & Equations".

        :see: https://help.narva.net/latex-math-for-confluence/
        """

        content = elem.text
        if not content:
            raise DocumentError("empty inline LaTeX formula")

        LOGGER.debug("Found inline LaTeX formula: %s", content)

        if self.options.render_latex:
            return self._transform_latex(elem, FormattingContext.INLINE)

        local_id = str(uuid.uuid4())
        macro_id = str(uuid.uuid4())
        macro = AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "eazy-math-inline",
                AC_ATTR("schema-version"): "1",
                AC_ATTR("local-id"): local_id,
                AC_ATTR("macro-id"): macro_id,
            },
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "body"},
                content,
            ),
            AC_ELEM("parameter", {AC_ATTR("name"): "align"}, self.options.alignment),
        )
        return macro

    def _transform_block_math(self, elem: ElementType) -> ElementType:
        """
        Creates a block-level LaTeX formula using the Confluence extension "LaTeX Math for Confluence - Math Formula & Equations".

        :see: https://help.narva.net/latex-math-for-confluence/
        """

        content = elem.text
        if not content:
            raise DocumentError("empty block-level LaTeX formula")

        LOGGER.debug("Found block-level LaTeX formula: %s", content)

        if self.options.render_latex:
            return self._transform_latex(elem, FormattingContext.BLOCK)

        local_id = str(uuid.uuid4())
        macro_id = str(uuid.uuid4())

        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "easy-math-block",
                AC_ATTR("schema-version"): "1",
                "data-layout": "default",
                AC_ATTR("local-id"): local_id,
                AC_ATTR("macro-id"): macro_id,
            },
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "body"},
                content,
            ),
            AC_ELEM("parameter", {AC_ATTR("name"): "align"}, self.options.alignment),
        )

    def _transform_footnote_ref(self, elem: ElementType) -> None:
        """
        Transforms a footnote reference.

        ```
        <sup id="fnref:NAME"><a class="footnote-ref" href="#fn:NAME">REF</a></sup>
        ```
        """

        if elem.tag != "sup":
            raise DocumentError("expected: `<sup>` as the HTML element for a footnote reference")

        ref_id = elem.attrib.pop("id", "")
        if not ref_id.startswith("fnref:"):
            raise DocumentError("expected: attribute `id` of format `fnref:NAME` applied on `<sup>` for a footnote reference")
        footnote_ref = ref_id.removeprefix("fnref:")

        link = next((elem.iterchildren(tag="a")), None)
        if link is None:
            raise DocumentError("expected: `<a>` as the first HTML element in a footnote reference")
        def_href = link.attrib.pop("href", "")
        if not def_href.startswith("#fn:"):
            raise DocumentError("expected: attribute `href` of format `#fn:NAME` applied on `<a>` for a footnote reference")
        footnote_def = def_href.removeprefix("#fn:")

        text = link.text or ""

        # remove link generated by Python-Markdown
        elem.remove(link)

        # build new anchor for footnote reference
        ref_anchor = AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "anchor",
                AC_ATTR("schema-version"): "1",
            },
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): ""},
                f"footnote-ref-{footnote_ref}",
            ),
        )

        # build new link to footnote definition at the end of page
        def_link = AC_ELEM(
            "link",
            {
                AC_ATTR("anchor"): f"footnote-def-{footnote_def}",
            },
            AC_ELEM("link-body", ET.CDATA(text)),
        )

        # append children synthesized for Confluence
        elem.append(ref_anchor)
        elem.append(def_link)

    def _transform_footnote_def(self, elem: ElementType) -> None:
        """
        Transforms the footnote definition block.

        ```
        <div class="footnote">
            <hr/>
            <ol>
                <li id="fn:NAME">
                    <p>TEXT <a class="footnote-backref" href="#fnref:NAME">↩</a></p>
                </li>
            </ol>
        </div>
        ```
        """

        ordered_list = next((elem.iterchildren(tag="ol")), None)
        if ordered_list is None:
            raise DocumentError("expected: `<ol>` as direct child of footnote definition block")

        for list_item in ordered_list:
            if list_item.tag != "li":
                raise DocumentError("expected: `<li>` as children of `<ol>` in footnote definition block")

            def_id = list_item.attrib.pop("id", "")
            if not def_id.startswith("fn:"):
                raise DocumentError("expected: attribute `id` of format `fn:NAME` applied on `<li>` for a footnote definition")
            footnote_def = def_id.removeprefix("fn:")

            paragraph = next((list_item.iterchildren(tag="p")), None)
            if paragraph is None:
                raise DocumentError("expected: `<p>` as a child of `<li>` in a footnote definition")

            ref_anchor = next((paragraph.iterchildren(tag="a", reversed=True)), None)
            if ref_anchor is None:
                raise DocumentError("expected: `<a>` as the last HTML element in a footnote definition")

            ref_href = ref_anchor.get("href", "")
            if not ref_href.startswith("#fnref:"):
                raise DocumentError("expected: attribute `href` of format `#fnref:NAME` applied on last element `<a>` for a footnote definition")
            footnote_ref = ref_href.removeprefix("#fnref:")

            # remove back-link generated by Python-Markdown
            paragraph.remove(ref_anchor)

            # build new anchor for footnote definition
            def_anchor = AC_ELEM(
                "structured-macro",
                {
                    AC_ATTR("name"): "anchor",
                    AC_ATTR("schema-version"): "1",
                },
                AC_ELEM(
                    "parameter",
                    {AC_ATTR("name"): ""},
                    f"footnote-def-{footnote_def}",
                ),
            )

            # build new link to footnote reference in page body
            ref_link = AC_ELEM(
                "link",
                {
                    AC_ATTR("anchor"): f"footnote-ref-{footnote_ref}",
                },
                AC_ELEM("link-body", ET.CDATA("↩")),
            )

            # append children synthesized for Confluence
            paragraph.insert(0, def_anchor)
            def_anchor.tail = paragraph.text
            paragraph.text = None
            paragraph.append(ref_link)

    def _transform_tasklist(self, elem: ElementType) -> ElementType:
        """
        Transforms a list of tasks into an action widget.

        :see: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/about-tasklists
        """

        if elem.tag != "ul":
            raise DocumentError("expected: `<ul>` as the HTML element for a tasklist")

        for item in elem:
            if item.tag != "li":
                raise DocumentError("expected: `<li>` as the HTML element for a task")
            if not element_text_starts_with_any(item, ["[ ]", "[x]", "[X]"]):
                raise DocumentError("expected: each `<li>` in a task list starting with [ ] or [x]")

        tasks: list[ElementType] = []
        for index, item in enumerate(elem, start=1):
            if item.text is None:
                raise NotImplementedError("pre-condition check not exhaustive")
            match = re.match(r"^\[([x X])\]", item.text)
            if match is None:
                raise NotImplementedError("pre-condition check not exhaustive")

            status = "incomplete" if match.group(1).isspace() else "complete"
            item.text = item.text[3:]

            # transform Markdown to Confluence within tasklist content
            self.visit(item)

            body = AC_ELEM("task-body", *list(item))
            body.text = item.text
            tasks.append(
                AC_ELEM(
                    "task",
                    {},
                    AC_ELEM("task-id", str(index)),
                    AC_ELEM("task-uuid", str(uuid.uuid4())),
                    AC_ELEM("task-status", status),
                    body,
                ),
            )
        return AC_ELEM("task-list", {}, *tasks)

    @override
    def transform(self, child: ElementType) -> Optional[ElementType]:
        """
        Transforms an HTML element tree obtained from a Markdown document into a Confluence Storage Format element tree.
        """

        # replace line breaks with regular space in element text to minimize phantom changes
        if child.text:
            child.text = child.text.replace("\n", " ")
        if child.tail:
            child.tail = child.tail.replace("\n", " ")

        if not isinstance(child.tag, str):
            return None

        # <p>...</p>
        if child.tag == "p":
            # <p><img src="..." /></p>
            if len(child) == 1 and not child.text and child[0].tag == "img" and not child[0].tail:
                return self._transform_image(FormattingContext.BLOCK, child[0])

            # <p>[[<em>TOC</em>]]</p> (represented in Markdown as `[[_TOC_]]`)
            elif is_placeholder_for(child, "TOC"):
                return self._transform_toc(child)

            # <p>[[<em>LISTING</em>]]</p> (represented in Markdown as `[[_LISTING_]]`)
            elif is_placeholder_for(child, "LISTING"):
                return self._transform_listing(child)

        # <div>...</div>
        elif child.tag == "div":
            classes = child.get("class", "").split(" ")

            # <div class="arithmatex">...</div>
            if "arithmatex" in classes:
                return self._transform_block_math(child)

            # <div><ac:structured-macro ...>...</ac:structured-macro></div>
            elif "csf" in classes:
                if len(child) != 1:
                    raise DocumentError("expected: single child in Confluence Storage Format block")

                return child[0]

            # <div class="footnote">
            #   <hr/>
            #   <ol>
            #     <li id="fn:NAME"><p>TEXT <a class="footnote-backref" href="#fnref:NAME">↩</a></p></li>
            #   </ol>
            # </div>
            elif "footnote" in classes:
                self._transform_footnote_def(child)
                return None

            # <div class="admonition note">
            # <p class="admonition-title">Note</p>
            # <p>...</p>
            # </div>
            #
            # --- OR ---
            #
            # <div class="admonition note">
            # <p>...</p>
            # </div>
            elif "admonition" in classes:
                return self._transform_admonition(child)

        # <blockquote>...</blockquote>
        elif child.tag == "blockquote":
            # Alerts in GitHub
            # <blockquote>
            #   <p>[!TIP] ...</p>
            # </blockquote>
            if len(child) > 0 and child[0].tag == "p" and child[0].text is not None and child[0].text.startswith("[!"):
                return self._transform_github_alert(child)

            # Alerts in GitLab
            # <blockquote>
            #   <p>DISCLAIMER: ...</p>
            # </blockquote>
            elif len(child) > 0 and child[0].tag == "p" and element_text_starts_with_any(child[0], ["FLAG:", "NOTE:", "WARNING:", "DISCLAIMER:"]):
                return self._transform_gitlab_alert(child)

        # <details markdown="1">
        # <summary>...</summary>
        # ...
        # </details>
        elif child.tag == "details" and len(child) > 1 and child[0].tag == "summary":
            return self._transform_collapsed(child)

        # <ol>...</ol>
        elif child.tag == "ol":
            # Confluence adds the attribute `start` for every ordered list
            child.set("start", "1")
            return None

        # <ul>
        #   <li>[ ] ...</li>
        #   <li>[x] ...</li>
        # </ul>
        elif child.tag == "ul":
            if len(child) > 0 and element_text_starts_with_any(child[0], ["[ ]", "[x]", "[X]"]):
                return self._transform_tasklist(child)

            return None

        elif child.tag == "li":
            normalize_inline(child)
            return None

        # <pre><code class="language-java"> ... </code></pre>
        elif child.tag == "pre" and len(child) == 1 and child[0].tag == "code":
            return self._transform_code_block(child[0])

        # <table>...</table>
        elif child.tag == "table":
            for td in child.iterdescendants("td", "th"):
                normalize_inline(td)
            child.set("data-layout", "default")
            return None

        # <img src="..." alt="..." />
        elif child.tag == "img":
            return self._transform_image(FormattingContext.INLINE, child)

        # <a href="..."> ... </a>
        elif child.tag == "a":
            return self._transform_link(child)

        # <mark>...</mark>
        elif child.tag == "mark":
            return self._transform_mark(child)

        # <span>...</span>
        elif child.tag == "span":
            classes = child.get("class", "").split(" ")

            # <span class="arithmatex">...</span>
            if "arithmatex" in classes:
                return self._transform_inline_math(child)

        # <sup id="fnref:NAME"><a class="footnote-ref" href="#fn:NAME">1</a></sup>
        elif child.tag == "sup" and child.get("id", "").startswith("fnref:"):
            self._transform_footnote_ref(child)
            return None

        # <input type="date" value="1984-01-01" />
        elif child.tag == "input" and child.get("type", "") == "date":
            return HTML("time", {"datetime": child.get("value", "")})

        # <ins>...</ins>
        elif child.tag == "ins":
            # Confluence prefers <u> over <ins> for underline, and replaces <ins> with <u>
            child.tag = "u"

        # <x-emoji data-shortname="wink" data-unicode="1f609">😉</x-emoji>
        elif child.tag == "x-emoji":
            return self._transform_emoji(child)

        # <h1>...</h1>
        # <h2>...</h2> ...
        m = re.match(r"^h([1-6])$", child.tag, flags=re.IGNORECASE)
        if m is not None:
            level = int(m.group(1))
            title = element_to_text(child)
            self.toc.add(level, title)

            if self.options.heading_anchors:
                self._transform_heading(child)
                return None

        return None


class DocumentError(RuntimeError):
    "Raised when a converted Markdown document has an unexpected element or attribute."


class ConversionError(RuntimeError):
    "Raised when a Markdown document cannot be converted to Confluence Storage Format."


class ConfluenceDocument:
    "Encapsulates an element tree for a Confluence document created by parsing a Markdown document."

    title: Optional[str]
    labels: Optional[list[str]]
    properties: Optional[dict[str, JsonType]]

    links: list[str]
    images: list[ImageData]
    embedded_files: dict[str, EmbeddedFileData]

    options: ConfluenceDocumentOptions
    root: ElementType

    @classmethod
    def create(
        cls,
        path: Path,
        options: ConfluenceDocumentOptions,
        root_dir: Path,
        site_metadata: ConfluenceSiteMetadata,
        page_metadata: ConfluencePageCollection,
    ) -> tuple[ConfluencePageID, "ConfluenceDocument"]:
        path = path.resolve(True)

        document = Scanner().read(path)

        if document.page_id is not None:
            page_id = ConfluencePageID(document.page_id)
        else:
            # look up Confluence page ID in metadata
            metadata = page_metadata.get(path)
            if metadata is not None:
                page_id = ConfluencePageID(metadata.page_id)
            else:
                raise PageError("missing Confluence page ID")

        return page_id, ConfluenceDocument(path, document, options, root_dir, site_metadata, page_metadata)

    def __init__(
        self,
        path: Path,
        document: ScannedDocument,
        options: ConfluenceDocumentOptions,
        root_dir: Path,
        site_metadata: ConfluenceSiteMetadata,
        page_metadata: ConfluencePageCollection,
    ) -> None:
        "Converts a single Markdown document to Confluence Storage Format."

        self.options = options

        # register auxiliary URL substitutions
        lines: list[str] = []
        for data_uri, color in status_images.items():
            lines.append(f"[STATUS-{color.upper()}]: {data_uri}")
        lines.append(document.text)

        # parse Markdown document and convert to HTML
        html = markdown_to_html("\n".join(lines))

        # modify HTML as necessary
        if self.options.generated_by is not None:
            generated_by = document.generated_by or self.options.generated_by
        else:
            generated_by = None

        if generated_by is not None:
            generated_by_html = markdown_to_html(generated_by)

            content = [
                '<ac:structured-macro ac:name="info" ac:schema-version="1">',
                f"<ac:rich-text-body>{generated_by_html}</ac:rich-text-body>",
                "</ac:structured-macro>",
                html,
            ]
        else:
            content = [html]

        # parse HTML into element tree
        try:
            self.root = elements_from_strings(content)
        except ParseError as ex:
            raise ConversionError(path) from ex

        # configure HTML-to-Confluence converter
        converter_options = ConfluenceConverterOptions(
            **{field.name: getattr(self.options, field.name) for field in dataclasses.fields(ConfluenceConverterOptions)}
        )
        if document.alignment is not None:
            converter_options.alignment = document.alignment
        converter = ConfluenceStorageFormatConverter(converter_options, path, root_dir, site_metadata, page_metadata)

        # execute HTML-to-Confluence converter
        try:
            converter.visit(self.root)
        except DocumentError as ex:
            raise ConversionError(path) from ex

        # extract information discovered by converter
        self.links = converter.links
        self.images = converter.images
        self.embedded_files = converter.embedded_files

        # assign global properties for document
        self.title = document.title or converter.toc.get_title()
        self.labels = document.tags
        self.properties = document.properties

    def xhtml(self) -> str:
        return elements_to_string(self.root)


def attachment_name(ref: Union[Path, str]) -> str:
    """
    Safe name for use with attachment uploads.

    Mutates a relative path such that it meets Confluence's attachment naming requirements.

    Allowed characters:

    * Alphanumeric characters: 0-9, a-z, A-Z
    * Special characters: hyphen (-), underscore (_), period (.)
    """

    if isinstance(ref, Path):
        path = ref
    else:
        path = Path(ref)

    if path.drive or path.root:
        raise ValueError(f"required: relative path; got: {ref}")

    regexp = re.compile(r"[^\-0-9A-Za-z_.]", re.UNICODE)

    def replace_part(part: str) -> str:
        if part == "..":
            return "PAR"
        else:
            return regexp.sub("_", part)

    parts = [replace_part(p) for p in path.parts]
    return Path(*parts).as_posix().replace("/", "_")
