"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, TypeVar

import yaml
from strong_typing.core import JsonType
from strong_typing.serialization import DeserializerOptions, json_to_object

T = TypeVar("T")


def _json_to_object(
    typ: type[T],
    data: JsonType,
) -> T:
    return json_to_object(typ, data, options=DeserializerOptions(skip_unassigned=True))


def extract_value(pattern: str, text: str) -> tuple[Optional[str], str]:
    values: list[str] = []

    def _repl_func(matchobj: re.Match[str]) -> str:
        values.append(matchobj.group(1))
        return ""

    text = re.sub(pattern, _repl_func, text, count=1, flags=re.ASCII)
    value = values[0] if values else None
    return value, text


def extract_frontmatter_block(text: str) -> tuple[Optional[str], str]:
    "Extracts the front-matter from a Markdown document as a blob of unparsed text."

    return extract_value(r"(?ms)\A---$(.+?)^---$", text)


def extract_frontmatter_properties(text: str) -> tuple[Optional[dict[str, Any]], str]:
    "Extracts the front-matter from a Markdown document as a dictionary."

    block, text = extract_frontmatter_block(text)

    properties: Optional[dict[str, Any]] = None
    if block is not None:
        data = yaml.safe_load(block)
        if isinstance(data, dict):
            properties = data

    return properties, text


@dataclass
class DocumentProperties:
    """
    An object that holds properties extracted from the front-matter of a Markdown document.

    :param page_id: Confluence page ID.
    :param space_key: Confluence space key.
    :param confluence_page_id: Confluence page ID. (Alternative name for JSON de-serialization.)
    :param confluence_space_key: Confluence space key. (Alternative name for JSON de-serialization.)
    :param generated_by: Text identifying the tool that generated the document.
    :param title: The title extracted from front-matter.
    :param tags: A list of tags (content labels) extracted from front-matter.
    :param properties: A dictionary of key-value pairs extracted from front-matter to apply as page properties.
    """

    page_id: Optional[str]
    space_key: Optional[str]
    confluence_page_id: Optional[str]
    confluence_space_key: Optional[str]
    generated_by: Optional[str]
    title: Optional[str]
    tags: Optional[list[str]]
    properties: Optional[dict[str, JsonType]]


@dataclass
class ScannedDocument:
    """
    An object that holds properties extracted from a Markdown document, including remaining source text.

    :param page_id: Confluence page ID.
    :param space_key: Confluence space key.
    :param generated_by: Text identifying the tool that generated the document.
    :param title: The title extracted from front-matter.
    :param tags: A list of tags (content labels) extracted from front-matter.
    :param properties: A dictionary of key-value pairs extracted from front-matter to apply as page properties.
    :param text: Text that remains after front-matter and inline properties have been extracted.
    """

    page_id: Optional[str]
    space_key: Optional[str]
    generated_by: Optional[str]
    title: Optional[str]
    tags: Optional[list[str]]
    properties: Optional[dict[str, JsonType]]
    text: str


class Scanner:
    def read(self, absolute_path: Path) -> ScannedDocument:
        """
        Extracts essential properties from a Markdown document.
        """

        # parse file
        with open(absolute_path, "r", encoding="utf-8") as f:
            text = f.read()

        # extract Confluence page ID
        page_id, text = extract_value(r"<!--\s+confluence[-_]page[-_]id:\s*(\d+)\s+-->", text)

        # extract Confluence space key
        space_key, text = extract_value(r"<!--\s+confluence[-_]space[-_]key:\s*(\S+)\s+-->", text)

        # extract 'generated-by' tag text
        generated_by, text = extract_value(r"<!--\s+generated[-_]by:\s*(.*)\s+-->", text)

        title: Optional[str] = None
        tags: Optional[list[str]] = None
        properties: Optional[dict[str, JsonType]] = None

        # extract front-matter
        data, text = extract_frontmatter_properties(text)
        if data is not None:
            p = _json_to_object(DocumentProperties, data)
            page_id = page_id or p.confluence_page_id or p.page_id
            space_key = space_key or p.confluence_space_key or p.space_key
            generated_by = generated_by or p.generated_by
            title = p.title
            tags = p.tags
            properties = p.properties

        return ScannedDocument(
            page_id=page_id,
            space_key=space_key,
            generated_by=generated_by,
            title=title,
            tags=tags,
            properties=properties,
            text=text,
        )
