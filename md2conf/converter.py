"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

# mypy: disable-error-code="dict-item"

import hashlib
import importlib.resources as resources
import logging
import os.path
import re
import uuid
import xml.etree.ElementTree
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional, Union
from urllib.parse import ParseResult, quote_plus, urlparse, urlunparse

import lxml.etree as ET
import markdown
from lxml.builder import ElementMaker
from strong_typing.core import JsonType

from md2conf.drawio import extract_diagram

from .collection import ConfluencePageCollection
from .extra import path_relative_to
from .mermaid import render_diagram
from .metadata import ConfluenceSiteMetadata
from .properties import PageError
from .scanner import ScannedDocument, Scanner

namespaces = {
    "ac": "http://atlassian.com/content",
    "ri": "http://atlassian.com/resource/identifier",
}
for key, value in namespaces.items():
    ET.register_namespace(key, value)


def get_volatile_attributes() -> list[ET.QName]:
    "Returns a list of volatile attributes that frequently change as a Confluence storage format XHTML document is updated."

    return [
        ET.QName(namespaces["ac"], "local-id"),
        ET.QName(namespaces["ac"], "macro-id"),
        ET.QName(namespaces["ri"], "version-at-save"),
    ]


HTML = ElementMaker()
AC = ElementMaker(namespace=namespaces["ac"])
RI = ElementMaker(namespace=namespaces["ri"])

LOGGER = logging.getLogger(__name__)


class ParseError(RuntimeError):
    pass


def starts_with_any(text: str, prefixes: list[str]) -> bool:
    "True if text starts with any of the listed prefixes."

    for prefix in prefixes:
        if text.startswith(prefix):
            return True
    return False


def is_absolute_url(url: str) -> bool:
    urlparts = urlparse(url)
    return bool(urlparts.scheme) or bool(urlparts.netloc)


def is_relative_url(url: str) -> bool:
    urlparts = urlparse(url)
    return not bool(urlparts.scheme) and not bool(urlparts.netloc)


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


def emoji_generator(
    index: str,
    shortname: str,
    alias: Optional[str],
    uc: Optional[str],
    alt: str,
    title: Optional[str],
    category: Optional[str],
    options: dict[str, Any],
    md: markdown.Markdown,
) -> xml.etree.ElementTree.Element:
    """
    Custom generator for `pymdownx.emoji`.
    """

    name = (alias or shortname).strip(":")
    span = xml.etree.ElementTree.Element("span", {"data-emoji-shortname": name})
    if uc is not None:
        span.attrib["data-emoji-unicode"] = uc

        # convert series of Unicode code point hexadecimal values into characters
        span.text = "".join(chr(int(item, base=16)) for item in uc.split("-"))
    else:
        span.text = alt
    return span


def math_formatter(
    source: str,
    language: str,
    css_class: str,
    options: dict[str, Any],
    md: markdown.Markdown,
    classes: Optional[list[str]] = None,
    id_value: str = "",
    attrs: Optional[dict[str, str]] = None,
    **kwargs: Any,
) -> str:
    """
    Custom formatter for language `math` in `pymdownx.superfences`.
    """

    if classes is None:
        classes = [css_class]
    else:
        classes.insert(0, css_class)

    html_id = f' id="{id_value}"' if id_value else ""
    html_class = ' class="{}"'.format(" ".join(classes))
    html_attrs = " " + " ".join(f'{k}="{v}"' for k, v in attrs.items()) if attrs else ""

    return f"<div{html_id}{html_class}{html_attrs}>{source}</div>"


def markdown_to_html(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=[
            "admonition",
            "footnotes",
            "markdown.extensions.tables",
            "md_in_html",
            "pymdownx.arithmatex",
            "pymdownx.emoji",
            "pymdownx.highlight",  # required by `pymdownx.superfences`
            "pymdownx.magiclink",
            "pymdownx.superfences",
            "pymdownx.tilde",
            "sane_lists",
        ],
        extension_configs={
            "footnotes": {"BACKLINK_TITLE": ""},
            "pymdownx.arithmatex": {"generic": True, "preview": False, "tex_inline_wrap": ["", ""], "tex_block_wrap": ["", ""]},
            "pymdownx.emoji": {
                "emoji_generator": emoji_generator,
            },
            "pymdownx.highlight": {
                "use_pygments": False,
            },
            "pymdownx.superfences": {"custom_fences": [{"name": "math", "class": "arithmatex", "format": math_formatter}]},
        },
    )


def _elements_from_strings(dtd_path: Path, items: list[str]) -> ET._Element:
    """
    Creates a fragment of several XML nodes from their string representation wrapped in a root element.

    :param dtd_path: Path to a DTD document that defines entities like &cent; or &copy;.
    :param items: Strings to parse into XML fragments.
    :returns: An XML document as an element tree.
    """

    parser = ET.XMLParser(
        remove_blank_text=True,
        remove_comments=True,
        strip_cdata=False,
        load_dtd=True,
    )

    ns_attr_list = "".join(f' xmlns:{key}="{value}"' for key, value in namespaces.items())

    data = [
        '<?xml version="1.0"?>',
        f'<!DOCTYPE ac:confluence PUBLIC "-//Atlassian//Confluence 4 Page//EN" "{dtd_path.as_posix()}"><root{ns_attr_list}>',
    ]
    data.extend(items)
    data.append("</root>")

    try:
        return ET.fromstringlist(data, parser=parser)
    except ET.XMLSyntaxError as ex:
        raise ParseError() from ex


