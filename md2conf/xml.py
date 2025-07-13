from typing import Iterable, Optional, Union

import lxml.etree as ET


def _attrs_equal_excluding(attrs1: ET._Attrib, attrs2: ET._Attrib, exclude: set[Union[str, ET.QName]]) -> bool:
    """
    Compares two dictionary objects, excluding keys in the skip set.
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
    skip_attributes: set[Union[str, ET.QName]]

    def __init__(self, *, skip_attributes: Optional[Iterable[Union[str, ET.QName]]] = None):
        self.skip_attributes = set(skip_attributes) if skip_attributes else set()

    def is_equal(self, e1: ET._Element, e2: ET._Element) -> bool:
        """
        Recursively check if two XML elements are equal.
        """

        if e1.tag != e2.tag:
            return False

        e1_text = e1.text.strip() if e1.text else ""
        e2_text = e2.text.strip() if e2.text else ""
        if e1_text != e2_text:
            return False

        e1_tail = e1.tail.strip() if e1.tail else ""
        e2_tail = e2.tail.strip() if e2.tail else ""
        if e1_tail != e2_tail:
            return False

        if not _attrs_equal_excluding(e1.attrib, e2.attrib, self.skip_attributes):
            return False
        if len(e1) != len(e2):
            return False
        return all(self.is_equal(c1, c2) for c1, c2 in zip(e1, e2))


def is_xml_equal(
    tree1: ET._Element,
    tree2: ET._Element,
    *,
    skip_attributes: Optional[Iterable[Union[str, ET.QName]]] = None,
) -> bool:
    """
    Compare two XML documents for equivalence, ignoring leading/trailing whitespace differences and attribute definition order.

    :param tree1: XML document as an element tree.
    :param tree2: XML document as an element tree.
    :returns: True if equivalent, False otherwise.
    """

    return ElementComparator(skip_attributes=skip_attributes).is_equal(tree1, tree2)
