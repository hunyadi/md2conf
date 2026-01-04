"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest
from typing import Iterable

import lxml.etree as ET

from md2conf.csf import elements_from_string, normalize_inline
from md2conf.xml import is_xml_equal, unwrap_substitute
from tests.utility import TypedTestCase

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestXml(TypedTestCase):
    def assertXmlEqual(
        self,
        tree1: ElementType,
        tree2: ElementType,
        *,
        skip_attributes: Iterable[str] | None = None,
        skip_elements: Iterable[str] | None = None,
        msg: str | None = None,
    ) -> None:
        if not is_xml_equal(tree1, tree2, skip_attributes=skip_attributes, skip_elements=skip_elements):
            xml1 = ET.tostring(tree1, encoding="utf8", method="xml").decode("utf8")
            xml2 = ET.tostring(tree2, encoding="utf8", method="xml").decode("utf8")
            self.assertMultiLineEqual(xml1, xml2, msg)

    def assertXmlNotEqual(self, tree1: ElementType, tree2: ElementType, msg: str | None = None) -> None:
        if is_xml_equal(tree1, tree2):
            xml1 = ET.tostring(tree1, encoding="utf8", method="xml").decode("utf8")
            xml2 = ET.tostring(tree2, encoding="utf8", method="xml").decode("utf8")
            self.assertMultiLineEqual(xml1, xml2)

    def test_xml_entities(self) -> None:
        tree1 = ET.fromstring('<body><p>to be, or "not" to be 😉</p></body>')
        tree2 = ET.fromstring("<body><p>to be, or &quot;not&quot; to be &#128521;</p></body>")
        self.assertXmlEqual(tree1, tree2)

    def test_xml_skip_attribute(self) -> None:
        tree1 = ET.fromstring('<body><p class="paragraph" data-skip="..." style="display: none;">to be, or not to be</p></body>')
        tree2 = ET.fromstring('<body><p style="display: none;" class="paragraph">to be, or not to be</p></body>')
        self.assertXmlNotEqual(tree1, tree2)
        self.assertXmlEqual(tree1, tree2, skip_attributes={"data-skip"})

    def test_normalize_inline(self) -> None:
        tree1 = ET.fromstring("<li>  </li>")
        tree2 = ET.fromstring("<li></li>")
        normalize_inline(tree1)
        self.assertXmlEqual(tree1, tree2)

        tree1 = ET.fromstring("<li>to be, or not to be</li>")
        tree2 = ET.fromstring("<li><p>to be, or not to be</p></li>")
        normalize_inline(tree1)
        self.assertXmlEqual(tree1, tree2)

        tree1 = ET.fromstring("<li>to <em>be</em>, or not to <em>be</em></li>")
        tree2 = ET.fromstring("<li><p>to <em>be</em>, or not to <em>be</em></p></li>")
        normalize_inline(tree1)
        self.assertXmlEqual(tree1, tree2)

        tree1 = ET.fromstring("<li>to be, <ol/> not to be</li>")
        tree2 = ET.fromstring("<li><p>to be,</p><ol/><p>not to be</p></li>")
        normalize_inline(tree1)
        self.assertXmlEqual(tree1, tree2)

        tree1 = ET.fromstring("<li>to <em>be</em>, <ol/> not to <em>be</em></li>")
        tree2 = ET.fromstring("<li><p>to <em>be</em>,</p><ol/><p>not to <em>be</em></p></li>")
        normalize_inline(tree1)
        self.assertXmlEqual(tree1, tree2)

        tree1 = ET.fromstring("<li>  to <em>be</em>, <ol/> not to <em>be</em>  </li>")
        tree2 = ET.fromstring("<li><p>to <em>be</em>,</p><ol/><p>not to <em>be</em></p></li>")
        normalize_inline(tree1)
        self.assertXmlEqual(tree1, tree2)

        tree1 = ET.fromstring("<li>  to <em>be</em>, <pre>  or  </pre> not to <em>be</em>  </li>")
        tree2 = ET.fromstring("<li><p>to <em>be</em>,</p><pre>  or  </pre><p>not to <em>be</em></p></li>")
        normalize_inline(tree1)
        self.assertXmlEqual(tree1, tree2)

    def test_unwrap(self) -> None:
        xml1 = (
            '<root xmlns:ac="http://atlassian.com/content"><p>'
            "Lorem <mark>ipsum</mark> dolor sit amet, "
            "<mark><em>consectetur</em> adipiscing elit</mark>, "
            "sed do eiusmod tempor incididunt ut <mark><b>labore</b> et <b>dolore</b></mark> "
            "<mark>magna <em>aliqua</em></mark>."
            "</p></root>"
        )
        xml2 = (
            '<root xmlns:ac="http://atlassian.com/content"><p>'
            "Lorem ipsum dolor sit amet, <em>consectetur</em> adipiscing elit, "
            "sed do eiusmod tempor incididunt ut <b>labore</b> et <b>dolore</b> magna <em>aliqua</em>."
            "</p></root>"
        )
        tree1 = elements_from_string(xml1)
        unwrap_substitute("mark", tree1)
        tree2 = elements_from_string(xml2)
        self.assertXmlEqual(tree1, tree2)


if __name__ == "__main__":
    unittest.main()
