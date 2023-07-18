from dataclasses import dataclass
import logging
import importlib.resources as resources
import os.path
import pathlib
import re
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
from urllib.parse import urlparse

import lxml.etree as ET
import markdown
from lxml.builder import ElementMaker

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
    return bool(urlparse(url).netloc)


def markdown_to_html(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=[
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "pymdownx.tilde",
            "sane_lists",
        ],
    )


def _elements_from_strings(dtd_path: pathlib.Path, items: List[str]) -> ET.Element:
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


def elements_from_strings(items: List[str]) -> ET.Element:
    "Creates a fragment of several XML nodes from their string representation wrapped in a root element."

    if sys.version_info >= (3, 9):
        resource_path = resources.files(__package__).joinpath("entities.dtd")
        with resources.as_file(resource_path) as dtd_path:
            return _elements_from_strings(dtd_path, items)
    else:
        with resources.path(__package__, "entities.dtd") as dtd_path:
            return _elements_from_strings(dtd_path, items)


_languages = [
    "actionscript3",
    "bash",
    "csharp",
    "coldfusion",
    "cpp",
    "css",
    "delphi",
    "diff",
    "erlang",
    "groovy",
    "html",
    "java",
    "javafx",
    "javascript",
    "json",
    "perl",
    "php",
    "powershell",
    "python",
    "ruby",
    "scala",
    "sql",
    "vb",
    "xml",
]

@dataclass
class ConfluencePageMetadata:
    page_id: str
    space_key: str
    title: str


class NodeVisitor:
    def visit(self, node: ET.Element) -> None:
        if len(node) < 1:
            return

        for index in range(len(node)):
            source = node[index]
            target = self.transform(source)
            if target is not None:
                node[index] = target
            else:
                self.visit(source)

    def transform(self, child: ET.Element) -> Optional[ET.Element]:
        pass


def _change_ext(path: str, target_ext: str) -> str:
    root, source_ext = os.path.splitext(path)
    return f"{root}{target_ext}"


class ConfluenceStorageFormatConverter(NodeVisitor):
    "Transforms a plain HTML tree into the Confluence storage format."

    path: str
    base_path: str
    links: List[str]
    images: List[str]
    page_metadata: Dict[str, ConfluencePageMetadata]

    def __init__(self, path: str, page_metadata: Dict[str, ConfluencePageMetadata] = dict()) -> None:
        super().__init__()
        self.path = path
        self.base_path = os.path.dirname(path)
        self.links = []
        self.images = []
        self.page_metadata = page_metadata

    def _transform_link(self, anchor: ET.Element) -> ET.Element:
        url = anchor.attrib["href"]
        if not is_absolute_url(url):
            LOGGER.debug(f"found link {url} relative to {self.path}")
            self.links.append(url)
            # Convert the relative href to absolute based on relative url the base path value then
            # look up the absolute path in the page metadata dictionary to discover
            # the relative path within confluence that should be used
            abs_path = os.path.abspath(
                os.path.join(os.path.abspath(self.base_path), url)
            )

            # Transform relative urls like "#page_anchor" to "$pagepath#page_anchor"
            if url.startswith("#"):
                abs_path = self.path + url

            # The path prior to the page anchor if it exists
            page_path = abs_path.split("#")[0]

            # lookup page metadata using the page path (without the achor)
            link_metadata = self.page_metadata.get(page_path)
            relative_url = None
            if link_metadata:
                LOGGER.debug(f"found page {page_path} with metadata: {link_metadata}")
                confluence_page_id = link_metadata.page_id
                confluence_space_key = link_metadata.space_key
                relative_url = f"https://onemedical.atlassian.net/wiki/spaces/{confluence_space_key}/pages/{confluence_page_id}"

                if "#" in url:
                    page_anchor = url.split("#", 1)[-1]
                    confluence_page_title = link_metadata.title # link_metadata[2]
                    if confluence_page_title != None:
                        confluence_page_title = confluence_page_title.replace(" ", "+")
                        relative_url = f"{relative_url}/{confluence_page_title}#{page_anchor}"
            else:
                LOGGER.warn(f"unable to find page metadata for {page_path}")

            if relative_url != None:
                # Set confluence relative URL
                LOGGER.debug(f"relative url: {url} now: {relative_url}") # change to debug
                anchor.attrib["href"] = relative_url
            else:
                LOGGER.warn(f"unable to set relative url for {url} {abs_path}")


    def _transform_image(self, image: ET.Element) -> ET.Element:
        path: str = image.attrib["src"]

        # prefer PNG over SVG; Confluence displays SVG in wrong size, and text labels are truncated
        if path and not is_absolute_url(path) and path.endswith(".svg"):
            replacement_path = _change_ext(path, ".png")
            if os.path.exists(os.path.join(self.base_path, replacement_path)):
                path = replacement_path

        self.images.append(path)
        caption = image.attrib["alt"]
        return AC(
            "image",
            {
                ET.QName(namespaces["ac"], "align"): "center",
                ET.QName(namespaces["ac"], "layout"): "center",
            },
            RI("attachment", {ET.QName(namespaces["ri"], "filename"): path}),
            AC("caption", HTML.p(caption)),
        )

    def _transform_block(self, code: ET.Element) -> ET.Element:
        language = code.attrib.get("class")
        if language:
            m = re.match("^language-(.*)$", language)
            if m:
                language = m.group(1)
            else:
                language = "none"
        if language not in _languages:
            language = "none"
        content: str = code.text
        content = content.rstrip()
        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "code",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "theme"}, "Midnight"),
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "language"}, language),
            AC(
                "parameter", {ET.QName(namespaces["ac"], "name"): "linenumbers"}, "true"
            ),
            AC("plain-text-body", ET.CDATA(content)),
        )

    def _transform_toc(self, code: ET.Element) -> ET.Element:
        return AC(
            "structured-macro",
            {
                ET.QName(namespaces["ac"], "name"): "toc",
                ET.QName(namespaces["ac"], "schema-version"): "1",
            },
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "outline"}, "clear"),
            AC("parameter", {ET.QName(namespaces["ac"], "name"): "style"}, "default"),
        )

    def transform(self, child: ET.Element) -> Optional[ET.Element]:
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

        # <img src="..." alt="..." />
        elif child.tag == "img":
            return self._transform_image(child)

        # <a href="..."> ... </a>
        elif child.tag == "a":
            return self._transform_link(child)

        # <pre><code class="language-java"> ... </code></pre>
        elif child.tag == "pre" and len(child) == 1 and child[0].tag == "code":
            return self._transform_block(child[0])

        return None


