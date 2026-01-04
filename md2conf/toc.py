"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass


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
