"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml


def extract_value(pattern: str, text: str) -> tuple[Optional[str], str]:
    values: list[str] = []

    def _repl_func(matchobj: re.Match) -> str:
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


def get_string(properties: dict[str, Any], key: str) -> Optional[str]:
    value = properties.get(key)
    if value is None:
        return None
    elif not isinstance(value, str):
        raise ValueError(
            f"expected dictionary value type of `str` for key `{key}`; got value of type `{type(value).__name__}`"
        )
    else:
        return value


@dataclass
class ScannedDocument:
    """
    An object that holds properties extracted from a Markdown document, including remaining source text.

    :param page_id: Confluence page ID.
    :param space_key: Confluence space key.
    :param generated_by: Text identifying the tool that generated the document.
    :param title: The title extracted from front-matter.
    :param text: Text that remains after front-matter and inline properties have been extracted.
    """

    page_id: Optional[str]
    space_key: Optional[str]
    generated_by: Optional[str]
    title: Optional[str]
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
        page_id, text = extract_value(r"<!--\s+confluence-page-id:\s*(\d+)\s+-->", text)

        # extract Confluence space key
        space_key, text = extract_value(
            r"<!--\s+confluence-space-key:\s*(\S+)\s+-->", text
        )

        # extract 'generated-by' tag text
        generated_by, text = extract_value(r"<!--\s+generated-by:\s*(.*)\s+-->", text)

        title: Optional[str] = None

        # extract front-matter
        properties, text = extract_frontmatter_properties(text)
        if properties is not None:
            page_id = page_id or get_string(properties, "confluence-page-id")
            space_key = space_key or get_string(properties, "confluence-space-key")
            generated_by = generated_by or get_string(properties, "generated-by")
            title = get_string(properties, "title")

        return ScannedDocument(
            page_id=page_id,
            space_key=space_key,
            generated_by=generated_by,
            title=title,
            text=text,
        )
