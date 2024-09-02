# mypy: disable-error-code="dict-item"

import hashlib
import importlib.resources as resources
import logging
import os.path
import pathlib
import re
import sys
import uuid
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Tuple
from urllib.parse import ParseResult, urlparse, urlunparse

import lxml.etree as ET
import markdown
from lxml.builder import ElementMaker

from . import mermaid

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


def is_absolute_url(url: str) -> bool:
    urlparts = urlparse(url)
    return bool(urlparts.scheme) or bool(urlparts.netloc)


def is_relative_url(url: str) -> bool:
    urlparts = urlparse(url)
    return not bool(urlparts.scheme) and not bool(urlparts.netloc)


def markdown_to_html(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=[
            "admonition",
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "pymdownx.magiclink",
            "pymdownx.tilde",
            "sane_lists",
            "md_in_html",
        ],
    )


def _elements_from_strings(dtd_path: pathlib.Path, items: List[str]) -> ET._Element:
    """
    Creates a fragment of several XML nodes from their string representation wrapped in a root element.

    :param dtd_path: Path to a DTD document that defines entities like &cent; or &copy;.
    :param items: Strings to parse into XML fragments.
    :returns: An XML document as an element tree.
    """

    parser = ET.XMLParser(
        remove_blank_text=True,
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
    data.extend(items)
    data.append("</root>")

    try:
        return ET.fromstringlist(data, parser=parser)
    except ET.XMLSyntaxError as e:
        raise ParseError(e)


def elements_from_strings(items: List[str]) -> ET._Element:
    "Creates a fragment of several XML nodes from their string representation wrapped in a root element."

    if sys.version_info >= (3, 9):
        resource_path = resources.files(__package__).joinpath("entities.dtd")
        with resources.as_file(resource_path) as dtd_path:
            return _elements_from_strings(dtd_path, items)
    else:
        with resources.path(__package__, "entities.dtd") as dtd_path:
            return _elements_from_strings(dtd_path, items)


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
class ConfluencePageMetadata:
    domain: str
    base_path: str
    page_id: str
    space_key: str
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


@dataclass
class ConfluenceConverterOptions:
    """
    Options for converting an HTML tree into Confluence storage format.

    :param ignore_invalid_url: When true, ignore invalid URLs in input, emit a warning and replace the anchor with
        plain text; when false, raise an exception.
    """

    ignore_invalid_url: bool = False
    render_mermaid: bool = False
    diagram_output_format: Literal["png", "svg"] = "png"


class ConfluenceStorageFormatConverter(NodeVisitor):
    "Transforms a plain HTML tree into the Confluence storage format."

    options: ConfluenceConverterOptions
    path: pathlib.Path
    base_path: pathlib.Path
    links: List[str]
    images: List[str]
    embedded_images: Dict[str, bytes]
    page_metadata: Dict[pathlib.Path, ConfluencePageMetadata]

    def __init__(
        self,
        options: ConfluenceConverterOptions,
        path: pathlib.Path,
        page_metadata: Dict[pathlib.Path, ConfluencePageMetadata],
    ) -> None:
        super().__init__()
        self.options = options
        self.path = path
        self.base_path = path.parent
        self.links = []
        self.images = []
        self.embedded_images = {}
        self.page_metadata = page_metadata

    def _transform_link(self, anchor: ET._Element) -> None:
        url = anchor.attrib["href"]
        if is_absolute_url(url):
            return

        LOGGER.debug(f"found link {url} relative to {self.path}")
        relative_url: ParseResult = urlparse(url)

        if (
            not relative_url.scheme
            and not relative_url.netloc
            and not relative_url.path
            and not relative_url.params
            and not relative_url.query
        ):
            LOGGER.debug(f"found local URL: {url}")
            anchor.attrib["href"] = url
            return

        # convert the relative URL to absolute URL based on the base path value, then look up
        # the absolute path in the page metadata dictionary to discover the relative path
        # within Confluence that should be used
        absolute_path = (self.base_path / relative_url.path).absolute()
        if not str(absolute_path).startswith(str(self.base_path)):
            msg = f"relative URL {url} points to outside base path: {self.base_path}"
            if self.options.ignore_invalid_url:
                LOGGER.warning(msg)
                anchor.attrib.pop("href")
                return
            else:
                raise DocumentError(msg)

        relative_path = os.path.relpath(absolute_path, self.base_path)

        link_metadata = self.page_metadata.get(absolute_path)
        if link_metadata is None:
            msg = f"unable to find matching page for URL: {url}"
            if self.options.ignore_invalid_url:
                LOGGER.warning(msg)
                anchor.attrib.pop("href")
                return
            else:
                raise DocumentError(msg)

        LOGGER.debug(
            f"found link to page {relative_path} with metadata: {link_metadata}"
        )
        self.links.append(url)

        components = ParseResult(
            scheme="https",
            netloc=link_metadata.domain,
            path=f"{link_metadata.base_path}spaces/{link_metadata.space_key}/pages/{link_metadata.page_id}/{link_metadata.title}",
            params="",
            query="",
            fragment=relative_url.fragment,
        )
        transformed_url = urlunparse(components)

        LOGGER.debug(f"transformed relative URL: {url} to URL: {transformed_url}")
        anchor.attrib["href"] = transformed_url

    def _transform_image(self, image: ET._Element) -> ET._Element:
        path: str = image.attrib["src"]

        # prefer PNG over SVG; Confluence displays SVG in wrong size, and text labels are truncated
        if path and is_relative_url(path):
            relative_path = pathlib.Path(path)
            if (
                relative_path.suffix == ".svg"
                and (self.base_path / relative_path.with_suffix(".png")).exists()
            ):
                path = str(relative_path.with_suffix(".png"))

        self.images.append(path)
        caption = image.attrib["alt"]
        return AC(
            "image",
            {
                ET.QName(namespaces["ac"], "align"): "center",
                ET.QName(namespaces["ac"], "layout"): "center",
            },
            RI(
                "attachment",
                {ET.QName(namespaces["ri"], "filename"): attachment_name(path)},
            ),
            AC("caption", HTML.p(caption)),
        )

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
                "Midnight",
            ),
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): "language"},
                language,
            ),
            AC(
                "parameter",
                {ET.QName(namespaces["ac"], "name"): "linenumbers"},
                "true",
            ),
            AC("plain-text-body", ET.CDATA(content)),
        )

    def _transform_mermaid(self, content: str) -> ET._Element:
        "Transforms a Mermaid diagram code block."

        if self.options.render_mermaid:
            image_data = mermaid.render(content, self.options.diagram_output_format)
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
        Creates an info, tip, note or warning panel.

        Transforms [Python-Markdown admonition](https://python-markdown.github.io/extensions/admonition/) syntax
        into Confluence structured macro syntax.
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

    def _transform_section(self, elem: ET._Element) -> ET._Element:
        """
        Creates a collapsed section.

        Transforms a [GitHub collapsed section](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/organizing-information-with-collapsed-sections)
        into the Confluence structured macro *expand*.
        """

        if elem[0].tag != "summary":
            raise DocumentError(
                "expected: `<summary>` as first direct child of `<details>`"
            )
        if elem[0].tail is not None:
            raise DocumentError('expected: attribute `markdown="1"` on `<details>`')
        summary = elem[0].text or ""
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

    def transform(self, child: ET._Element) -> Optional[ET._Element]:
        # normalize line breaks to regular space in element text
        if child.text:
            text: str = child.text
            child.text = text.replace("\n", " ")
        if child.tail:
            tail: str = child.tail
            child.tail = tail.replace("\n", " ")

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
            self._transform_link(child)
            return None

        # <pre><code class="language-java"> ... </code></pre>
        elif child.tag == "pre" and len(child) == 1 and child[0].tag == "code":
            return self._transform_block(child[0])

        return None


class ConfluenceStorageFormatCleaner(NodeVisitor):
    "Removes volatile attributes from a Confluence storage format XHTML document."

    def transform(self, child: ET._Element) -> Optional[ET._Element]:
        child.attrib.pop(ET.QName(namespaces["ac"], "macro-id"), None)
        child.attrib.pop(ET.QName(namespaces["ri"], "version-at-save"), None)
        return None


class DocumentError(RuntimeError):
    pass


def extract_value(pattern: str, string: str) -> Tuple[Optional[str], str]:
    values: List[str] = []

    def _repl_func(matchobj: re.Match) -> str:
        values.append(matchobj.group(1))
        return ""

    string = re.sub(pattern, _repl_func, string, 1, re.ASCII)
    value = values[0] if values else None
    return value, string


@dataclass
class ConfluenceQualifiedID:
    page_id: str
    space_key: Optional[str] = None


def extract_qualified_id(string: str) -> Tuple[Optional[ConfluenceQualifiedID], str]:
    page_id, string = extract_value(r"<!--\s+confluence-page-id:\s*(\d+)\s+-->", string)

    if page_id is None:
        return None, string

    # extract Confluence space key
    space_key, string = extract_value(
        r"<!--\s+confluence-space-key:\s*(\S+)\s+-->", string
    )

    return ConfluenceQualifiedID(page_id, space_key), string


@dataclass
class ConfluenceDocumentOptions:
    """
    Options that control the generated page content.

    :param ignore_invalid_url: When true, ignore invalid URLs in input, emit a warning and replace the anchor with
        plain text; when false, raise an exception.
    :param show_generated: Whether to display a prompt "This page has been generated with a tool."
    """

    ignore_invalid_url: bool = False
    generated_by: Optional[str] = "This page has been generated with a tool."
    root_page_id: Optional[str] = None
    render_mermaid: bool = False
    diagram_output_format: Literal["png", "svg"] = "png"


class ConfluenceDocument:
    id: ConfluenceQualifiedID
    links: List[str]
    images: List[str]

    options: ConfluenceDocumentOptions
    root: ET._Element

    def __init__(
        self,
        path: pathlib.Path,
        options: ConfluenceDocumentOptions,
        page_metadata: Dict[pathlib.Path, ConfluencePageMetadata],
    ) -> None:
        self.options = options
        path = path.absolute()

        with open(path, "r", encoding="utf-8") as f:
            text = f.read()

        # extract Confluence page ID
        qualified_id, text = extract_qualified_id(text)
        if qualified_id is None:
            raise ValueError("missing Confluence page ID")
        self.id = qualified_id

        # extract 'generated-by' tag text
        generated_by_tag, text = extract_value(
            r"<!--\s+generated-by:\s*(.*)\s+-->", text
        )

        # extract frontmatter
        frontmatter, text = extract_value(r"(?ms)\A---$(.+?)^---$", text)

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
                render_mermaid=self.options.render_mermaid,
                diagram_output_format=self.options.diagram_output_format,
            ),
            path,
            page_metadata,
        )
        converter.visit(self.root)
        self.links = converter.links
        self.images = converter.images
        self.embedded_images = converter.embedded_images

    def xhtml(self) -> str:
        return _content_to_string(self.root)


def attachment_name(name: str) -> str:
    """
    Safe name for use with attachment uploads.

    Allowed characters:
    * Alphanumeric characters: 0-9, a-z, A-Z
    * Special characters: hyphen (-), underscore (_), period (.)
    """

    return re.sub(r"[^\-0-9A-Za-z_.]", "_", name)


def sanitize_confluence(html: str) -> str:
    "Generates a sanitized version of a Confluence storage format XHTML document with no volatile attributes."

    if not html:
        return ""

    root = elements_from_strings([html])
    ConfluenceStorageFormatCleaner().visit(root)
    return _content_to_string(root)


def _content_to_string(root: ET._Element) -> str:
    xml = ET.tostring(root, encoding="utf8", method="xml").decode("utf8")
    m = re.match(r"^<root\s+[^>]*>(.*)</root>\s*$", xml, re.DOTALL)
    if m:
        return m.group(1)
    else:
        raise ValueError("expected: Confluence content")
