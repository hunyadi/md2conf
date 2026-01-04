"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from .coalesce import coalesce
from .frontmatter import extract_frontmatter_json, extract_value
from .options import LayoutOptions
from .serializer import JsonType, json_to_object

T = TypeVar("T")


@dataclass
class AliasProperties:
    """
    An object that holds properties extracted from the front-matter of a Markdown document.

    :param confluence_page_id: Confluence page ID. (Alternative name for JSON de-serialization.)
    :param confluence_space_key: Confluence space key. (Alternative name for JSON de-serialization.)
    """

    confluence_page_id: str | None = None
    confluence_space_key: str | None = None


@dataclass
class DocumentProperties:
    """
    An object that holds properties extracted from the front-matter of a Markdown document.

    :param page_id: Confluence page ID.
    :param space_key: Confluence space key.
    :param generated_by: Text identifying the tool that generated the document.
    :param title: The title extracted from front-matter.
    :param tags: A list of tags (content labels) extracted from front-matter.
    :param synchronized: True if the document content is parsed and synchronized with Confluence.
    :param properties: A dictionary of key-value pairs extracted from front-matter to apply as page properties.
    :param layout: Layout options for content on a Confluence page.
    """

    page_id: str | None = None
    space_key: str | None = None
    generated_by: str | None = None
    title: str | None = None
    tags: list[str] | None = None
    synchronized: bool | None = None
    properties: dict[str, JsonType] | None = None
    layout: LayoutOptions | None = None


@dataclass
class ScannedDocument:
    """
    An object that holds properties extracted from a Markdown document, including remaining source text.

    :param properties: Properties extracted from the front-matter of a Markdown document.
    :param text: Text that remains after front-matter and inline properties have been extracted.
    """

    properties: DocumentProperties
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

        body_props = DocumentProperties(page_id=page_id, space_key=space_key, generated_by=generated_by)

        # extract front-matter
        data, text = extract_frontmatter_json(text)
        if data is not None:
            frontmatter_props = json_to_object(DocumentProperties, data)
            alias_props = json_to_object(AliasProperties, data)
            if alias_props.confluence_page_id is not None:
                frontmatter_props.page_id = alias_props.confluence_page_id
            if alias_props.confluence_space_key is not None:
                frontmatter_props.space_key = alias_props.confluence_space_key
            props = coalesce(body_props, frontmatter_props)
        else:
            props = body_props

        return ScannedDocument(properties=props, text=text)
