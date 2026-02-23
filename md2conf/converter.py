"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import copy
import logging
import os.path
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import ClassVar
from urllib.parse import ParseResult, quote_plus, urlparse

import lxml.etree as ET

from .attachment import AttachmentCatalog, EmbeddedFileData, ImageData, attachment_name
from .coalesce import coalesce
from .collection import ConfluencePageCollection
from .compatibility import override, path_relative_to
from .csf import AC_ATTR, AC_ELEM, HTML, RI_ATTR, RI_ELEM, ParseError, elements_from_strings, elements_to_string, normalize_inline
from .drawio.extension import DrawioExtension
from .emoticon import emoji_to_emoticon
from .environment import PageError
from .extension import ExtensionOptions, MarketplaceExtension
from .formatting import FormattingContext, ImageAlignment, ImageAttributes
from .image import ImageGenerator, ImageGeneratorOptions
from .latex import render_latex
from .markdown import markdown_to_html, markdown_with_line_numbers
from .mermaid.extension import MermaidExtension
from .metadata import ConfluenceSiteMetadata
from .options import ConfluencePageID, ConverterOptions, ProcessorOptions
from .plantuml.extension import PlantUMLExtension
from .png import remove_png_chunks
from .scanner import ScannedDocument, Scanner
from .serializer import JsonType
from .toc import TableOfContentsBuilder
from .uri import is_absolute_url, to_uuid_urn
from .xml import element_to_text, remove_element

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]


def apply_generated_by_template(template: str, path: Path) -> str:
    """Apply template substitution to the generated_by string.

    Supported placeholders:
    - %{filepath}: Full path to the file (relative to the source directory)
    - %{filename}: Just the filename
    - %{filedir}: Dirname of the full path to the file (relative to the source directory)
    - %{filestem}: Just the filename without the extension

    :param template: The template string with placeholders
    :param path: The path to the file being converted
    :returns: The template string with placeholders replaced
    """

    return (
        template.replace("%{filepath}", path.as_posix())
        .replace("%{filename}", path.name)
        .replace("%{filedir}", path.parent.as_posix())
        .replace("%{filestem}", path.stem)
    )


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


def get_orderless_elements() -> list[str]:
    "Returns a list of order-insensitive elements whose children can appear in any order for the element to compare equal to another."

    return [AC_ATTR("structured-macro")]


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


def fix_absolute_path(path: Path, root_path: Path) -> Path:
    "Make absolute path relative to another root path."

    return root_path / path.relative_to(path.root)


_UNSAFE_CHAR_REGEXP = re.compile(r"[^A-Za-z0-9._~()'!*:@,;+?-]+")
_MULTIPLE_SPACE_REGEXP = re.compile(r"\s\s+")


def encode_title(text: str) -> str:
    "Converts a title string such that it is safe to embed into a Confluence URL."

    # replace unsafe characters with space
    text = _UNSAFE_CHAR_REGEXP.sub(" ", text)

    # replace multiple consecutive spaces with single space
    text = _MULTIPLE_SPACE_REGEXP.sub(" ", text)

    # URL-encode
    return quote_plus(text.strip())


# supported code block languages, for which syntax highlighting is available
# spellchecker: disable
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
    "dockerfile": "dockerfile",
    "elixir": "elixir",
    "erl": "erl",
    "erlang": "erl",
    "fortran": "fortran",
    "foxpro": "foxpro",
    "gherkin": "gherkin",
    "go": "go",
    "graphql": "graphql",
    "groovy": "groovy",
    "handlebars": "handlebars",
    "haskell": "haskell",
    "haxe": "haxe",
    "hcl": "hcl",
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
    "protobuf": "protobuf",
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
    "toml": "toml",
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
# spellchecker: enable


class ElementAction(Enum):
    "Captures standard actions a node visitor may take with the element."

    RECURSE = "recurse"
    REMOVE = "remove"


class NodeVisitor(ABC):
    def visit(self, node: ElementType) -> None:
        "Recursively visits all descendants of this node."

        if len(node) < 1:
            return

        index = 0
        count = len(node)
        while index < count:
            source = node[index]
            target = self.transform(source)
            if isinstance(target, ElementAction):
                match target:
                    case ElementAction.RECURSE:
                        # recurse into the element
                        self.visit(source)
                        index += 1
                    case ElementAction.REMOVE:
                        # remove the element from the tree
                        remove_element(source)
                        count -= 1
            else:
                # chain sibling text node that immediately follows original element
                target.tail = source.tail
                source.tail = None

                # replace original element with transformed element
                node[index] = target
                index += 1

    @abstractmethod
    def transform(self, child: ElementType) -> ElementType | ElementAction: ...


_DISALLOWED_CHAR_REGEXP = re.compile(r"[^\sA-Za-z0-9_\-]")
_SPACE_COLLAPSE_REGEXP = re.compile(r"\s+")


def title_to_identifier(title: str) -> str:
    "Converts a section heading title to a GitHub-style Markdown same-page anchor."

    s = title.strip().lower()
    s = _DISALLOWED_CHAR_REGEXP.sub("", s)
    s = _SPACE_COLLAPSE_REGEXP.sub("-", s)
    return s


