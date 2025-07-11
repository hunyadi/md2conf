import xml.etree.ElementTree as ET


def normalize_element(elem: ET.Element) -> None:
    """
    Recursively normalize an XML element by stripping whitespace and sorting attributes/children.
    """

    # strip text and tail
    elem.text = elem.text.strip() if elem.text else ""
    elem.tail = elem.tail.strip() if elem.tail else ""

    # sort attributes (for consistent order)
    elem.attrib = dict(sorted(elem.attrib.items()))

    # recursively normalize children
    for child in elem:
        normalize_element(child)


def elements_equal(e1: ET.Element, e2: ET.Element) -> bool:
    """
    Recursively check if two XML elements are equal.
    """

    if e1.tag != e2.tag:
        return False
    if e1.text != e2.text:
        return False
    if e1.tail != e2.tail:
        return False
    if e1.attrib != e2.attrib:
        return False
    if len(e1) != len(e2):
        return False
    return all(elements_equal(c1, c2) for c1, c2 in zip(e1, e2))


def compare_xml(tree1: ET.Element, tree2: ET.Element) -> bool:
    """
    Compare two XML documents for equivalence, ignoring whitespace differences.

    :param tree1: XML document as an element tree.
    :param tree2: XML document as an element tree.
    :returns: True if equivalent, False otherwise.
    """

    normalize_element(tree1)
    normalize_element(tree2)
    return elements_equal(tree1, tree2)
