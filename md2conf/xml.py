"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from typing import Iterable

import lxml.etree as ET

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]
AttribType = ET._Attrib  # pyright: ignore[reportPrivateUsage]


def _attrs_equal_excluding(attrs1: AttribType, attrs2: AttribType, exclude: set[str]) -> bool:
    """
    Compares two dictionary objects, excluding keys in the skip set.

    :param exclude: Attributes to exclude, in `{namespace}name` notation.
    """

    # create key sets to compare, excluding keys to be skipped
    keys1 = {k for k in attrs1.keys() if k not in exclude}
    keys2 = {k for k in attrs2.keys() if k not in exclude}
    if keys1 != keys2:
        return False

    # compare values for each key
    for key in keys1:
        if attrs1.get(key) != attrs2.get(key):
            return False

    return True


class ElementComparator:
    skip_attributes: set[str]
    skip_elements: set[str]

    def __init__(self, *, skip_attributes: Iterable[str] | None = None, skip_elements: Iterable[str] | None = None):
        """
        Initializes a new element tree comparator.

        :param skip_attributes: Attributes to exclude, in `{namespace}name` notation.
        :param skip_elements: Elements to exclude, in `{namespace}name` notation.
        """

        self.skip_attributes = set(skip_attributes) if skip_attributes else set()
        self.skip_elements = set(skip_elements) if skip_elements else set()

    def is_equal(self, e1: ElementType, e2: ElementType) -> bool:
        """
        Recursively check if two XML elements are equal.
        """

        if e1.tag != e2.tag:
            return False

        # compare tail first, which is outside of element
        e1_tail = e1.tail.strip() if e1.tail else ""
        e2_tail = e2.tail.strip() if e2.tail else ""
        if e1_tail != e2_tail:
            return False

        # skip element (and content) if on ignore list
        if e1.tag in self.skip_elements:
            return True

        # compare text second, which is encapsulated by element
        e1_text = e1.text.strip() if e1.text else ""
        e2_text = e2.text.strip() if e2.text else ""
        if e1_text != e2_text:
            return False

        # compare attributes, disregarding definition order
        if not _attrs_equal_excluding(e1.attrib, e2.attrib, self.skip_attributes):
            return False

        # compare children recursively
        if len(e1) != len(e2):
            return False
        return all(self.is_equal(c1, c2) for c1, c2 in zip(e1, e2, strict=True))


def is_xml_equal(tree1: ElementType, tree2: ElementType, *, skip_attributes: Iterable[str] | None = None, skip_elements: Iterable[str] | None = None) -> bool:
    """
    Compare two XML documents for equivalence, ignoring leading/trailing whitespace differences and attribute definition order.

    Elements may be excluded, in which case they compare equal to any element of the same type that has the same tail text.

    :param tree1: XML document as an element tree.
    :param tree2: XML document as an element tree.
    :param skip_attributes: Attributes to exclude, in `{namespace}name` notation.
    :param skip_elements: Elements to exclude, in `{namespace}name` notation.
    :returns: True if equivalent, False otherwise.
    """

    return ElementComparator(skip_attributes=skip_attributes, skip_elements=skip_elements).is_equal(tree1, tree2)


def element_to_text(node: ElementType) -> str:
    "Returns all text contained in an element as a concatenated string."

    return "".join(node.itertext()).strip()


def unwrap_substitute(name: str, root: ElementType) -> None:
    """
    Substitutes all occurrences of an element with its contents.

    :param name: Element tag name to find and replace.
    :param root: Top-most element at which to start.
    """

    for node in root.iterdescendants(name):
        if node.text:
            # append first piece of text in this element at the end of previous sibling, or text contained by parent
            if (prev_node := node.getprevious()) is not None:
                prev_node.tail = (prev_node.tail or "") + node.text
            elif (parent_node := node.getparent()) is not None:  # always true except for root
                parent_node.text = (parent_node.text or "") + node.text
            else:
                raise NotImplementedError("must always have a previous sibling or a parent")
        if node.tail:
            if len(node) > 0:
                # append text immediately following the closing tag of this element to the last child element of this element
                last_node = node[-1]
                last_node.tail = (last_node.tail or "") + node.tail
            else:  # node has no child elements, only text
                if (prev_node := node.getprevious()) is not None:
                    prev_node.tail = (prev_node.tail or "") + node.tail
                elif (parent_node := node.getparent()) is not None:  # always true except for root
                    parent_node.text = (parent_node.text or "") + node.tail
                else:
                    raise NotImplementedError("must always have a previous sibling or a parent")
        for child in node.iterchildren(reversed=True):
            node.addnext(child)
        if (parent_node := node.getparent()) is not None:  # always true except for root
            parent_node.remove(node)
