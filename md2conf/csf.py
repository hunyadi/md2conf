"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import importlib.resources as resources
import re
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import lxml.etree as ET
from lxml.builder import ElementMaker

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]

# XML namespaces typically associated with Confluence Storage Format documents
_namespaces = {
    "ac": "http://atlassian.com/content",
    "ri": "http://atlassian.com/resource/identifier",
}
for key, value in _namespaces.items():
    ET.register_namespace(key, value)

HTML = ElementMaker()
AC_ELEM = ElementMaker(namespace=_namespaces["ac"])
RI_ELEM = ElementMaker(namespace=_namespaces["ri"])


class ParseError(RuntimeError):
    pass


def _qname(namespace_uri: str, name: str) -> str:
    return ET.QName(namespace_uri, name).text


def AC_ATTR(name: str) -> str:
    return _qname(_namespaces["ac"], name)


def RI_ATTR(name: str) -> str:
    return _qname(_namespaces["ri"], name)


@contextmanager
def entities() -> Generator[Path, None, None]:
    "Invokes a callable in the context of an entity definition file."

    if __package__ is not None:  # always true at run time
        resource_path = resources.files(__package__).joinpath("entities.dtd")
        with resources.as_file(resource_path) as dtd_path:
            yield dtd_path


def _elements_from_strings(dtd_path: Path, items: list[str]) -> ElementType:
    """
    Creates an XML document tree from XML fragment strings.

    This function
    * adds an XML declaration,
    * wraps the content in a root element,
    * adds namespace declarations associated with Confluence documents.

    :param dtd_path: Path to a DTD document that defines entities like `&cent;` or `&copy;`.
    :param items: Strings to parse into XML fragments.
    :returns: An XML document as an element tree.
    """

    parser = ET.XMLParser(
        remove_blank_text=True,
        remove_comments=True,
        strip_cdata=False,
        load_dtd=True,
    )

    ns_attr_list = "".join(f' xmlns:{key}="{value}"' for key, value in _namespaces.items())

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


def elements_from_strings(items: list[str]) -> ElementType:
    """
    Creates a Confluence Storage Format XML document tree from XML fragment strings.

    A root element is created to hold several XML fragments.

    :param items: Strings to parse into XML fragments.
    :returns: An XML document as an element tree.
    """

    with entities() as dtd_path:
        return _elements_from_strings(dtd_path, items)


def elements_from_string(content: str) -> ElementType:
    """
    Creates a Confluence Storage Format XML document tree from an XML string.

    :param content: String to parse into XML.
    :returns: An XML document as an element tree.
    """

    return elements_from_strings([content])


def _content_to_string(dtd_path: Path, content: str) -> str:
    tree = _elements_from_strings(dtd_path, [content])
    return ET.tostring(tree, pretty_print=True).decode("utf-8")


def content_to_string(content: str) -> str:
    """
    Converts a Confluence Storage Format document returned by the Confluence REST API into a readable XML document.

    This function
    * adds an XML declaration,
    * wraps the content in a root element,
    * adds namespace declarations associated with Confluence documents.

    :param content: Confluence Storage Format content as a string.
    :returns: XML as a string.
    """

    with entities() as dtd_path:
        return _content_to_string(dtd_path, content)


def elements_to_string(root: ElementType) -> str:
    """
    Converts a Confluence Storage Format element tree into an XML string to push to Confluence REST API.

    :param root: Synthesized XML element tree of a Confluence Storage Format document.
    :returns: XML as a string.
    """

    xml = ET.tostring(root, encoding="utf8", method="xml").decode("utf8")
    m = re.match(r"^<root\s+[^>]*>(.*)</root>\s*$", xml, re.DOTALL)
    if m:
        return m.group(1)
    else:
        raise ValueError("expected: Confluence content")


def is_block_like(elem: ElementType) -> bool:
    return elem.tag in ["div", "li", "ol", "p", "pre", "td", "th", "ul"]


def normalize_inline(elem: ElementType) -> None:
    """
    Ensures that inline elements are direct children of an eligible block element.

    The following transformations are applied:

    * consecutive inline elements and text nodes that are the direct children of the parent element are wrapped into a `<p>`,
    * block elements are left intact,
    * leading and trailing whitespace in each block element is removed.

    The above steps transform an element tree such as
    ```
    <li>  to <em>be</em>, <ol/> not to <em>be</em>  </li>
    ```

    into another element tree such as
    ```
    <li><p>to <em>be</em>,</p><ol/><p>not to <em>be</em></p></li>
    ```
    """

    if not is_block_like(elem):
        raise ValueError(f"expected: block element; got: {elem.tag!s}")

    contents: list[ElementType] = []

    paragraph = HTML.p()
    contents.append(paragraph)
    if elem.text:
        paragraph.text = elem.text
        elem.text = None

    for child in elem:
        if is_block_like(child):
            contents.append(child)
            paragraph = HTML.p()
            contents.append(paragraph)
            if child.tail:
                paragraph.text = child.tail
                child.tail = None
        else:
            paragraph.append(child)

    for item in contents:
        # remove lead whitespace in the block element
        if item.text:
            item.text = item.text.lstrip()
        if len(item) > 0:
            # remove tail whitespace in the last child of the block element
            last = item[-1]
            if last.tail:
                last.tail = last.tail.rstrip()
        else:
            # remove tail whitespace directly in the block element content
            if item.text:
                item.text = item.text.rstrip()

        # ignore empty elements
        if item.tag != "p" or len(item) > 0 or item.text:
            elem.append(item)
