"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
import typing
from typing import Any, TypeVar

import yaml

from .serializer import JsonType, json_to_object

D = TypeVar("D")


def extract_value(pattern: str, text: str) -> tuple[str | None, str]:
    """
    Extracts the value captured by the first group in a regular expression.

    :returns: A tuple of (1) the value extracted and (2) remaining text without the captured text.
    """

    expr = re.compile(pattern)
    if expr.groups != 1:
        raise ValueError("expected: a single group whose value to extract")

    class _Matcher:
        value: str | None = None

        def __call__(self, match: re.Match[str]) -> str:
            self.value = match.group(1)
            return ""

    matcher = _Matcher()
    text = expr.sub(matcher, text, count=1)
    return matcher.value, text


def extract_frontmatter_block(text: str) -> tuple[str | None, str]:
    "Extracts the front-matter from a Markdown document as a blob of unparsed text."

    return extract_value(r"(?ms)\A---$(.+?)^---$", text)


def extract_frontmatter_json(text: str) -> tuple[dict[str, JsonType] | None, str]:
    "Extracts the front-matter from a Markdown document as a dictionary."

    block, text = extract_frontmatter_block(text)

    properties: dict[str, Any] | None = None
    if block is not None:
        data = yaml.safe_load(block)
        if isinstance(data, dict):
            properties = typing.cast(dict[str, JsonType], data)

    return properties, text


def extract_frontmatter_object(tp: type[D], text: str) -> tuple[D | None, str]:
    properties, text = extract_frontmatter_json(text)

    value_object: D | None = None
    if properties is not None:
        value_object = json_to_object(tp, properties)

    return value_object, text