def elements_from_strings(items: list[str]) -> ET._Element:
    "Creates a fragment of several XML nodes from their string representation wrapped in a root element."

    resource_path = resources.files(__package__).joinpath("entities.dtd")
    with resources.as_file(resource_path) as dtd_path:
        return _elements_from_strings(dtd_path, items)


def elements_from_string(content: str) -> ET._Element:
    return elements_from_strings([content])


_languages = [
    "abap",
    "actionscript3",
    "ada",
    "applescript",
    "arduino",
    "autoit",
    "bash",
    "c",
    "clojure",
    "coffeescript",
    "coldfusion",
    "cpp",
    "csharp",
    "css",
    "cuda",
    "d",
    "dart",
    "delphi",
    "diff",
    "elixir",
    "erlang",
    "fortran",
    "foxpro",
    "go",
    "graphql",
    "groovy",
    "haskell",
    "haxe",
    "html",
    "java",
    "javafx",
    "javascript",
    "json",
    "jsx",
    "julia",
    "kotlin",
    "livescript",
    "lua",
    "mermaid",
    "mathematica",
    "matlab",
    "objectivec",
    "objectivej",
    "ocaml",
    "octave",
    "pascal",
    "perl",
    "php",
    "powershell",
    "prolog",
    "puppet",
    "python",
    "qml",
    "r",
    "racket",
    "rst",
    "ruby",
    "rust",
    "sass",
    "scala",
    "scheme",
    "shell",
    "smalltalk",
    "splunk",
    "sql",
    "standardml",
    "swift",
    "tcl",
    "tex",
    "tsx",
    "typescript",
    "vala",
    "vb",
    "verilog",
    "vhdl",
    "xml",
    "xquery",
    "yaml",
]


class NodeVisitor:
    def visit(self, node: ET._Element) -> None:
        "Recursively visits all descendants of this node."

        if len(node) < 1:
            return

        for index in range(len(node)):
            source = node[index]
            target = self.transform(source)
            if target is not None:
                node[index] = target
            else:
                self.visit(source)

    def transform(self, child: ET._Element) -> Optional[ET._Element]:
        pass


def title_to_identifier(title: str) -> str:
    "Converts a section heading title to a GitHub-style Markdown same-page anchor."

    s = title.strip().lower()
    s = re.sub("[^ A-Za-z0-9]", "", s)
    s = s.replace(" ", "-")
    return s


def element_to_text(node: ET._Element) -> str:
    "Returns all text contained in an element as a concatenated string."

    return "".join(node.itertext()).strip()


@dataclass
class ImageAttributes:
    caption: Optional[str]
    width: Optional[str]
    height: Optional[str]


@dataclass
class TableOfContentsEntry:
    level: int
    text: str


