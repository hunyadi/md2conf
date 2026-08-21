"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
from collections.abc import Iterator
from copy import deepcopy
from difflib import SequenceMatcher
from enum import Enum

from .csf import AC_ATTR, AC_ELEM, ElementType
from .xml import ElementComparator, ElementComparatorOptions, WrapVisitor, get_element_spans, unwrap_substitute

_COMMENT_MARKER = AC_ATTR("inline-comment-marker")


class MergeResult(Enum):
    # no comments need to be merged
    UNCHANGED = "unchanged"
    # all comments have been merged successfully
    MERGED = "merged"
    # some comments have been discarded due to incompatible content
    INCOMPATIBLE = "incompatible"


def _has_comment_as_descendant(node: ElementType) -> bool:
    "True if any descendant of the node contains an inline comment marker."

    return next(node.iter(_COMMENT_MARKER), None) is not None


def is_heading(node: ElementType) -> bool:
    "True if the node is a heading element (i.e. h1, h2, h3, h4, h5 or h6)."

    return node.tag in ("h1", "h2", "h3", "h4", "h5", "h6")


def mark_comment(node: ElementType, start: int, end: int, ref: str) -> bool:
    "Wraps the specified range of text in an inline comment marker."

    def create_comment_marker(text: str, tail: str | None) -> ElementType:
        "Creates an inline comment marker element with the specified text and tail."

        elem = AC_ELEM(
            "inline-comment-marker",
            {AC_ATTR("ref"): ref},
            text,
        )
        if tail:
            elem.tail = tail
        return elem

    return WrapVisitor(start, end, create_comment_marker).visit(node)


def remove_comments(node: ElementType) -> ElementType:
    "Removes any inline comment markers from the node, recursing to descendants."

    copy = deepcopy(node)
    unwrap_substitute(AC_ATTR("inline-comment-marker"), copy)
    return copy


def tokenize_string(s: str) -> list[str]:
    "Tokenizes a string into a list of lowercase words and punctuation marks."

    return re.findall(r"\w+|[^\w\s]", s.lower())


def tokenize_itertext(items: Iterator[str]) -> list[str]:
    "Tokenizes an iterable of strings (e.g. the result of `itertext()`), returning a list of tokens."

    tokens: list[str] = []
    for item in items:
        tokens.extend(tokenize_string(item))
    return tokens


class CommentMerger:
    comparator: ElementComparator

    def __init__(self, options: ElementComparatorOptions | None = None):
        self.comparator = ElementComparator(options)

    def merge(self, md_tree: ElementType, cf_tree: ElementType) -> MergeResult:
        """
        Merges inline comment markers from a Confluence tree into a tree generated from a Markdown source.

        :param md_tree: The root of the tree generated from a Markdown source file. May be updated.
        :param cf_tree: The root of the tree acquired from a Confluence page. Never mutated.
        :returns: Indicates whether comments were absent, merged, or incompatible.
        """

        cf_nodes = [
            (e, tokenize_itertext(e.itertext())) for e in cf_tree.iterdescendants("p", "h1", "h2", "h3", "h4", "h5", "h6") if _has_comment_as_descendant(e)
        ]
        if not cf_nodes:
            return MergeResult.UNCHANGED

        md_nodes = [(e, tokenize_itertext(e.itertext())) for e in md_tree.iterdescendants("p", "h1", "h2", "h3", "h4", "h5", "h6")]
        matches: list[tuple[ElementType, ElementType]] = []
        for cf_node, cf_tokens in cf_nodes:
            matcher = SequenceMatcher(None)
            matcher.set_seq2(cf_tokens)
            best_fit = 0.8
            best_node: ElementType | None = None
            for md_node, md_tokens in md_nodes:
                if is_heading(md_node) != is_heading(cf_node):
                    continue

                matcher.set_seq1(md_tokens)
                current_fit = matcher.ratio()
                if current_fit > best_fit:
                    best_fit = current_fit
                    best_node = md_node
            if best_node is not None:
                matches.append((cf_node, best_node))

        status = MergeResult.INCOMPATIBLE if len(cf_nodes) > len(matches) else MergeResult.MERGED

        for cf_node, md_node in matches:
            if self.comparator.is_equal(md_node, remove_comments(cf_node)):
                md_node.text = cf_node.text
                md_node[:] = [deepcopy(n) for n in cf_node]
                continue

            md_text = "".join(md_node.itertext())
            cf_text = "".join(cf_node.itertext())
            spans = get_element_spans(_COMMENT_MARKER, cf_node)
            blocks = SequenceMatcher(None, md_text, cf_text).get_matching_blocks()
            for span in spans:
                ref = span.element.get(AC_ATTR("ref"))
                if ref is None:
                    continue
                for i, j, n in blocks:
                    if span.start >= j and span.end <= j + n:
                        mark_comment(md_node, i + span.start - j, i + span.end - j, ref)
                        break
                else:
                    status = MergeResult.INCOMPATIBLE

        return status


def merge_comments(md_tree: ElementType, cf_tree: ElementType, options: ElementComparatorOptions | None = None) -> MergeResult:
    """
    Merges inline comment markers from a Confluence tree into a tree generated from a Markdown source.

    The Markdown source is edited by users, and produces a Confluence Storage Format XML tree as part of
    the synchronization procedure. The generated XML never contains inline comment markers.

    The Confluence tree is acquired from a page and may contain inline comment markers, added by users in
    the Confluence web interface interactively.

    The objective of this function is to merge the inline comment markers from the Confluence tree into
    the Markdown tree, so that the Markdown tree can be published to Confluence while losing as few inline comment
    markers as possible.

    First, the function pairs each paragraph or heading with inline comment markers present in the Confluence tree with
    their best match in the Markdown tree. Second, the function merges the inline comment markers in each matched node
    using :class:`difflib.SequenceMatcher`.

    :param md_tree: The root of the tree generated from a Markdown source file. May be updated.
    :param cf_tree: The root of the tree acquired from a Confluence page. Never mutated.
    :param options: Options to control how XML elements are compared.
    :returns: Indicates whether comments were absent, merged, or incompatible.
    """

    return CommentMerger(options).merge(md_tree, cf_tree)