def element_text_starts_with_any(node: ElementType, prefixes: list[str]) -> bool:
    "True if the text contained in an element starts with any of the specified prefix strings."

    if node.text is None:
        return False
    return starts_with_any(node.text, prefixes)


def child_count(node: ElementType) -> int:
    "Number of children, excluding special elements."

    return len(node) - sum(1 for _ in node.iterchildren("line-number"))


def is_placeholder_for(node: ElementType, name: str) -> bool:
    """
    Identifies a Confluence widget placeholder, e.g. `[[_TOC_]]` or `[[_LISTING_]]`.

    :param node: The element to check.
    :param name: The placeholder name.
    """

    # `[[_TOC_]]` is represented in HTML as <p>[[<em>TOC</em>]]</p>
    if node.text != "[[" or child_count(node) != 1:
        return False

    child = node[0]
    if child.tag != "em" or child.text != name or child.tail != "]]":
        return False

    return True


class PreprocessingError(RuntimeError):
    "Raised when a preprocessing step has failed."


class DocumentError(RuntimeError):
    "Raised when a converted Markdown document has an unexpected element or attribute."

    element: ElementType

    def __init__(self, element: ElementType, message: str) -> None:
        super().__init__(message)
        self.element = element


class ConversionError(RuntimeError):
    "Raised when a Markdown document cannot be converted to Confluence Storage Format."


def transform_skip_comments_in_html(html: str) -> str:
    """
    Transforms HTML comments marking skip sections into custom elements.

    From:
    ```
        <!-- confluence-skip-start --> ... <!-- confluence-skip-end -->
    ```
    Into:
    ```
        <confluence-skip> ... </confluence-skip>
    ```

    This must run BEFORE the HTML (generated from Markdown) is parsed, as the XML parser strips comments (remove_comments=True).

    :param html: HTML string with skip comment markers.
    :returns: HTML string with comments replaced by custom elements.
    """

    start_pattern = re.compile(r"<!--\s*confluence-skip-start\s*-->")
    end_pattern = re.compile(r"<!--\s*confluence-skip-end\s*-->")

    start_count = sum(1 for _ in start_pattern.finditer(html))
    end_count = sum(1 for _ in end_pattern.finditer(html))

    if start_count != end_count:
        raise PreprocessingError(f"unmatched confluence-skip markers: found {start_count} start marker(s) and {end_count} end marker(s)")

    if start_count < 1:
        return html

    skip_pattern = re.compile(r"<!--\s*confluence-skip-start\s*-->(.*?)<!--\s*confluence-skip-end\s*-->", flags=re.DOTALL)
    html = skip_pattern.sub(r"<confluence-skip>\1</confluence-skip>", html)

    return html


_FOOTNOTE_REF_REGEXP = re.compile(r"^fnref(\d*):(.+)$")
_TASKLIST_REGEXP = re.compile(r"^\[([x X])\]")


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
    "attention": ConfluencePanel("❗", "exclamation", "var(--ds-background-accent-gray-subtlest)"),  # rST admonition
    "abstract": ConfluencePanel("📄", "page_facing_up", "var(--ds-background-accent-teal-subtlest)"),  # Material for MkDocs
    "bug": ConfluencePanel("🐛", "bug", "var(--ds-background-accent-red-subtlest)"),  # Material for MkDocs
    "caution": ConfluencePanel("❌", "x", "var(--ds-background-accent-orange-subtlest)"),
    "danger": ConfluencePanel("☠️", "skull_crossbones", "var(--ds-background-accent-red-subtlest)"),  # rST admonition
    "disclaimer": ConfluencePanel("❗", "exclamation", "var(--ds-background-accent-gray-subtlest)"),  # GitLab
    "error": ConfluencePanel("❌", "x", "var(--ds-background-accent-red-subtlest)"),  # rST admonition
    "example": ConfluencePanel("💡", "bulb", "var(--ds-background-accent-purple-subtlest)"),  # Material for MkDocs
    "failure": ConfluencePanel("❌", "x", "var(--ds-background-accent-red-subtlest)"),  # Material for MkDocs
    "flag": ConfluencePanel("🚩", "triangular_flag_on_post", "var(--ds-background-accent-orange-subtlest"),  # GitLab
    "hint": ConfluencePanel("💡", "bulb", "var(--ds-background-accent-green-subtlest)"),  # rST admonition
    "info": ConfluencePanel("ℹ️", "information_source", "var(--ds-background-accent-blue-subtlest)"),
    "note": ConfluencePanel("📝", "pencil", "var(--ds-background-accent-teal-subtlest)"),
    "question": ConfluencePanel("❓", "question", "var(--ds-background-accent-green-subtlest)"),  # Material for MkDocs
    "quote": ConfluencePanel("💬", "speech_balloon", "var(--ds-background-accent-gray-subtlest)"),  # Material for MkDocs
    "success": ConfluencePanel("✅", "white_check_mark", "var(--ds-background-accent-green-subtlest)"),  # Material for MkDocs
    "tip": ConfluencePanel("💡", "bulb", "var(--ds-background-accent-green-subtlest)"),
    "important": ConfluencePanel("❗", "exclamation", "var(--ds-background-accent-purple-subtlest)"),
    "warning": ConfluencePanel("⚠️", "warning", "var(--ds-background-accent-yellow-subtlest)"),
}


