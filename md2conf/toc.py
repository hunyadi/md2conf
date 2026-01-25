"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
from dataclasses import dataclass
from typing import Iterable, Iterator


@dataclass(eq=True)
class TableOfContentsEntry:
    """
    Represents a table of contents entry.

    :param level: The heading level assigned to the entry. Each entry can only contain children whose level is strictly greater than of its parent.
    :param text: The heading text.
    :param children: Direct descendants whose parent is this entry.
    """

    level: int
    text: str
    children: list["TableOfContentsEntry"]

    def __init__(self, level: int, text: str, children: list["TableOfContentsEntry"] | None = None) -> None:
        self.level = level
        self.text = text
        self.children = children or []


class TableOfContentsBuilder:
    """
    Builds a table of contents from Markdown headings.
    """

    _root: TableOfContentsEntry
    _stack: list[TableOfContentsEntry]

    def __init__(self) -> None:
        self._root = TableOfContentsEntry(0, "<root>")
        self._stack = [self._root]

    @property
    def tree(self) -> list[TableOfContentsEntry]:
        """
        Table of contents as a hierarchy of headings.
        """

        return self._root.children

    def add(self, level: int, text: str) -> None:
        """
        Adds a heading to the table of contents.

        :param level: Markdown heading level (e.g. `1` for first-level heading).
        :param text: Markdown heading text.
        """

        if level < 1:
            raise ValueError("expected: Markdown heading level >= 1")

        # remove any stack items deeper than the current level
        top = self._stack[-1]
        while top.level >= level:
            self._stack.pop()
            top = self._stack[-1]

        # add the new section under the current top level
        item = TableOfContentsEntry(level, text)
        top.children.append(item)

        # push new level onto the stack
        self._stack.append(item)

    def get_title(self) -> str | None:
        """
        Returns a proposed document title.

        The proposed title is text of the top-level heading if and only if that heading is unique.

        :returns: Title text, or `None` if no title can be inferred.
        """

        if len(self.tree) == 1:
            return self.tree[0].text
        else:
            return None


_FENCED_CODE_REGEXP = re.compile(r"^\s*(?:`{3,}|~{3,})", re.MULTILINE)
_ATX_HEADING_REGEXP = re.compile(r"^(#{1,6})\s+(.*?)$", re.MULTILINE)
_SETEXT_HEADING_REGEXP = re.compile(r"^(=+|-+)\s*?$", re.MULTILINE)


def headings(lines: Iterable[str]) -> Iterator[tuple[int, str]]:
    fence_marker: str | None = None
    heading_text: str | None = None

    for line in lines:
        # fenced code blocks
        fence_match = _FENCED_CODE_REGEXP.match(line)
        if fence_match:
            marker = fence_match.group()
            if fence_marker is None:
                fence_marker = marker
            elif marker == fence_marker:
                fence_marker = None
            heading_text = None
            continue

        if fence_marker is not None:
            heading_text = None
            continue

        # ATX headings
        atx = _ATX_HEADING_REGEXP.match(line)
        if atx is not None:
            level = len(atx.group(1))
            title = atx.group(2).rstrip().rstrip("#").rstrip()  # remove decorative text: `## Section 1.2 ##`
            yield level, title

            heading_text = None
            continue

        # Setext headings
        setext = _SETEXT_HEADING_REGEXP.match(line)
        if setext is not None and heading_text is not None:
            match setext.group(1)[0:1]:
                case "=":
                    level = 1
                case "-":
                    level = 2
                case _:
                    level = 0
            yield level, heading_text.rstrip()

            heading_text = None
            continue

        # candidate for Setext title
        heading_text = line


def unique_title(content: str) -> str | None:
    """
    Returns a proposed document title.

    The proposed title is text of the top-level heading if and only if that heading is unique.

    :returns: Title text, or `None` if no title can be inferred.
    """

    builder = TableOfContentsBuilder()
    for heading in headings(content.splitlines(keepends=True)):  # spellchecker:disable-line
        level, text = heading
        builder.add(level, text)
    return builder.get_title()