class ConfluenceStorageFormatCleaner(NodeVisitor):
    "Removes volatile attributes from a Confluence storage format XHTML document."

    def transform(self, child: ET.Element) -> Optional[ET.Element]:
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
class ConfluenceDocumentOptions:
    """
    Options that control the generated page content.

    :param show_generated: Whether to display a prompt "This page has been generated with a tool."
    """

    generated_by: Optional[str] = "This page has been generated with a tool."


class ConfluenceDocument:
    page_id: str
    space_key: Optional[str] = None
    links: List[str]
    images: List[str]

    options: ConfluenceDocumentOptions
    root: ET.Element

    def __init__(self, path: str, options: ConfluenceDocumentOptions, page_metadata: Dict[str, ConfluencePageMetadata] = dict()) -> None:
        self.options = options
        path = os.path.abspath(path)

        with open(path, "r") as f:
            html = markdown_to_html(f.read())

        # extract Confluence page ID
        page_id, html = extract_value(r"<!--\s+confluence-page-id:\s*(\d+)\s+-->", html)
        if page_id is None:
            raise DocumentError(
                "Markdown document has no Confluence page ID associated with it"
            )
        self.page_id = page_id

        # extract Confluence space key
        self.space_key, html = extract_value(
            r"<!--\s+confluence-space-key:\s*(\w+)\s+-->", html
        )

        # extract 'generated-by' tag text
        generated_by_tag, html = extract_value(
            r"<!--\s+generated-by:\s*(.*)\s+-->", html
        )

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

        converter = ConfluenceStorageFormatConverter(path, page_metadata)
        converter.visit(self.root)
        self.links = converter.links
        self.images = converter.images

    def xhtml(self) -> str:
        return _content_to_string(self.root)

    def title(self) -> str:
        return _content_title(self.root)

    def metadata(self) -> ConfluencePageMetadata:
        return ConfluencePageMetadata(
            page_id=self.page_id,
            space_key=self.space_key or "",
            title=self.title()
        )



def sanitize_confluence(html: str) -> str:
    "Generates a sanitized version of a Confluence storage format XHTML document with no volatile attributes."

    if not html:
        return ""

    root = elements_from_strings([html])
    ConfluenceStorageFormatCleaner().visit(root)
    return _content_to_string(root)


def _content_title(root: ET.Element) -> str:
    xml = ET.tostring(root, encoding="utf8", method="xml").decode("utf8")
    m = re.match(r".*<h1>(.*)</h1>.*", xml, re.DOTALL)

    # if the contents of the page are empty
    if m is None:
        return ""

    return m.group(1)


def _content_to_string(root: ET.Element) -> str:
    xml = ET.tostring(root, encoding="utf8", method="xml").decode("utf8")
    m = re.match(r"^<root\s+[^>]*>(.*)</root>\s*$", xml, re.DOTALL)
    if m:
        return m.group(1)
    else:
        raise ValueError("expected: Confluence content")
