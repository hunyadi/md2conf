"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
import typing
from dataclasses import dataclass
from typing import TypeVar

import yaml

from .serializer import JsonType, json_to_object

D = TypeVar("D")


def extract_value(expr: re.Pattern[str], text: str) -> tuple[str | None, str]:
    """
    Extracts the value captured by the first group in a regular expression.

    :returns: A tuple of (1) the value extracted and (2) remaining text without the captured text.
    """

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


@dataclass
class FrontMatterProperties:
    data: dict[str, JsonType] | None
    inner_line_count: int

    @property
    def outer_line_count(self) -> int:
        return self.inner_line_count + 2  # account for enclosing `--` (double dash)


def _extract_frontmatter_block(expr: re.Pattern[str], text: str) -> tuple[FrontMatterProperties | None, str]:
    "Extracts the front-matter from a blob of unparsed text into a structured object."

    block, text = extract_value(expr, text)

    properties: FrontMatterProperties | None = None
    if block is not None:
        inner_line_count = block.count("\n")
        data = yaml.safe_load(block)
        if isinstance(data, dict):
            properties = FrontMatterProperties(typing.cast(dict[str, JsonType], data), inner_line_count)

    return properties, text


_FRONT_MATTER_REGEXP = re.compile(r"\A---\n(.+?)^---\n", flags=re.DOTALL | re.MULTILINE)
_FRONT_COMMENT_REGEXP = re.compile(r"\A<!--\n(.+?)^-->\n", flags=re.DOTALL | re.MULTILINE)


def extract_frontmatter_json(text: str) -> tuple[FrontMatterProperties | None, str]:
    "Extracts the front-matter from a Markdown document into a structured object."

    block, text = _extract_frontmatter_block(_FRONT_MATTER_REGEXP, text)
    if block is None:
        block, text = _extract_frontmatter_block(_FRONT_COMMENT_REGEXP, text)
    return block, text


def extract_frontmatter_object(tp: type[D], text: str) -> tuple[D | None, str]:
    properties, text = extract_frontmatter_json(text)

    value_object: D | None = None
    if properties is not None:
        value_object = json_to_object(tp, properties.data)

    return value_object, text
