"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
from io import StringIO
from pathlib import Path
from typing import TextIO

from lxml.etree import CDATA

from md2conf.compatibility import override
from md2conf.csf import AC_ATTR, AC_ELEM, ElementType
from md2conf.formatting import ImageAttributes
from md2conf.options import MarketplaceExtension

_RELATION_REGEXP: re.Pattern[str] = re.compile(r"^\s*(?P<parent>\w+)\s*<\|--\s*(?P<child>\w+)\s*$")


def parse_mermaid_class_diagram(diagram: str) -> tuple[list[str], dict[str, list[str]]]:
    if not diagram.startswith("classDiagram"):
        raise ValueError("expected: a class diagram")

    relations: dict[str, list[str]] = {}
    parents: dict[str, str] = {}

    for line in diagram.splitlines():
        if match := _RELATION_REGEXP.match(line):
            parent: str = match.group("parent")
            child: str = match.group("child")

            relations.setdefault(parent, []).append(child)
            parents[child] = parent

            # ensure all nodes exist in children map
            relations.setdefault(child, [])

    roots = [node for node in relations if node not in parents]
    return roots, relations


class MermaidTreeRenderer:
    target: TextIO | None

    def __init__(self, target: TextIO | None) -> None:
        self.target = target

    def _print_tree(self, node: str, children: dict[str, list[str]], prefix: str, is_last: bool) -> None:
        connector = "└── " if is_last else "├── "
        print(prefix + connector + node, file=self.target)

        child_connector = "    " if is_last else "│   "
        child_prefix = prefix + child_connector

        child_list = children[node]
        for i, child in enumerate(child_list, start=1):
            self._print_tree(child, children, child_prefix, i == len(child_list))

    def print_tree(self, diagram: str) -> None:
        roots, children = parse_mermaid_class_diagram(diagram)

        for root in roots:
            print(root, file=self.target)

            root_children = children[root]
            for i, child in enumerate(root_children, start=1):
                self._print_tree(child, children, "", i == len(root_children))


def render_mermaid_tree(diagram: str) -> str:
    with StringIO() as buf:
        MermaidTreeRenderer(buf).print_tree(diagram)
        return buf.getvalue().strip()


class MermaidTreeExtension(MarketplaceExtension):
    @override
    def matches_image(self, absolute_path: Path) -> bool:
        return False

    @override
    def matches_fenced(self, language: str, content: str) -> bool:
        return language == "mermaid" and content.startswith("classDiagram")

    @override
    def transform_image(self, absolute_path: Path, attrs: ImageAttributes) -> ElementType:
        raise NotImplementedError()

    @override
    def transform_fenced(self, content: str) -> ElementType:
        return AC_ELEM(
            "structured-macro",
            {
                AC_ATTR("name"): "code",
                AC_ATTR("schema-version"): "1",
            },
            AC_ELEM(
                "parameter",
                {AC_ATTR("name"): "language"},
                "mermaid",
            ),
            AC_ELEM("plain-text-body", CDATA(render_mermaid_tree(content))),
        )