class TableOfContents:
    "Builds a table of contents from Markdown headings."

    headings: list[TableOfContentsEntry]

    def __init__(self) -> None:
        self.headings = []

    def add(self, level: int, text: str) -> None:
        """
        Adds a heading to the table of contents.

        :param level: Markdown heading level (e.g. `1` for first-level heading).
        :param text: Markdown heading text.
        """

        self.headings.append(TableOfContentsEntry(level, text))

    def get_title(self) -> Optional[str]:
        """
        Returns a proposed document title (if unique).

        :returns: Title text, or `None` if no unique title can be inferred.
        """

        for level in range(1, 7):
            try:
                (title,) = (item.text for item in self.headings if item.level == level)
                return title
            except ValueError:
                pass

        return None


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
    :param diagram_output_format: Target image format for diagrams.
    :param webui_links: When true, convert relative URLs to Confluence Web UI links.
    """

    ignore_invalid_url: bool = False
    heading_anchors: bool = False
    prefer_raster: bool = True
    render_drawio: bool = False
    render_mermaid: bool = False
    diagram_output_format: Literal["png", "svg"] = "png"
    webui_links: bool = False


class ConfluenceStorageFormatConverter(NodeVisitor):
    "Transforms a plain HTML tree into Confluence Storage Format."

    options: ConfluenceConverterOptions
    path: Path
    base_dir: Path
    root_dir: Path
    toc: TableOfContents
    links: list[str]
    images: list[Path]
    embedded_images: dict[str, bytes]
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
        self.toc = TableOfContents()
        self.links = []
        self.images = []
        self.embedded_images = {}
        self.site_metadata = site_metadata
        self.page_metadata = page_metadata

    def _transform_heading(self, heading: ET._Element) -> None:
        "Adds anchors to headings in the same document (if *heading anchors* is enabled)."

        for e in heading:
            self.visit(e)

        anchor = AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "anchor",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): ""},
                title_to_identifier(element_to_text(heading)),
            ),
        )

        # insert anchor as first child, pushing any text nodes
        heading.insert(0, anchor)
        anchor.tail = heading.text
        heading.text = None

    def _warn_or_raise(self, msg: str) -> None:
        "Emit a warning or raise an exception when a path points to a resource that doesn't exist."

        if self.options.ignore_invalid_url:
            LOGGER.warning(msg)
        else:
            raise DocumentError(msg)

    def _transform_link(self, anchor: ET._Element) -> Optional[ET._Element]:
        """
        Transforms links (HTML anchor `<a>`).

        * Absolute URLs are left intact.
        * Links to headings in the same document are transformed into `<ac:link>` (if *heading anchors* is enabled).
        * Links to documents in the source hierarchy are mapped into full Confluence URLs.
        """

        url = anchor.attrib.get("href")
        if url is None or is_absolute_url(url):
            return None

        LOGGER.debug("Found link %s relative to %s", url, self.path)
        relative_url: ParseResult = urlparse(url)

        if not relative_url.scheme and not relative_url.netloc and not relative_url.path and not relative_url.params and not relative_url.query:
            LOGGER.debug("Found local URL: %s", url)
            if self.options.heading_anchors:
                # <ac:link ac:anchor="anchor"><ac:link-body>...</ac:link-body></ac:link>
                target = relative_url.fragment.lstrip("#")
                link_body = AC("link-body", {}, *list(anchor))
                link_body.text = anchor.text
                link_wrapper = AC(
                    "link",
                    {
                        ET.QName(namespaces["ac"], "anchor"): target,
                    },
                    link_body,
                )
                link_wrapper.tail = anchor.tail
                return link_wrapper
            else:
                return None

        # convert the relative URL to absolute URL based on the base path value, then look up
        # the absolute path in the page metadata dictionary to discover the relative path
        # within Confluence that should be used
        absolute_path = (self.base_dir / relative_url.path).resolve()
        if not is_directory_within(absolute_path, self.root_dir):
            anchor.attrib.pop("href")
            self._warn_or_raise(f"relative URL {url} points to outside root path: {self.root_dir}")
            return None

        link_metadata = self.page_metadata.get(absolute_path)
        if link_metadata is None:
            msg = f"unable to find matching page for URL: {url}"
            if self.options.ignore_invalid_url:
                LOGGER.warning(msg)
                anchor.attrib.pop("href")
                return None
            else:
                raise DocumentError(msg)

        relative_path = os.path.relpath(absolute_path, self.base_dir)
        LOGGER.debug("Found link to page %s with metadata: %s", relative_path, link_metadata)
        self.links.append(url)

        if self.options.webui_links:
            page_url = f"{self.site_metadata.base_path}pages/viewpage.action?pageId={link_metadata.page_id}"
        else:
            space_key = link_metadata.space_key or self.site_metadata.space_key

            if space_key is None:
                raise DocumentError("Confluence space key required for building full web URLs")

            page_url = f"{self.site_metadata.base_path}spaces/{space_key}/pages/{link_metadata.page_id}/{encode_title(link_metadata.title)}"

        components = ParseResult(
            scheme="https",
            netloc=self.site_metadata.domain,
            path=page_url,
            params="",
            query="",
            fragment=relative_url.fragment,
        )
        transformed_url = urlunparse(components)

        LOGGER.debug("Transformed relative URL: %s to URL: %s", url, transformed_url)
        anchor.attrib["href"] = transformed_url
        return None

    def _transform_image(self, image: ET._Element) -> ET._Element:
        "Inserts an attached or external image."

        src = image.attrib.get("src")

        if not src:
            raise DocumentError("image lacks `src` attribute")

        caption = image.attrib.get("alt")
        width = image.attrib.get("width")
        height = image.attrib.get("height")
        attrs = ImageAttributes(caption, width, height)

        if is_absolute_url(src):
            return self._transform_external_image(src, attrs)
        else:
            path = Path(src)

            absolute_path = self._verify_image_path(path)
            if absolute_path is None:
                return self._create_missing(path, caption)

            if absolute_path.name.endswith(".drawio.png") or absolute_path.name.endswith(".drawio.svg"):
                return self._transform_drawio_image(absolute_path, attrs)
            elif absolute_path.name.endswith(".drawio.xml") or absolute_path.name.endswith(".drawio"):
                self.images.append(absolute_path)
                image_filename = attachment_name(path_relative_to(absolute_path, self.base_dir))
                return self._create_drawio(image_filename, attrs)
            else:
                return self._transform_attached_image(absolute_path, attrs)

    def _transform_external_image(self, url: str, attrs: ImageAttributes) -> ET._Element:
        "Emits Confluence Storage Format XHTML for an external image."

        attributes: dict[str, Any] = {
            ET.QName(namespaces["ac"], "align"): "center",
            ET.QName(namespaces["ac"], "layout"): "center",
        }
        if attrs.width is not None:
            attributes.update({ET.QName(namespaces["ac"], "width"): attrs.width})
        if attrs.height is not None:
            attributes.update({ET.QName(namespaces["ac"], "height"): attrs.height})

        elements: list[ET._Element] = []
        elements.append(
            RI(
                "url",
                # refers to an external image
                {ET.QName(namespaces["ri"], "value"): url},
            )
        )
        if attrs.caption is not None:
            elements.append(AC("caption", HTML.p(attrs.caption)))

        return AC("image", attributes, *elements)

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

    def _transform_attached_image(self, absolute_path: Path, attrs: ImageAttributes) -> ET._Element:
        "Emits Confluence Storage Format XHTML for an attached raster or vector image."

        if self.options.prefer_raster and absolute_path.name.endswith(".svg"):
            # prefer PNG over SVG; Confluence displays SVG in wrong size, and text labels are truncated
            png_file = absolute_path.with_suffix(".png")
            if png_file.exists():
                absolute_path = png_file

        self.images.append(absolute_path)
        return self._create_image(absolute_path, attrs)

    def _transform_drawio_image(self, absolute_path: Path, attrs: ImageAttributes) -> ET._Element:
        "Emits Confluence Storage Format XHTML for a draw.io image."

        if not absolute_path.name.endswith(".drawio.png") and not absolute_path.name.endswith(".drawio.svg"):
            raise DocumentError("invalid image format; expected: `*.drawio.png` or `*.drawio.svg`")

        if self.options.render_drawio:
            return self._transform_attached_image(absolute_path, attrs)
        else:
            # extract embedded editable diagram and upload as *.drawio
            image_data = extract_diagram(absolute_path)
            image_filename = attachment_name(path_relative_to(absolute_path.with_suffix(".xml"), self.base_dir))
            self.embedded_images[image_filename] = image_data

            return self._create_drawio(image_filename, attrs)

    def _create_image(self, absolute_path: Path, attrs: ImageAttributes) -> ET._Element:
        "An image embedded into the page, linking to an attachment."

        image_name = attachment_name(path_relative_to(absolute_path, self.base_dir))

        attributes: dict[str, Any] = {
            ET.QName(namespaces["ac"], "align"): "center",
            ET.QName(namespaces["ac"], "layout"): "center",
        }
        if attrs.width is not None:
            attributes.update({ET.QName(namespaces["ac"], "width"): attrs.width})
        if attrs.height is not None:
            attributes.update({ET.QName(namespaces["ac"], "height"): attrs.height})

        elements: list[ET._Element] = []
        elements.append(
            RI(
                "attachment",
                # refers to an attachment uploaded alongside the page
                {ET.QName(namespaces["ri"], "filename"): image_name},
            )
        )
        if attrs.caption is not None:
            elements.append(AC("caption", HTML.p(attrs.caption)))

        return AC("image", attributes, *elements)

    def _create_drawio(self, filename: str, attrs: ImageAttributes) -> ET._Element:
        "A draw.io diagram embedded into the page, linking to an attachment."

        parameters: list[ET._Element] = [
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): "diagramName"},
                filename,
            ),
        ]
        if attrs.width is not None:
            parameters.append(
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): "width"},
                    attrs.width,
                ),
            )
        if attrs.height is not None:
            parameters.append(
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): "height"},
                    attrs.height,
                ),
            )

        local_id = str(uuid.uuid4())
        macro_id = str(uuid.uuid4())
        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "drawio",
                ET.QName(namespaces["ac"], "schema-version"): "1",
                "data-layout": "default",
                ET.QName(namespaces["ac"], "local-id"): local_id,
                ET.QName(namespaces["ac"], "macro-id"): macro_id,
            },
            *parameters,
        )

    def _create_missing(self, path: Path, caption: Optional[str]) -> ET._Element:
        "A warning panel for a missing image."

        message = HTML.p("Missing image: ", HTML.code(path.as_posix()))
        if caption is not None:
            content = [
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): "title"},
                    caption,
                ),
                AC("rich-text-body", {}, message),
            ]
        else:
            content = [AC("rich-text-body", {}, message)]

        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "warning",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            *content,
        )

    def _transform_code_block(self, code: ET._Element) -> ET._Element:
        "Transforms a code block."

        language = code.attrib.get("class")
        if language:
            m = re.match("^language-(.*)$", language)
            if m:
                language = m.group(1)
            else:
                language = "none"
        if language not in _languages:
            language = "none"
        content: str = code.text or ""
        content = content.rstrip()

        if language == "mermaid":
            return self._transform_mermaid(content)

        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "code",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): "theme"},
                "Default",
            ),
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): "language"},
                language,
            ),
            AC("plain-text-body", ET.CDATA(content)),
        )

    def _transform_mermaid(self, content: str) -> ET._Element:
        "Transforms a Mermaid diagram code block."

        if self.options.render_mermaid:
            image_data = render_diagram(content, self.options.diagram_output_format)
            image_hash = hashlib.md5(image_data).hexdigest()
            image_filename = attachment_name(f"embedded_{image_hash}.{self.options.diagram_output_format}")
            self.embedded_images[image_filename] = image_data
            return AC(
                "image",
                {
                    ET.QName(namespaces["ac"], "align"): "center",
                    ET.QName(namespaces["ac"], "layout"): "center",
                },
                RI(
                    "attachment",
                    {ET.QName(namespaces["ri"], "filename"): image_filename},
                ),
            )
        else:
            local_id = str(uuid.uuid4())
            macro_id = str(uuid.uuid4())
            return AC(
                "structured-macro",
                {
                    ET.QName(namespaces["ac"], "name"): "macro-diagram",
                    ET.QName(namespaces["ac"], "schema-version"): "1",
                    "data-layout": "default",
                    ET.QName(namespaces["ac"], "local-id"): local_id,
                    ET.QName(namespaces["ac"], "macro-id"): macro_id,
                },
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): "sourceType"},
                    "MacroBody",
                ),
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): "attachmentPageId"},
                ),
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): "syntax"},
                    "Mermaid",
                ),
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): "attachmentId"},
                ),
                AC("parameter", {ET.QName(namespaces["ac"], "name"): "url"}),
                AC("plain-text-body", ET.CDATA(content)),
            )

    def _transform_toc(self, code: ET._Element) -> ET._Element:
        "Creates a table of contents, constructed from headings in the document."

        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "toc",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "outline"}, "clear"),
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "style"}, "default"),
        )

    def _transform_listing(self, code: ET._Element) -> ET._Element:
        "Creates a list of child pages."

        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "children",
                ET.QName(namespaces["ac"], "schema-version"): "2",
                "data-layout": "default",
            },
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "allChildren"}, "true"),
        )

    def _transform_admonition(self, elem: ET._Element) -> ET._Element:
        """
        Creates an info, tip, note or warning panel from a Markdown admonition.

        Transforms [Python-Markdown admonition](https://python-markdown.github.io/extensions/admonition/)
        syntax into one of the Confluence structured macros *info*, *tip*, *note*, or *warning*.
        """

        # <div class="admonition note">
        class_list = elem.attrib.get("class", "").split(" ")
        class_name: Optional[str] = None
        if "info" in class_list:
            class_name = "info"
        elif "tip" in class_list:
            class_name = "tip"
        elif "note" in class_list:
            class_name = "note"
        elif "warning" in class_list:
            class_name = "warning"

        if class_name is None:
            raise DocumentError(f"unsupported admonition label: {class_list}")

        for e in elem:
            self.visit(e)

        # <p class="admonition-title">Note</p>
        if "admonition-title" in elem[0].attrib.get("class", "").split(" "):
            content = [
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): "title"},
                    elem[0].text or "",
                ),
                AC("rich-text-body", {}, *list(elem[1:])),
            ]
        else:
            content = [AC("rich-text-body", {}, *list(elem))]

        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): class_name,
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            *content,
        )

    def _transform_github_alert(self, elem: ET._Element) -> ET._Element:
        """
        Creates a GitHub-style panel, normally triggered with a block-quote starting with a capitalized string such as `[!TIP]`.
        """

        content = elem[0]
        if content.text is None:
            raise DocumentError("empty content")

        class_name: Optional[str] = None
        skip = 0

        pattern = re.compile(r"^\[!([A-Z]+)\]\s*")
        match = pattern.match(content.text)
        if match:
            skip = len(match.group(0))
            alert = match.group(1)
            if alert == "NOTE":
                class_name = "note"
            elif alert == "TIP":
                class_name = "tip"
            elif alert == "IMPORTANT":
                class_name = "tip"
            elif alert == "WARNING":
                class_name = "warning"
            elif alert == "CAUTION":
                class_name = "warning"
            else:
                raise DocumentError(f"unsupported GitHub alert: {alert}")

        return self._transform_alert(elem, class_name, skip)

    def _transform_gitlab_alert(self, elem: ET._Element) -> ET._Element:
        """
        Creates a classic GitLab-style panel.

        Classic panels are defined with a block-quote and text starting with a capitalized string such as `DISCLAIMER:`.
        This syntax does not use Hugo shortcode.
        """

        content = elem[0]
        if content.text is None:
            raise DocumentError("empty content")

        class_name: Optional[str] = None
        skip = 0

        pattern = re.compile(r"^(FLAG|NOTE|WARNING|DISCLAIMER):\s*")
        match = pattern.match(content.text)
        if match:
            skip = len(match.group(0))
            alert = match.group(1)
            if alert == "FLAG":
                class_name = "note"
            elif alert == "NOTE":
                class_name = "note"
            elif alert == "WARNING":
                class_name = "warning"
            elif alert == "DISCLAIMER":
                class_name = "info"
            else:
                raise DocumentError(f"unsupported GitLab alert: {alert}")

        return self._transform_alert(elem, class_name, skip)

    def _transform_alert(self, elem: ET._Element, class_name: Optional[str], skip: int) -> ET._Element:
        """
        Creates an info, tip, note or warning panel from a GitHub or GitLab alert.

        Transforms
        [GitHub alert](https://docs.github.com/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#alerts)
        or [GitLab alert](https://docs.gitlab.com/ee/development/documentation/styleguide/#alert-boxes)
        syntax into one of the Confluence structured macros *info*, *tip*, *note*, or *warning*.
        """

        content = elem[0]
        if content.text is None:
            raise DocumentError("empty content")

        if class_name is None:
            raise DocumentError("not an alert")

        for e in elem:
            self.visit(e)

        content.text = content.text[skip:]
        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): class_name,
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC("rich-text-body", {}, *list(elem)),
        )

    def _transform_section(self, elem: ET._Element) -> ET._Element:
        """
        Creates a collapsed section.

        Transforms
        [GitHub collapsed section](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections)
        syntax into the Confluence structured macro *expand*.
        """

        if elem[0].tag != "summary":
            raise DocumentError("expected: `<summary>` as first direct child of `<details>`")
        if elem[0].tail is not None:
            raise DocumentError('expected: attribute `markdown="1"` on `<details>`')

        summary = "".join(elem[0].itertext()).strip()
        elem.remove(elem[0])

        self.visit(elem)

        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "expand",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): "title"},
                summary,
            ),
            AC("rich-text-body", {}, *list(elem)),
        )

    def _transform_emoji(self, elem: ET._Element) -> ET._Element:
        """
        Inserts an inline emoji character.
        """

        shortname = elem.attrib.get("data-emoji-shortname", "")
        unicode = elem.attrib.get("data-emoji-unicode", None)
        alt = elem.text or ""

        # <ac:emoticon ac:name="wink" ac:emoji-shortname=":wink:" ac:emoji-id="1f609" ac:emoji-fallback="&#128521;"/>
        # <ac:emoticon ac:name="blue-star" ac:emoji-shortname=":heavy_plus_sign:" ac:emoji-id="2795" ac:emoji-fallback="&#10133;"/>
        # <ac:emoticon ac:name="blue-star" ac:emoji-shortname=":heavy_minus_sign:" ac:emoji-id="2796" ac:emoji-fallback="&#10134;"/>
        return AC(
            "emoticon",
            {
                ET.QName(namespaces["ac"], "name"): shortname,
                ET.QName(namespaces["ac"], "emoji-shortname"): f":{shortname}:",
                ET.QName(namespaces["ac"], "emoji-id"): unicode,
                ET.QName(namespaces["ac"], "emoji-fallback"): alt,
            },
        )

    def _transform_inline_math(self, elem: ET._Element) -> ET._Element:
        """
        Creates an inline LaTeX formula using the Confluence extension "LaTeX Math for Confluence - Math Formula & Equations".

        :see: https://help.narva.net/latex-math-for-confluence/
        """

        content = elem.text or ""
        if not content:
            raise DocumentError("empty inline LaTeX formula")

        LOGGER.debug("Found inline LaTeX formula: %s", content)

        local_id = str(uuid.uuid4())
        macro_id = str(uuid.uuid4())
        macro = AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "eazy-math-inline",
                ET.QName(namespaces["ac"], "schema-version"): "1",
                ET.QName(namespaces["ac"], "local-id"): local_id,
                ET.QName(namespaces["ac"], "macro-id"): macro_id,
            },
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): "body"},
                content,
            ),
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "align"}, "center"),
        )
        macro.tail = elem.tail  # chain sibling text node that immediately follows original element
        return macro

    def _transform_block_math(self, elem: ET._Element) -> ET._Element:
        """
        Creates a block-level LaTeX formula using the Confluence extension "LaTeX Math for Confluence - Math Formula & Equations".

        :see: https://help.narva.net/latex-math-for-confluence/
        """

        content = elem.text or ""
        if not content:
            raise DocumentError("empty block-level LaTeX formula")

        LOGGER.debug("Found block-level LaTeX formula: %s", content)

        local_id = str(uuid.uuid4())
        macro_id = str(uuid.uuid4())

        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "easy-math-block",
                ET.QName(namespaces["ac"], "schema-version"): "1",
                "data-layout": "default",
                ET.QName(namespaces["ac"], "local-id"): local_id,
                ET.QName(namespaces["ac"], "macro-id"): macro_id,
            },
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): "body"},
                content,
            ),
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "align"}, "center"),
        )

    def _transform_footnote_ref(self, elem: ET._Element) -> None:
        """
        Transforms a footnote reference.

        ```
        <sup id="fnref:NAME"><a class="footnote-ref" href="#fn:NAME">1</a></sup>
        ```
        """

        if elem.tag != "sup":
            raise DocumentError("expected: `<sup>` as the HTML element for a footnote reference")

        ref_id = elem.attrib.pop("id", "")
        if not ref_id.startswith("fnref:"):
            raise DocumentError("expected: attribute `id` of format `fnref:NAME` applied on `<sup>` for a footnote reference")
        footnote_ref = ref_id.removeprefix("fnref:")

        link = elem[0]
        def_href = link.attrib.pop("href", "")
        if not def_href.startswith("#fn:"):
            raise DocumentError("expected: attribute `href` of format `#fn:NAME` applied on `<a>` for a footnote reference")
        footnote_def = def_href.removeprefix("#fn:")

        text = link.text or ""

        # remove link generated by Python-Markdown
        elem.remove(link)

        # build new anchor for footnote reference
        ref_anchor = AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "anchor",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): ""},
                f"footnote-ref-{footnote_ref}",
            ),
        )

        # build new link to footnote definition at the end of page
        def_link = AC(
            "link",
            {
                ET.QName(namespaces["ac"], "anchor"): f"footnote-def-{footnote_def}",
            },
            AC("link-body", ET.CDATA(text)),
        )

        # append children synthesized for Confluence
        elem.append(ref_anchor)
        elem.append(def_link)

    def _transform_footnote_def(self, elem: ET._Element) -> None:
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

        for list_item in elem[1]:
            def_id = list_item.attrib.pop("id", "")
            if not def_id.startswith("fn:"):
                raise DocumentError("expected: attribute `id` of format `fn:NAME` applied on `<li>` for a footnote definition")
            footnote_def = def_id.removeprefix("fn:")

            paragraph = list_item[0]
            ref_anchor = paragraph[-1]
            if ref_anchor.tag != "a":
                raise DocumentError("expected: `<a>` as the last HTML element in a footnote definition")

            ref_href = ref_anchor.attrib.get("href", "")
            if not ref_href.startswith("#fnref:"):
                raise DocumentError("expected: attribute `href` of format `#fnref:NAME` applied on last element `<a>` for a footnote definition")
            footnote_ref = ref_href.removeprefix("#fnref:")

            # remove back-link generated by Python-Markdown
            paragraph.remove(ref_anchor)

            # build new anchor for footnote definition
            def_anchor = AC(
                "structured-macro",
                {
                    ET.QName(namespaces["ac"], "name"): "anchor",
                    ET.QName(namespaces["ac"], "schema-version"): "1",
                },
                AC(
                    "parameter",
                    {ET.QName(namespaces["ac"], "name"): ""},
                    f"footnote-def-{footnote_def}",
                ),
            )

            # build new link to footnote reference in page body
            ref_link = AC(
                "link",
                {
                    ET.QName(namespaces["ac"], "anchor"): f"footnote-ref-{footnote_ref}",
                },
                AC("link-body", ET.CDATA("↩")),
            )

            # append children synthesized for Confluence
            paragraph.insert(0, def_anchor)
            def_anchor.tail = paragraph.text
            paragraph.text = None
            paragraph.append(ref_link)

    def transform(self, child: ET._Element) -> Optional[ET._Element]:
        """
        Transforms an HTML element tree obtained from a Markdown document into a Confluence Storage Format element tree.
        """

        # normalize line breaks to regular space in element text
        if child.text:
            text: str = child.text
            child.text = text.replace("\n", " ")
        if child.tail:
            tail: str = child.tail
            child.tail = tail.replace("\n", " ")

        if not isinstance(child.tag, str):
            return None

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

        # <p><img src="..." /></p>
        if child.tag == "p" and len(child) == 1 and child[0].tag == "img":
            return self._transform_image(child[0])

        # <p>[[_TOC_]]</p>
        # <p>[TOC]</p>
        elif child.tag == "p" and "".join(child.itertext()) in ["[[TOC]]", "[TOC]"]:
            return self._transform_toc(child)

        # <p>[[_LISTING_]]</p>
        elif child.tag == "p" and "".join(child.itertext()) in ["[[LISTING]]", "[LISTING]"]:
            return self._transform_listing(child)

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
        elif child.tag == "div" and "admonition" in child.attrib.get("class", ""):
            return self._transform_admonition(child)

        # Alerts in GitHub
        # <blockquote>
        #   <p>[!TIP] ...</p>
        # </blockquote>
        elif child.tag == "blockquote" and len(child) > 0 and child[0].tag == "p" and child[0].text is not None and child[0].text.startswith("[!"):
            return self._transform_github_alert(child)

        # Alerts in GitLab
        # <blockquote>
        #   <p>DISCLAIMER: ...</p>
        # </blockquote>
        elif (
            child.tag == "blockquote"
            and len(child) > 0
            and child[0].tag == "p"
            and child[0].text is not None
            and starts_with_any(child[0].text, ["FLAG:", "NOTE:", "WARNING:", "DISCLAIMER:"])
        ):
            return self._transform_gitlab_alert(child)

        # <details markdown="1">
        # <summary>...</summary>
        # ...
        # </details>
        elif child.tag == "details" and len(child) > 1 and child[0].tag == "summary":
            return self._transform_section(child)

        # <img src="..." alt="..." />
        elif child.tag == "img":
            return self._transform_image(child)

        # <a href="..."> ... </a>
        elif child.tag == "a":
            return self._transform_link(child)

        # <pre><code class="language-java"> ... </code></pre>
        elif child.tag == "pre" and len(child) == 1 and child[0].tag == "code":
            return self._transform_code_block(child[0])

        # <span data-emoji-shortname="..." data-emoji-unicode="...">...</span>
        elif child.tag == "span" and child.attrib.has_key("data-emoji-shortname"):
            return self._transform_emoji(child)

        # <div class="arithmatex">...</div>
        elif child.tag == "div" and "arithmatex" in child.attrib.get("class", "").split(" "):
            return self._transform_block_math(child)

        # <span class="arithmatex">...</span>
        elif child.tag == "span" and "arithmatex" in child.attrib.get("class", "").split(" "):
            return self._transform_inline_math(child)

        # <sup id="fnref:NAME"><a class="footnote-ref" href="#fn:NAME">1</a></sup>
        elif child.tag == "sup" and child.attrib.get("id", "").startswith("fnref:"):
            self._transform_footnote_ref(child)
            return None

        # <div class="footnote">
        #   <hr/>
        #   <ol>
        #     <li id="fn:NAME"><p>TEXT <a class="footnote-backref" href="#fnref:NAME">↩</a></p></li>
        #   </ol>
        # </div>
        elif child.tag == "div" and "footnote" in child.attrib.get("class", "").split(" "):
            self._transform_footnote_def(child)
            return None

        return None


class DocumentError(RuntimeError):
    "Raised when a converted Markdown document has an unexpected element or attribute."


@dataclass
class ConfluencePageID:
    page_id: str


@dataclass
class ConfluenceQualifiedID:
    page_id: str
    space_key: str


@dataclass
class ConfluenceDocumentOptions:
    """
    Options that control the generated page content.

    :param ignore_invalid_url: When true, ignore invalid URLs in input, emit a warning and replace the anchor with
        plain text; when false, raise an exception.
    :param heading_anchors: When true, emit a structured macro *anchor* for each section heading using GitHub
        conversion rules for the identifier.
    :param generated_by: Text to use as the generated-by prompt (or `None` to omit a prompt).
    :param root_page_id: Confluence page to assume root page role for publishing a directory of Markdown files.
    :param keep_hierarchy: Whether to maintain source directory structure when exporting to Confluence.
    :param prefer_raster: Whether to choose PNG files over SVG files when available.
    :param render_drawio: Whether to pre-render (or use the pre-rendered version of) draw.io diagrams.
    :param render_mermaid: Whether to pre-render Mermaid diagrams into PNG/SVG images.
    :param diagram_output_format: Target image format for diagrams.
    :param webui_links: When true, convert relative URLs to Confluence Web UI links.
    """

    ignore_invalid_url: bool = False
    heading_anchors: bool = False
    generated_by: Optional[str] = "This page has been generated with a tool."
    root_page_id: Optional[ConfluencePageID] = None
    keep_hierarchy: bool = False
    prefer_raster: bool = True
    render_drawio: bool = False
    render_mermaid: bool = False
    diagram_output_format: Literal["png", "svg"] = "png"
    webui_links: bool = False


class ConversionError(RuntimeError):
    "Raised when a Markdown document cannot be converted to Confluence Storage Format."


class ConfluenceDocument:
    title: Optional[str]
    labels: Optional[list[str]]
    properties: Optional[dict[str, JsonType]]
    links: list[str]
    images: list[Path]

    options: ConfluenceDocumentOptions
    root: ET._Element

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
        self.options = options

        # convert to HTML
        html = markdown_to_html(document.text)

        # parse Markdown document
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

        try:
            self.root = elements_from_strings(content)
        except ParseError as ex:
            raise ConversionError(path) from ex

        converter = ConfluenceStorageFormatConverter(
            ConfluenceConverterOptions(
                ignore_invalid_url=self.options.ignore_invalid_url,
                heading_anchors=self.options.heading_anchors,
                prefer_raster=self.options.prefer_raster,
                render_drawio=self.options.render_drawio,
                render_mermaid=self.options.render_mermaid,
                diagram_output_format=self.options.diagram_output_format,
                webui_links=self.options.webui_links,
            ),
            path,
            root_dir,
            site_metadata,
            page_metadata,
        )
        converter.visit(self.root)
        self.links = converter.links
        self.images = converter.images
        self.embedded_images = converter.embedded_images

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


def elements_to_string(root: ET._Element) -> str:
    xml = ET.tostring(root, encoding="utf8", method="xml").decode("utf8")
    m = re.match(r"^<root\s+[^>]*>(.*)</root>\s*$", xml, re.DOTALL)
    if m:
        return m.group(1)
    else:
        raise ValueError("expected: Confluence content")


def _content_to_string(dtd_path: Path, content: str) -> str:
    parser = ET.XMLParser(
        remove_blank_text=True,
        remove_comments=True,
        strip_cdata=False,
        load_dtd=True,
    )

    ns_attr_list = "".join(f' xmlns:{key}="{value}"' for key, value in namespaces.items())

    data = [
        '<?xml version="1.0"?>',
        f'<!DOCTYPE ac:confluence PUBLIC "-//Atlassian//Confluence 4 Page//EN" "{dtd_path.as_posix()}"><root{ns_attr_list}>',
    ]
    data.append(content)
    data.append("</root>")

    tree = ET.fromstringlist(data, parser=parser)
    return ET.tostring(tree, pretty_print=True).decode("utf-8")


def content_to_string(content: str) -> str:
    "Converts a Confluence Storage Format document returned by the API into a readable XML document."

    resource_path = resources.files(__package__).joinpath("entities.dtd")
    with resources.as_file(resource_path) as dtd_path:
        return _content_to_string(dtd_path, content)
