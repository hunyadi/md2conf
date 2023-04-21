import os.path
import re
from typing import List, Optional, Tuple
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


def elements_from_strings(items: List[str]) -> ET.Element:
    "Creates a fragment of several XML nodes from their string representation wrapped in a root element."

    parser = ET.XMLParser(remove_blank_text=True, strip_cdata=False)

    ns_attr_list = "".join(
        f' xmlns:{key}="{value}"' for key, value in namespaces.items()
    )
    data = [
        '<?xml version="1.0"?>',
        f"<root{ns_attr_list}>",
    ]
    data.extend(items)
    data.append("</root>")

    try:
        return ET.fromstringlist(data, parser=parser)
    except ET.XMLSyntaxError as e:
        raise ParseError(e)


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

    base_path: str
    links: List[str]
    images: List[str]

    def __init__(self, base_path: str) -> None:
        super().__init__()
        self.base_path = base_path
        self.links = []
        self.images = []

    def _transform_link(self, anchor: ET.Element) -> ET.Element:
        url = anchor.attrib["href"]
        if not is_absolute_url(url):
            self.links.append(url)

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


def _extract_value(pattern: str, string: str) -> Tuple[Optional[str], str]:
    values: List[str] = []

    def _repl_func(matchobj: re.Match) -> str:
        values.append(matchobj.group(1))
        return ""

    string = re.sub(pattern, _repl_func, string, 1, re.ASCII)
    value = values[0] if values else None
    return value, string


class ConfluenceDocument:
    page_id: str
    space_key: Optional[str] = None
    links: List[str]
    images: List[str]

    root: ET.Element

    def __init__(self, path: str) -> None:
        path = os.path.abspath(path)

        with open(path, "r") as f:
            html = markdown_to_html(f.read())

        # extract Confluence page ID
        page_id, html = _extract_value(
            r"<!--\s+confluence-page-id:\s*(\d+)\s+-->", html
        )
        if page_id is None:
            raise DocumentError(
                "Markdown document has no Confluence page ID associated with it"
            )
        self.page_id = page_id

        # extract Confluence space key
        self.space_key, html = _extract_value(
            r"<!--\s+confluence-space-key:\s*(\w+)\s+-->", html
        )

        # parse Markdown document
        self.root = elements_from_strings(
            [
                '<ac:structured-macro ac:name="info" ac:schema-version="1">',
                "<ac:rich-text-body><p>This page has been generated with a tool.</p></ac:rich-text-body>",
                "</ac:structured-macro>",
                html,
            ]
        )

        converter = ConfluenceStorageFormatConverter(os.path.dirname(path))
        converter.visit(self.root)
        self.links = converter.links
        self.images = converter.images

    def xhtml(self) -> str:
        return _content_to_string(self.root)


def sanitize_confluence(html: str) -> str:
    "Generates a sanitized version of a Confluence storage format XHTML document with no volatile attributes."

    root = elements_from_strings([html])
    ConfluenceStorageFormatCleaner().visit(root)
    return _content_to_string(root)


def _content_to_string(root: ET.Element) -> str:
    xml = ET.tostring(root, encoding="utf8", method="xml").decode("utf8")
    m = re.match(r"^<root\s+[^>]*>(.*)</root>\s*$", xml, re.DOTALL)
    if m:
        return m.group(1)
    else:
        raise ValueError("expected: Confluence content")
