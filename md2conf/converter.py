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
from urllib.parse import ParseResult, urlparse, urlunparse

import lxml.etree as ET
import markdown
import yaml
from lxml.builder import ElementMaker

from .mermaid import render_diagram
from .properties import PageError

namespaces = {
    "ac": "http://atlassian.com/content",
    "ri": "http://atlassian.com/resource/identifier",
}
for key, value in namespaces.items():
    ET.register_namespace(key, value)

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
    name = (alias or shortname).strip(":")
    span = xml.etree.ElementTree.Element("span", {"data-emoji": name})
    if uc is not None:
        # convert series of Unicode code point hexadecimal values into characters
        span.text = "".join(chr(int(item, base=16)) for item in uc.split("-"))
    else:
        span.text = alt
    return span


def markdown_to_html(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=[
            "admonition",
            "markdown.extensions.tables",
            # "markdown.extensions.fenced_code",
            "pymdownx.emoji",
            "pymdownx.highlight",  # required by `pymdownx.superfences`
            "pymdownx.magiclink",
            "pymdownx.superfences",
            "pymdownx.tilde",
            "sane_lists",
            "md_in_html",
        ],
        extension_configs={
            "pymdownx.emoji": {
                "emoji_generator": emoji_generator,
            },
            "pymdownx.highlight": {
                "use_pygments": False,
            },
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

    ns_attr_list = "".join(
        f' xmlns:{key}="{value}"' for key, value in namespaces.items()
    )

    data = [
        '<?xml version="1.0"?>',
        f'<!DOCTYPE ac:confluence PUBLIC "-//Atlassian//Confluence 4 Page//EN" "{dtd_path.as_posix()}">'
        f"<root{ns_attr_list}>",
    ]
    data.extend(items)
    data.append("</root>")

    try:
        return ET.fromstringlist(data, parser=parser)
    except ET.XMLSyntaxError as e:
        raise ParseError(e)


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


@dataclass
class ConfluenceSiteMetadata:
    domain: str
    base_path: str
    space_key: Optional[str]


@dataclass
class ConfluencePageMetadata:
    page_id: str
    space_key: Optional[str]
    title: str


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
    :param render_mermaid: Whether to pre-render Mermaid diagrams into PNG/SVG images.
    :param diagram_output_format: Target image format for diagrams.
    :param webui_links: When true, convert relative URLs to Confluence Web UI links.
    """

    ignore_invalid_url: bool = False
    heading_anchors: bool = False
    render_mermaid: bool = False
    diagram_output_format: Literal["png", "svg"] = "png"
    webui_links: bool = False


class ConfluenceStorageFormatConverter(NodeVisitor):
    "Transforms a plain HTML tree into the Confluence storage format."

    options: ConfluenceConverterOptions
    path: Path
    base_dir: Path
    root_dir: Path
    toc: TableOfContents
    links: list[str]
    images: list[Path]
    embedded_images: dict[str, bytes]
    site_metadata: ConfluenceSiteMetadata
    page_metadata: dict[Path, ConfluencePageMetadata]

    def __init__(
        self,
        options: ConfluenceConverterOptions,
        path: Path,
        root_dir: Path,
        site_metadata: ConfluenceSiteMetadata,
        page_metadata: dict[Path, ConfluencePageMetadata],
    ) -> None:
        super().__init__()
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

    def _transform_link(self, anchor: ET._Element) -> Optional[ET._Element]:
        url = anchor.attrib.get("href")
        if url is None or is_absolute_url(url):
            return None

        LOGGER.debug("Found link %s relative to %s", url, self.path)
        relative_url: ParseResult = urlparse(url)

        if (
            not relative_url.scheme
            and not relative_url.netloc
            and not relative_url.path
            and not relative_url.params
            and not relative_url.query
        ):
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
                anchor.attrib["href"] = url
                return None

        # convert the relative URL to absolute URL based on the base path value, then look up
        # the absolute path in the page metadata dictionary to discover the relative path
        # within Confluence that should be used
        absolute_path = (self.base_dir / relative_url.path).resolve(True)
        if not str(absolute_path).startswith(str(self.root_dir)):
            msg = f"relative URL {url} points to outside root path: {self.root_dir}"
            if self.options.ignore_invalid_url:
                LOGGER.warning(msg)
                anchor.attrib.pop("href")
                return None
            else:
                raise DocumentError(msg)

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
        LOGGER.debug(
            "found link to page %s with metadata: %s", relative_path, link_metadata
        )
        self.links.append(url)

        if self.options.webui_links:
            page_url = f"{self.site_metadata.base_path}pages/viewpage.action?pageId={link_metadata.page_id}"
        else:
            space_key = link_metadata.space_key or self.site_metadata.space_key

            if space_key is None:
                raise DocumentError(
                    "Confluence space key required for building full web URLs"
                )

            page_url = f"{self.site_metadata.base_path}spaces/{space_key}/pages/{link_metadata.page_id}/{link_metadata.title}"

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
        src = image.attrib.get("src")

        if not src:
            raise DocumentError("image lacks `src` attribute")

        attributes: dict[str, Any] = {
            ET.QName(namespaces["ac"], "align"): "center",
            ET.QName(namespaces["ac"], "layout"): "center",
        }
        width = image.attrib.get("width")
        if width is not None:
            attributes.update({ET.QName(namespaces["ac"], "width"): width})
        height = image.attrib.get("height")
        if height is not None:
            attributes.update({ET.QName(namespaces["ac"], "height"): height})

        caption = image.attrib.get("alt")

        if is_absolute_url(src):
            return self._transform_external_image(src, caption, attributes)
        else:
            return self._transform_attached_image(Path(src), caption, attributes)

    def _transform_external_image(
        self, url: str, caption: Optional[str], attributes: dict[str, Any]
    ) -> ET._Element:
        "Emits Confluence Storage Format XHTML for an external image."

        elements: list[ET._Element] = []
        elements.append(
            RI(
                "url",
                # refers to an external image
                {ET.QName(namespaces["ri"], "value"): url},
            )
        )
        if caption is not None:
            elements.append(AC("caption", HTML.p(caption)))

        return AC("image", attributes, *elements)

    def _transform_attached_image(
        self, path: Path, caption: Optional[str], attributes: dict[str, Any]
    ) -> ET._Element:
        "Emits Confluence Storage Format XHTML for an attached image."

        # prefer PNG over SVG; Confluence displays SVG in wrong size, and text labels are truncated
        png_file = path.with_suffix(".png")
        if path.suffix == ".svg" and (self.base_dir / png_file).exists():
            path = png_file

        self.images.append(path)
        image_name = attachment_name(path)

        elements: list[ET._Element] = []
        elements.append(
            RI(
                "attachment",
                # refers to an attachment uploaded alongside the page
                {ET.QName(namespaces["ri"], "filename"): image_name},
            )
        )
        if caption is not None:
            elements.append(AC("caption", HTML.p(caption)))

        return AC("image", attributes, *elements)

    def _transform_block(self, code: ET._Element) -> ET._Element:
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
            image_filename = attachment_name(
                f"embedded_{image_hash}.{self.options.diagram_output_format}"
            )
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
                    ET.QName(namespaces["ac"], "data-layout"): "default",
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
        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "toc",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "outline"}, "clear"),
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "style"}, "default"),
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

    def _transform_alert(
        self, elem: ET._Element, class_name: Optional[str], skip: int
    ) -> ET._Element:
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
        [GitHub collapsed section](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections)  # noqa: E501 # no way to make this link shorter
        syntax into the Confluence structured macro *expand*.
        """

        if elem[0].tag != "summary":
            raise DocumentError(
                "expected: `<summary>` as first direct child of `<details>`"
            )
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
        shortname = elem.attrib.get("data-emoji", "")
        alt = elem.text or ""

        # <ac:emoticon ac:name="wink" ac:emoji-shortname=":wink:" ac:emoji-id="1f609" ac:emoji-fallback="&#128521;"/>
        # <ac:emoticon ac:name="blue-star" ac:emoji-shortname=":heavy_plus_sign:" ac:emoji-id="2795" ac:emoji-fallback="&#10133;"/>
        # <ac:emoticon ac:name="blue-star" ac:emoji-shortname=":heavy_minus_sign:" ac:emoji-id="2796" ac:emoji-fallback="&#10134;"/>
        return AC(
            "emoticon",
            {
                # use "blue-star" as a placeholder name to ensure wiki page loads in timely manner
                ET.QName(namespaces["ac"], "name"): "blue-star",
                ET.QName(namespaces["ac"], "emoji-shortname"): f":{shortname}:",
                ET.QName(namespaces["ac"], "emoji-fallback"): alt,
            },
        )

    def transform(self, child: ET._Element) -> Optional[ET._Element]:
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
        elif (
            child.tag == "blockquote"
            and len(child) > 0
            and child[0].tag == "p"
            and child[0].text is not None
            and child[0].text.startswith("[!")
        ):
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
            and starts_with_any(
                child[0].text, ["FLAG:", "NOTE:", "WARNING:", "DISCLAIMER:"]
            )
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
            return self._transform_block(child[0])

        elif child.tag == "span" and child.attrib.has_key("data-emoji"):
            return self._transform_emoji(child)

        return None


class ConfluenceStorageFormatCleaner(NodeVisitor):
    "Removes volatile attributes from a Confluence storage format XHTML document."

    def transform(self, child: ET._Element) -> Optional[ET._Element]:
        child.attrib.pop(ET.QName(namespaces["ac"], "macro-id"), None)
        child.attrib.pop(ET.QName(namespaces["ri"], "version-at-save"), None)
        return None


class DocumentError(RuntimeError):
    "Raised when a converted Markdown document has an unexpected element or attribute."


def extract_value(pattern: str, text: str) -> tuple[Optional[str], str]:
    values: list[str] = []

    def _repl_func(matchobj: re.Match) -> str:
        values.append(matchobj.group(1))
        return ""

    text = re.sub(pattern, _repl_func, text, 1, re.ASCII)
    value = values[0] if values else None
    return value, text


@dataclass
class ConfluenceQualifiedID:
    page_id: str
    space_key: Optional[str] = None

    def __init__(self, page_id: str, space_key: Optional[str] = None):
        self.page_id = page_id
        self.space_key = space_key


def extract_qualified_id(text: str) -> tuple[Optional[ConfluenceQualifiedID], str]:
    "Extracts the Confluence page ID and space key from a Markdown document."

    page_id, text = extract_value(r"<!--\s+confluence-page-id:\s*(\d+)\s+-->", text)

    if page_id is None:
        return None, text

    # extract Confluence space key
    space_key, text = extract_value(r"<!--\s+confluence-space-key:\s*(\S+)\s+-->", text)

    return ConfluenceQualifiedID(page_id, space_key), text


def extract_frontmatter(text: str) -> tuple[Optional[str], str]:
    "Extracts the front matter from a Markdown document."

    return extract_value(r"(?ms)\A---$(.+?)^---$", text)


def extract_frontmatter_title(text: str) -> tuple[Optional[str], str]:
    frontmatter, text = extract_frontmatter(text)

    title: Optional[str] = None
    if frontmatter is not None:
        properties = yaml.safe_load(frontmatter)
        if isinstance(properties, dict):
            property_title = properties.get("title")
            if isinstance(property_title, str):
                title = property_title

    return title, text


def read_qualified_id(absolute_path: Path) -> Optional[ConfluenceQualifiedID]:
    "Reads the Confluence page ID and space key from a Markdown document."

    with open(absolute_path, "r", encoding="utf-8") as f:
        document = f.read()

    qualified_id, _ = extract_qualified_id(document)
    return qualified_id


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
    :param render_mermaid: Whether to pre-render Mermaid diagrams into PNG/SVG images.
    :param diagram_output_format: Target image format for diagrams.
    :param webui_links: When true, convert relative URLs to Confluence Web UI links.
    """

    ignore_invalid_url: bool = False
    heading_anchors: bool = False
    generated_by: Optional[str] = "This page has been generated with a tool."
    root_page_id: Optional[str] = None
    keep_hierarchy: bool = False
    render_mermaid: bool = False
    diagram_output_format: Literal["png", "svg"] = "png"
    webui_links: bool = False


class ConfluenceDocument:
    id: ConfluenceQualifiedID
    title: Optional[str]
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
        page_metadata: dict[Path, ConfluencePageMetadata],
    ) -> "ConfluenceDocument":
        path = path.resolve(True)

        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        # extract Confluence page ID
        qualified_id, text = extract_qualified_id(text)
        if qualified_id is None:
            # look up Confluence page ID in metadata
            metadata = page_metadata.get(path)
            if metadata is not None:
                qualified_id = ConfluenceQualifiedID(
                    metadata.page_id, metadata.space_key
                )
        if qualified_id is None:
            raise PageError("missing Confluence page ID")

        return ConfluenceDocument(
            path, text, qualified_id, options, root_dir, site_metadata, page_metadata
        )

    def __init__(
        self,
        path: Path,
        text: str,
        qualified_id: ConfluenceQualifiedID,
        options: ConfluenceDocumentOptions,
        root_dir: Path,
        site_metadata: ConfluenceSiteMetadata,
        page_metadata: dict[Path, ConfluencePageMetadata],
    ) -> None:
        self.options = options
        self.id = qualified_id

        # extract 'generated-by' tag text
        generated_by_tag, text = extract_value(
            r"<!--\s+generated-by:\s*(.*)\s+-->", text
        )

        # extract frontmatter
        self.title, text = extract_frontmatter_title(text)

        # convert to HTML
        html = markdown_to_html(text)

        # parse Markdown document
        if self.options.generated_by is not None:
            generated_by = self.options.generated_by
            if generated_by_tag is not None:
                generated_by = generated_by_tag

            content = [
                '<ac:structured-macro ac:name="info" ac:schema-version="1">',
                f"<ac:rich-text-body><p>{generated_by}</p></ac:rich-text-body>",
                "</ac:structured-macro>",
                html,
            ]
        else:
            content = [html]
        self.root = elements_from_strings(content)

        converter = ConfluenceStorageFormatConverter(
            ConfluenceConverterOptions(
                ignore_invalid_url=self.options.ignore_invalid_url,
                heading_anchors=self.options.heading_anchors,
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

        if self.title is None:
            self.title = converter.toc.get_title()

    def xhtml(self) -> str:
        return elements_to_string(self.root)


def attachment_name(name: Union[Path, str]) -> str:
    """
    Safe name for use with attachment uploads.

    Allowed characters:
    * Alphanumeric characters: 0-9, a-z, A-Z
    * Special characters: hyphen (-), underscore (_), period (.)
    """

    return re.sub(r"[^\-0-9A-Za-z_.]", "_", str(name))


def sanitize_confluence(html: str) -> str:
    "Generates a sanitized version of a Confluence storage format XHTML document with no volatile attributes."

    if not html:
        return ""

    root = elements_from_strings([html])
    ConfluenceStorageFormatCleaner().visit(root)
    return elements_to_string(root)


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

    ns_attr_list = "".join(
        f' xmlns:{key}="{value}"' for key, value in namespaces.items()
    )

    data = [
        '<?xml version="1.0"?>',
        f'<!DOCTYPE ac:confluence PUBLIC "-//Atlassian//Confluence 4 Page//EN" "{dtd_path}">'
        f"<root{ns_attr_list}>",
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