class ConfluenceStorageFormatConverter(NodeVisitor):
    "Transforms a plain HTML tree into Confluence Storage Format."

    options: ConverterOptions
    path: Path
    base_dir: Path
    root_dir: Path
    toc: TableOfContentsBuilder
    links: list[str]
    attachments: AttachmentCatalog
    site_metadata: ConfluenceSiteMetadata
    page_metadata: ConfluencePageCollection

    image_generator: ImageGenerator
    extensions: list[MarketplaceExtension]

    def __init__(
        self,
        options: ConverterOptions,
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
        self.attachments = AttachmentCatalog()
        self.site_metadata = site_metadata
        self.page_metadata = page_metadata

        self.image_generator = ImageGenerator(
            self.base_dir,
            self.attachments,
            ImageGeneratorOptions(self.options.diagram_output_format, self.options.prefer_raster, self.options.layout.image.max_width),
        )

        self.extensions = [
            DrawioExtension(self.image_generator, ExtensionOptions(render=self.options.render_drawio)),
            MermaidExtension(self.image_generator, ExtensionOptions(render=self.options.render_mermaid)),
            PlantUMLExtension(self.image_generator, ExtensionOptions(render=self.options.render_plantuml)),
        ]

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

        if self.options.force_valid_url:
            raise DocumentError(anchor, msg)
        else:
            LOGGER.warning(msg)
            if anchor.text:
                anchor.text = "❌ " + anchor.text
            elif len(anchor) > 0:
                anchor.text = "❌ "

    def _transform_link(self, anchor: ElementType) -> ElementType | None:
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
        if relative_url.path.startswith("/"):
            absolute_path = fix_absolute_path(path=Path(relative_url.path), root_path=self.root_dir).resolve()
        else:
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

    def _transform_page_link(self, anchor: ElementType, relative_url: ParseResult, absolute_path: Path) -> ElementType | None:
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
                raise DocumentError(anchor, "Confluence space key required for building full web URLs")

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

    def _transform_attachment_link(self, anchor: ElementType, absolute_path: Path) -> ElementType | None:
        """
        Transforms links to document binaries such as PDF, DOCX or XLSX.
        """

        if not absolute_path.exists():
            self._anchor_warn_or_raise(anchor, f"relative URL points to non-existing file: {absolute_path}")
            return None

        file_name = attachment_name(path_relative_to(absolute_path, self.base_dir))
        self.attachments.add_image(ImageData(absolute_path))

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

    def _transform_card(self, paragraph: ElementType) -> ElementType | None:
        """
        Transforms stand-alone absolute links that fully occupy a paragraph into a preview card.
        """

        anchor = paragraph[0]
        url = anchor.get("href")
        if url is not None and is_absolute_url(url):
            return HTML("a", {"href": url, "data-card-appearance": "block"}, anchor.text or url)
        else:
            return None

    def _transform_image(self, context: FormattingContext, image: ElementType) -> ElementType:
        "Inserts an attached or external image."

        src = image.get("src")
        if not src:
            raise DocumentError(image, "image lacks `src` attribute")

        alt = image.get("alt")
        if alt is not None and src.startswith("urn:uuid:") and (color := status_images.get(src)) is not None:
            return self._transform_status(color, alt)

        title = image.get("title")
        width = image.get("width")
        height = image.get("height")
        pixel_width = int(width) if width is not None and width.isdecimal() else None
        pixel_height = int(height) if height is not None and height.isdecimal() else None
        attrs = ImageAttributes(
            context,
            width=pixel_width,
            height=pixel_height,
            alt=alt,
            title=title,
            caption=None,
            alignment=ImageAlignment(self.options.layout.get_image_alignment()),
        )

        if is_absolute_url(src):
            return self._transform_external_image(src, attrs)
        else:
            path = Path(src)

            absolute_path = self._verify_image_path(image, path)
            if absolute_path is None:
                return self._create_missing(path, attrs)

            for extension in self.extensions:
                if extension.matches_image(absolute_path):
                    return extension.transform_image(absolute_path, attrs)

            return self.image_generator.transform_attached_image(absolute_path, attrs)

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

        return AC_ELEM("image", attrs.as_dict(max_width=self.options.layout.image.max_width), *elements)

    def _warn_or_raise(self, image: ElementType, msg: str) -> None:
        "Emit a warning or raise an exception when a path points to a resource that doesn't exist or is outside of the permitted hierarchy."

        if self.options.force_valid_url:
            raise DocumentError(image, msg)
        else:
            LOGGER.warning(msg)

    def _verify_image_path(self, image: ElementType, path: Path) -> Path | None:
        "Checks whether an image path is safe to use."

        if path.is_absolute():
            absolute_path = fix_absolute_path(path=path, root_path=self.root_dir).resolve()
        else:
            # resolve relative path into absolute path w.r.t. base dir
            absolute_path = (self.base_dir / path).resolve()

        if not absolute_path.exists():
            self._warn_or_raise(image, f"path to image does not exist: {path}")
            return None

        if not is_directory_within(absolute_path, self.root_dir):
            self._warn_or_raise(image, f"path to image {path} points to outside root path {self.root_dir}")
            return None

        return absolute_path

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

        content: str = code.text or ""
        content = content.rstrip()

        if language_class := code.get("class"):
            if m := re.match("^language-(.*)$", language_class):
                language_name = m.group(1)
            else:
                language_name = None
        else:
            language_name = None

        # translate name to standard name for (programming) language
        if language_name is not None:
            for extension in self.extensions:
                if extension.matches_fenced(language_name, content):
                    return extension.transform_fenced(content)

            language_id = _LANGUAGES.get(
                language_name,
                None if self.options.force_valid_language else language_name,
            )
        else:
            language_id = None

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
            raise DocumentError(elem, "empty admonition")

        # <div class="admonition note">
        class_list = elem.get("class", "").split(" ")
        class_list.remove("admonition")
        if len(class_list) > 1:
            raise DocumentError(elem, f"too many admonition types: {class_list}")
        elif len(class_list) < 1:
            raise DocumentError(elem, "missing specific admonition type")
        admonition = class_list[0]

        for e in elem:
            self.visit(e)

        # <p class="admonition-title">Note</p>
        if "admonition-title" in elem[0].get("class", "").split(" "):
            content = [HTML.p(HTML.strong(elem[0].text or "")), *list(elem[1:])]
            elem.clear(keep_tail=True)
            elem.extend(content)

        if self.options.use_panel:
            return self._transform_panel(elem, admonition)
        else:
            # === Note to maintainers: ===
            #
            # Confluence Storage Format types used as values in the dictionary below are extremely counter-intuitive.
            # The visual representation in a Confluence page does not correspond to what words such as "note", "tip"
            # or "warning" might suggest. Specifically,
            #
            # * "info": a lowercase "i" shown in a blue circle
            # * "note": an exclamation mark "!" shown in an orange triangle
            # * "tip": a check-mark shown in a green circle
            # * "warning": a lowercase "x" shown in a red circle

            admonition_to_csf = {
                "attention": "note",
                "abstract": "info",
                "bug": "warning",
                "caution": "warning",
                "danger": "warning",
                "error": "warning",
                "example": "info",
                "failure": "warning",
                "hint": "tip",
                "important": "note",
                "info": "info",
                "note": "info",
                "question": "info",
                "quote": "info",
                "success": "tip",
                "tip": "tip",
                "warning": "note",
            }
            class_name = admonition_to_csf.get(admonition)
            if class_name is None:
                raise DocumentError(elem, f"unsupported admonition type: {admonition}")

            return AC_ELEM(
                "structured-macro",
                {
                    AC_ATTR("name"): class_name,
                    AC_ATTR("schema-version"): "1",
                },
                AC_ELEM("rich-text-body", {}, *list(elem)),
            )

    def _transform_github_alert(self, blockquote: ElementType) -> ElementType:
        """
        Creates a GitHub-style panel, normally triggered with a block-quote starting with a capitalized string such as `[!TIP]`.
        """

        for e in blockquote:
            self.visit(e)

        if len(blockquote) < 1:
            raise DocumentError(blockquote, "empty GitHub alert")

        content = blockquote[0]
        if content.text is None:
            raise DocumentError(blockquote, "empty content for GitHub alert")

        pattern = re.compile(r"^\[!([A-Z]+)\]\s*")
        match = pattern.match(content.text)
        if not match:
            raise DocumentError(blockquote, "not a GitHub alert")
        alert = match.group(1)

        # remove alert indicator prefix
        content.text = content.text[len(match.group(0)) :]

        if self.options.use_panel:
            return self._transform_panel(blockquote, alert.lower())
        else:
            alert_to_csf = {"NOTE": "info", "TIP": "tip", "IMPORTANT": "note", "WARNING": "note", "CAUTION": "warning"}
            class_name = alert_to_csf.get(alert)
            if class_name is None:
                raise DocumentError(blockquote, f"unsupported GitHub alert: {alert}")

            return self._transform_alert(blockquote, class_name)

    def _transform_gitlab_alert(self, blockquote: ElementType) -> ElementType:
        """
        Creates a classic GitLab-style panel.

        Classic panels are defined with a block-quote and text starting with a capitalized string such as `DISCLAIMER:`.
        This syntax does not use Hugo shortcode.
        """

        for e in blockquote:
            self.visit(e)

        if len(blockquote) < 1:
            raise DocumentError(blockquote, "empty GitLab alert")

        content = blockquote[0]
        if content.text is None:
            raise DocumentError(blockquote, "empty content for GitLab alert")

        pattern = re.compile(r"^(FLAG|NOTE|WARNING|DISCLAIMER):\s*")
        match = pattern.match(content.text)
        if not match:
            raise DocumentError(blockquote, "not a GitLab alert")
        alert = match.group(1)

        # remove alert indicator prefix
        content.text = content.text[len(match.group(0)) :]

        if self.options.use_panel:
            return self._transform_panel(blockquote, alert.lower())
        else:
            alert_to_csf = {"FLAG": "note", "NOTE": "info", "WARNING": "note", "DISCLAIMER": "info"}
            class_name = alert_to_csf.get(alert)
            if class_name is None:
                raise DocumentError(blockquote, f"unsupported GitLab alert: {alert}")

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

    def _transform_panel(self, elem: ElementType, class_name: str) -> ElementType:
        "Transforms a blockquote into a themed panel."

        panel = ConfluencePanel.from_class.get(class_name)
        if panel is None:
            raise DocumentError(elem, f"unsupported panel class: {class_name}")

        macro_id = str(uuid.uuid4())
        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "panel",
                AC_ATTR("schema-version"): "1",
                AC_ATTR("macro-id"): macro_id,
            },
            AC_ELEM("parameter", {AC_ATTR("name"): "panelIconId"}, panel.emoji_unicode),
            AC_ELEM("parameter", {AC_ATTR("name"): "panelIcon"}, f":{panel.emoji_shortname}:"),
            AC_ELEM("parameter", {AC_ATTR("name"): "panelIconText"}, panel.emoji),
            AC_ELEM("parameter", {AC_ATTR("name"): "bgColor"}, panel.background_color),
            AC_ELEM("rich-text-body", {}, *list(elem)),
        )

    def _transform_collapsed(self, details: ElementType) -> ElementType:
        """
        Creates a collapsed section.

        Transforms a GitHub collapsed section syntax into the Confluence structured macro *expand*.

        :see: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections
        """

        summary = details[0]
        if summary.tag != "summary":
            raise DocumentError(details, "expected: `<summary>` as first direct child of `<details>`")
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
            raise DocumentError(details, 'expected: attribute `markdown="1"` on `<details>`')

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
            raise DocumentError(elem, "empty LaTeX formula")

        image_data = render_latex(content, format=self.options.diagram_output_format)
        if self.options.diagram_output_format == "png":
            image_data = remove_png_chunks(["pHYs"], source_data=image_data)

        attrs = ImageAttributes(
            context,
            width=None,
            height=None,
            alt=content,
            title=None,
            caption="",
            alignment=ImageAlignment(self.options.layout.get_image_alignment()),
        )
        return self.image_generator.transform_attached_data(image_data, attrs, image_type="formula")

    def _transform_inline_math(self, elem: ElementType) -> ElementType:
        """
        Creates an inline LaTeX formula using the Confluence extension "LaTeX Math for Confluence - Math Formula & Equations".

        :see: https://help.narva.net/latex-math-for-confluence/
        """

        content = elem.text
        if not content:
            raise DocumentError(elem, "empty inline LaTeX formula")

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
            AC_ELEM("parameter", {AC_ATTR("name"): "align"}, self.options.layout.get_image_alignment()),
        )
        return macro

    def _transform_block_math(self, elem: ElementType) -> ElementType:
        """
        Creates a block-level LaTeX formula using the Confluence extension "LaTeX Math for Confluence - Math Formula & Equations".

        :see: https://help.narva.net/latex-math-for-confluence/
        """

        content = elem.text
        if not content:
            raise DocumentError(elem, "empty block-level LaTeX formula")

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
            AC_ELEM("parameter", {AC_ATTR("name"): "align"}, self.options.layout.get_image_alignment()),
        )

    def _transform_footnote_ref(self, elem: ElementType) -> None:
        """
        Transforms a footnote reference.

        When a footnote is referenced multiple times, Python-Markdown generates
        different `id` attributes for each reference:
        - First reference: `fnref:NAME`
        - Second reference: `fnref2:NAME`
        - Third reference: `fnref3:NAME`
        - etc.

        ```
        <sup id="fnref:NAME"><a class="footnote-ref" href="#fn:NAME">REF</a></sup>
        <sup id="fnref2:NAME"><a class="footnote-ref" href="#fn:NAME">REF</a></sup>
        ```
        """

        if elem.tag != "sup":
            raise DocumentError(elem, "expected: `<sup>` as the HTML element for a footnote reference")

        ref_id = elem.attrib.pop("id", "")
        # Match fnref:NAME, fnref2:NAME, fnref3:NAME, etc.
        match = _FOOTNOTE_REF_REGEXP.match(ref_id)
        if match is None:
            raise DocumentError(elem, "expected: attribute `id` of format `fnref:NAME` or `fnrefN:NAME` applied on `<sup>` for a footnote reference")
        numeric_suffix = match.group(1)
        footnote_name = match.group(2)
        # Build anchor name: first reference uses NAME, subsequent references use NAME-N
        footnote_ref = f"{footnote_name}-{numeric_suffix}" if numeric_suffix else footnote_name

        link = next((elem.iterchildren(tag="a")), None)
        if link is None:
            raise DocumentError(elem, "expected: `<a>` as the first HTML element in a footnote reference")
        def_href = link.attrib.pop("href", "")
        if not def_href.startswith("#fn:"):
            raise DocumentError(elem, "expected: attribute `href` of format `#fn:NAME` applied on `<a>` for a footnote reference")
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

        When a footnote is referenced multiple times, Python-Markdown generates
        multiple back-reference links in the footnote definition:
        - First reference: `#fnref:NAME`
        - Second reference: `#fnref2:NAME`
        - Third reference: `#fnref3:NAME`
        - etc.

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

        With multiple references to the same footnote:
        ```
        <li id="fn:NAME">
            <p>TEXT <a class="footnote-backref" href="#fnref:NAME">↩</a><a class="footnote-backref" href="#fnref2:NAME">↩</a></p>
        </li>
        ```
        """

        ordered_list = next((elem.iterchildren(tag="ol")), None)
        if ordered_list is None:
            raise DocumentError(elem, "expected: `<ol>` as direct child of footnote definition block")

        for list_item in ordered_list:
            if list_item.tag != "li":
                raise DocumentError(elem, "expected: `<li>` as children of `<ol>` in footnote definition block")

            def_id = list_item.attrib.pop("id", "")
            if not def_id.startswith("fn:"):
                raise DocumentError(elem, "expected: attribute `id` of format `fn:NAME` applied on `<li>` for a footnote definition")
            footnote_def = def_id.removeprefix("fn:")

            # find the last paragraph, which is where the backref links are placed
            paragraphs = list(list_item.iterchildren(tag="p"))
            if not paragraphs:
                raise DocumentError(elem, "expected: `<p>` as a child of `<li>` in a footnote definition")
            last_paragraph = paragraphs[-1]

            # collect all backref anchors (there may be multiple when a footnote is referenced multiple times)
            # pattern matches #fnref:NAME, #fnref2:NAME, #fnref3:NAME, etc.
            # store tuples of (anchor_element, number, footnote_name)
            backref_info: list[tuple[ElementType, int | None, str]] = []
            for anchor in list(last_paragraph.iterchildren(tag="a")):
                href = anchor.get("href", "")
                if href.startswith("#") and (match := _FOOTNOTE_REF_REGEXP.match(href[1:])) is not None:
                    backref_info.append((anchor, int(match.group(1), base=10) if match.group(1) else None, match.group(2)))

            if not backref_info:
                raise DocumentError(
                    elem, "expected: at least one `<a>` element with `href` attribute of format `#fnref:NAME` or `#fnrefN:NAME` in a footnote definition"
                )

            # remove all back-links generated by Python-Markdown
            for anchor, _, _ in backref_info:
                last_paragraph.remove(anchor)

            # use the first paragraph for the anchor placement
            first_paragraph = paragraphs[0]

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

            # build back-links to each footnote reference in page body:
            # * for single reference: ↩
            # * for multiple references: ↩¹ ↩² ↩³ ...
            for _, number, footnote_name in backref_info:
                # build anchor name matching the reference anchor:
                # * first reference: footnote-ref-NAME
                # * subsequent references: footnote-ref-NAME-N
                if number is None:
                    anchor_name = f"footnote-ref-{footnote_name}"
                    if len(backref_info) > 1:
                        link_text = "↩¹"
                    else:
                        link_text = "↩"
                else:
                    anchor_name = f"footnote-ref-{footnote_name}-{number}"

                    # use superscript numbers for references
                    superscript_digits = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
                    link_text = f"↩{str(number).translate(superscript_digits)}"

                ref_link = AC_ELEM(
                    "link",
                    {
                        AC_ATTR("anchor"): anchor_name,
                    },
                    AC_ELEM("link-body", ET.CDATA(link_text)),
                )

                last_paragraph.append(ref_link)

            # append anchor to first paragraph
            first_paragraph.insert(0, def_anchor)
            def_anchor.tail = first_paragraph.text
            first_paragraph.text = None

    def _transform_tasklist(self, elem: ElementType) -> ElementType:
        """
        Transforms a list of tasks into an action widget.

        :see: https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/about-tasklists
        """

        if elem.tag != "ul":
            raise DocumentError(elem, "expected: `<ul>` as the HTML element for a tasklist")

        for item in elem:
            if item.tag != "li":
                raise DocumentError(elem, "expected: `<li>` as the HTML element for a task")
            if not _TASKLIST_REGEXP.match(item.text or ""):
                raise DocumentError(elem, "expected: each `<li>` in a task list starting with [ ] or [x]")

        tasks: list[ElementType] = []
        for index, item in enumerate(elem, start=1):
            if item.text is None:
                raise NotImplementedError("pre-condition check for tasklist not exhaustive")
            match = _TASKLIST_REGEXP.match(item.text)
            if match is None:
                raise NotImplementedError("pre-condition check for tasklist not exhaustive")

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
    def transform(self, child: ElementType) -> ElementType | ElementAction:
        """
        Transforms an HTML element tree obtained from a Markdown document into a Confluence Storage Format element tree.
        """

        # replace line breaks with regular space in element text to minimize phantom changes
        if child.text:
            child.text = child.text.replace("\n", " ")
        if child.tail:
            child.tail = child.tail.replace("\n", " ")

        if not isinstance(child.tag, str):
            return ElementAction.RECURSE

        match child.tag:
            # <line-number value="#" />
            case "line-number":
                return ElementAction.REMOVE

            # <p>...</p>
            case "p":
                child_elem_count = child_count(child)

                # <p><img src="..." /></p>
                if child_elem_count == 1 and not child.text and child[0].tag == "img" and not child[0].tail:
                    return self._transform_image(FormattingContext.BLOCK, child[0])

                # <p><a href="..."> ... </a></p>
                elif child_elem_count == 1 and child[0].tag == "a" and not child[0].tail:
                    link = self._transform_card(child)
                    if link is not None:
                        return link
                    else:
                        return ElementAction.RECURSE

                # <p>[[<em>TOC</em>]]</p> (represented in Markdown as `[[_TOC_]]`)
                elif is_placeholder_for(child, "TOC"):
                    return self._transform_toc(child)

                # <p>[[<em>LISTING</em>]]</p> (represented in Markdown as `[[_LISTING_]]`)
                elif is_placeholder_for(child, "LISTING"):
                    return self._transform_listing(child)

            # <div>...</div>
            case "div":
                classes = child.get("class", "").split(" ")

                # <div class="arithmatex">...</div>
                if "arithmatex" in classes:
                    return self._transform_block_math(child)

                # <div><ac:structured-macro ...>...</ac:structured-macro></div>
                elif "csf" in classes:
                    if len(child) != 1:
                        raise DocumentError(child, "expected: single child in Confluence Storage Format block")

                    return child[0]

                # <div class="footnote">
                #   <hr/>
                #   <ol>
                #     <li id="fn:NAME"><p>TEXT <a class="footnote-backref" href="#fnref:NAME">↩</a></p></li>
                #   </ol>
                # </div>
                elif "footnote" in classes:
                    self._transform_footnote_def(child)
                    return ElementAction.RECURSE

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
            case "blockquote":
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
            case "details" if len(child) > 1 and child[0].tag == "summary":
                return self._transform_collapsed(child)

            # <ol>...</ol>
            case "ol":
                # Confluence adds the attribute `start` for every ordered list
                child.set("start", "1")
                return ElementAction.RECURSE

            # <ul>
            #   <li>[ ] ...</li>
            #   <li>[x] ...</li>
            # </ul>
            case "ul":
                if len(child) > 0 and all(element_text_starts_with_any(item, ["[ ]", "[x]", "[X]"]) for item in child):
                    return self._transform_tasklist(child)

                return ElementAction.RECURSE

            case "li":
                normalize_inline(child)
                return ElementAction.RECURSE

            # <pre><code class="language-java"> ... </code></pre>
            case "pre" if len(child) == 1 and child[0].tag == "code":
                return self._transform_code_block(child[0])

            # <table>...</table>
            case "table":
                # remove <thead> if it doesn't contain any text
                for thead in list(child.iterchildren("thead")):
                    for th in thead.iterdescendants("td", "th"):
                        if any(text and not text.isspace() for text in th.itertext()):
                            break
                    else:
                        child.remove(thead)

                # ensure inline content is wrapped in <p>
                for td in child.iterdescendants("td", "th"):
                    normalize_inline(td)

                match self.options.layout.alignment:
                    case "left":
                        layout = "align-start"
                    case _:
                        layout = "default"
                child.set("data-layout", layout)
                if self.options.layout.table.display_mode == "fixed":
                    child.set("data-table-display-mode", "fixed")
                if self.options.layout.table.width:
                    child.set("data-table-width", str(self.options.layout.table.width))

                return ElementAction.RECURSE

            # <img src="..." alt="..." />
            case "img":
                return self._transform_image(FormattingContext.INLINE, child)

            # <a href="..."> ... </a>
            case "a":
                link = self._transform_link(child)
                if link is not None:
                    return link
                else:
                    return ElementAction.RECURSE

            # <mark>...</mark>
            case "mark":
                return self._transform_mark(child)

            # <span>...</span>
            case "span":
                classes = child.get("class", "").split(" ")

                # <span class="arithmatex">...</span>
                if "arithmatex" in classes:
                    return self._transform_inline_math(child)

            # <sup id="fnref:NAME"><a class="footnote-ref" href="#fn:NAME">1</a></sup>
            # Multiple references: <sup id="fnref2:NAME">...</sup>, <sup id="fnref3:NAME">...</sup>
            case "sup" if _FOOTNOTE_REF_REGEXP.match(child.get("id", "")):
                self._transform_footnote_ref(child)
                return ElementAction.RECURSE

            # <input type="date" value="1984-01-01" />
            case "input" if child.get("type", "") == "date":
                return HTML("time", {"datetime": child.get("value", "")})

            # <ins>...</ins>
            case "ins":
                # Confluence prefers <u> over <ins> for underline, and replaces <ins> with <u>
                child.tag = "u"

            # <confluence-skip>...</confluence-skip>
            case "confluence-skip":
                # Content marked for exclusion from Confluence
                return ElementAction.REMOVE

            # <x-emoji data-shortname="wink" data-unicode="1f609">😉</x-emoji>
            case "x-emoji":
                return self._transform_emoji(child)

            # <h1>...</h1>
            # <h2>...</h2> ...
            case "h1" | "h2" | "h3" | "h4" | "h5" | "h6":
                level = int(child.tag[1:])
                title = element_to_text(child)
                self.toc.add(level, title)

                if self.options.heading_anchors:
                    self._transform_heading(child)
                    return ElementAction.RECURSE
            case _:
                pass

        return ElementAction.RECURSE


class ConfluenceDocument:
    "Encapsulates an element tree for a Confluence document created by parsing a Markdown document."

    title: str | None
    labels: list[str] | None
    properties: dict[str, JsonType] | None

    links: list[str]
    images: list[ImageData]
    embedded_files: dict[str, EmbeddedFileData]

    options: ProcessorOptions
    root: ElementType

    @classmethod
    def create(
        cls,
        path: Path,
        options: ProcessorOptions,
        root_dir: Path,
        site_metadata: ConfluenceSiteMetadata,
        page_metadata: ConfluencePageCollection,
    ) -> tuple[ConfluencePageID, "ConfluenceDocument"]:
        path = path.resolve(True)

        document = Scanner().read(path)
        props = document.properties

        if props.page_id is not None:
            page_id = ConfluencePageID(props.page_id)
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
        options: ProcessorOptions,
        root_dir: Path,
        site_metadata: ConfluenceSiteMetadata,
        page_metadata: ConfluencePageCollection,
    ) -> None:
        "Converts a single Markdown document to Confluence Storage Format."

        props = document.properties
        self.options = options

        # register auxiliary URL substitutions
        lines: list[str] = []
        for data_uri, color in status_images.items():
            lines.append(f"[STATUS-{color.upper()}]: {data_uri}")

        if options.line_numbers:
            lines.extend(markdown_with_line_numbers(document.text.splitlines(), document.start_line_number))
        else:
            lines.append(document.text)

        # parse Markdown document and convert to HTML
        html = markdown_to_html("\n".join(lines))

        try:
            # Transform skip markers in HTML string before parsing
            html = transform_skip_comments_in_html(html)
        except PreprocessingError as ex:
            raise ConversionError(f"failed to convert Markdown file: {path}") from ex

        # modify HTML as necessary
        if self.options.generated_by is not None:
            generated_by = props.generated_by or self.options.generated_by
        else:
            generated_by = None

        if generated_by is not None:
            generated_by = apply_generated_by_template(generated_by, path.relative_to(root_dir))
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
            raise ConversionError(f"failed to convert Markdown file: {path}") from ex

        # configure HTML-to-Confluence converter
        converter_options = copy.deepcopy(self.options.converter)
        if props.layout is not None:
            converter_options.layout = coalesce(props.layout, converter_options.layout)
        converter = ConfluenceStorageFormatConverter(converter_options, path, root_dir, site_metadata, page_metadata)

        # execute HTML-to-Confluence converter
        try:
            converter.visit(self.root)
        except DocumentError as ex:
            if options.line_numbers:
                # find closest paragraph ancestor
                elem = ex.element
                while elem.tag != "p" and (parent := elem.getparent()):
                    elem = parent

                # locate line number marker element
                line_number = 0
                for placeholder in elem.iterchildren("line-number"):
                    line_number = int(placeholder.attrib["value"])

                raise ConversionError(f"failed to convert Markdown file: {path} @ line {line_number}") from ex
            else:
                raise ConversionError(f"failed to convert Markdown file: {path}") from ex
        except RuntimeError as ex:
            raise ConversionError(f"failed to convert Markdown file: {path}") from ex

        # extract information discovered by converter
        self.links = converter.links
        self.images = converter.attachments.images
        self.embedded_files = converter.attachments.embedded_files

        # assign global properties for document
        self.title = props.title or converter.toc.get_title()
        self.labels = props.tags
        self.properties = props.properties

        # Remove the first heading if:
        # 1. The option is enabled
        # 2. Title was NOT from front-matter (document.title is None)
        # 3. A title was successfully extracted from heading (self.title is not None)
        if converter_options.skip_title_heading and props.title is None and self.title is not None:
            self._remove_first_heading()

    def _remove_first_heading(self) -> None:
        """
        Removes the first heading element from the document root.

        This is used when the title was extracted from the first unique top-level heading
        and the user has requested to skip it from the body to avoid duplication.

        Handles the case where a generated-by info panel may be present as the first child.
        """

        # find the first heading element (h1-h6) in the root
        heading_pattern = re.compile(r"^h[1-6]$", re.IGNORECASE)

        for child in self.root:
            if not isinstance(child.tag, str):
                continue

            if heading_pattern.match(child.tag) is None:
                continue

            remove_element(child)

            # only remove the FIRST heading, then stop
            break

    def xhtml(self) -> str:
        return elements_to_string(self.root)
