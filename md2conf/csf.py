"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import importlib.resources as resources
import re
from pathlib import Path
from typing import Callable, TypeVar

import lxml.etree as ET
from lxml.builder import ElementMaker

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


R = TypeVar("R")


def with_entities(func: Callable[[Path], R]) -> R:
    "Invokes a callable in the context of an entity definition file."

    resource_path = resources.files(__package__).joinpath("entities.dtd")
    with resources.as_file(resource_path) as dtd_path:
        return func(dtd_path)


def _elements_from_strings(dtd_path: Path, items: list[str]) -> ET._Element:
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


def elements_from_strings(items: list[str]) -> ET._Element:
    """
    Creates a Confluence Storage Format XML document tree from XML fragment strings.

    A root element is created to hold several XML fragments.

    :param items: Strings to parse into XML fragments.
    :returns: An XML document as an element tree.
    """

    return with_entities(lambda dtd_path: _elements_from_strings(dtd_path, items))


def elements_from_string(content: str) -> ET._Element:
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

    return with_entities(lambda dtd_path: _content_to_string(dtd_path, content))


def elements_to_string(root: ET._Element) -> str:
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
