"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest

from md2conf.comment import MergeResult, mark_comment, merge_comments
from md2conf.converter import get_orderless_elements, get_volatile_attributes, get_volatile_elements
from md2conf.csf import AC_ATTR, ElementType, elements_from_string, elements_to_string
from md2conf.xml import ElementComparatorOptions, ElementSpan, get_element_spans, is_xml_equal


class TestComment(unittest.TestCase):
    def assertXmlEqualString(self, actual_tree: ElementType, expected: str) -> None:
        expected_tree = elements_from_string(expected)
        if not is_xml_equal(actual_tree, expected_tree, ElementComparatorOptions()):
            actual_xml = elements_to_string(actual_tree)
            expected_xml = elements_to_string(expected_tree)
            self.assertEqual(actual_xml, expected_xml)

    def test_element_spans(self) -> None:
        root = elements_from_string("Text <span>with</span> <strong>bold</strong> and <em>italic</em>. <strong>No <span>comments</span></strong>")
        elements = list(root.iter("strong"))
        spans = get_element_spans("strong", root)
        self.assertEqual(spans, [ElementSpan(elements[0], 10, 14), ElementSpan(elements[1], 27, 38)])

    def test_mark_comment(self) -> None:
        root = elements_from_string("Text <span>with</span> <strong>bold</strong>.")
        self.assertTrue(mark_comment(root, 2, 3, "ID"))
        self.assertXmlEqualString(root, 'Te<ac:inline-comment-marker ac:ref="ID">x</ac:inline-comment-marker>t <span>with</span> <strong>bold</strong>.')

        root = elements_from_string("Text <span>with</span> <strong>bold</strong>.")
        self.assertTrue(mark_comment(root, 2, 7, "ID"))
        self.assertXmlEqualString(
            root,
            'Te<ac:inline-comment-marker ac:ref="ID">xt </ac:inline-comment-marker>'
            '<span><ac:inline-comment-marker ac:ref="ID">wi</ac:inline-comment-marker>th</span> <strong>bold</strong>.',
        )

        root = elements_from_string("Text <span>with</span> <strong>bold</strong>.")
        self.assertTrue(mark_comment(root, 2, 12, "ID"))
        self.assertXmlEqualString(
            root,
            'Te<ac:inline-comment-marker ac:ref="ID">xt </ac:inline-comment-marker>'
            '<span><ac:inline-comment-marker ac:ref="ID">with</ac:inline-comment-marker></span>'
            '<ac:inline-comment-marker ac:ref="ID"> </ac:inline-comment-marker>'
            '<strong><ac:inline-comment-marker ac:ref="ID">bo</ac:inline-comment-marker>ld</strong>.',
        )

    def test_across_inline_formatting(self) -> None:
        md_tree = elements_from_string("<p>Text with <strong>bold</strong>, <em>italic</em>.</p>")
        cf_tree = elements_from_string(
            '<p><ac:inline-comment-marker ac:ref="ID">Text with </ac:inline-comment-marker>'
            '<strong><ac:inline-comment-marker ac:ref="ID">bold</ac:inline-comment-marker></strong>'
            '<ac:inline-comment-marker ac:ref="ID">, </ac:inline-comment-marker>'
            '<em><ac:inline-comment-marker ac:ref="ID">italic</ac:inline-comment-marker></em>'
            '<ac:inline-comment-marker ac:ref="ID">.</ac:inline-comment-marker></p>'
        )

        self.assertEqual(merge_comments(md_tree, cf_tree), MergeResult.MERGED)

        self.assertXmlEqualString(
            md_tree,
            '<p><ac:inline-comment-marker ac:ref="ID">Text with </ac:inline-comment-marker>'
            '<strong><ac:inline-comment-marker ac:ref="ID">bold</ac:inline-comment-marker></strong>'
            '<ac:inline-comment-marker ac:ref="ID">, </ac:inline-comment-marker>'
            '<em><ac:inline-comment-marker ac:ref="ID">italic</ac:inline-comment-marker></em>'
            '<ac:inline-comment-marker ac:ref="ID">.</ac:inline-comment-marker></p>',
        )

        markers = list(md_tree.iter(AC_ATTR("inline-comment-marker")))
        self.assertEqual([marker.get(AC_ATTR("ref")) for marker in markers], ["ID"] * 5)

    def test_unchanged_tree(self) -> None:
        md_tree = elements_from_string("<p>Status: <b>Unchanged</b></p>")
        cf_tree = elements_from_string("<p>\nStatus: <b>Unchanged</b>\n</p>")

        self.assertEqual(merge_comments(md_tree, cf_tree), MergeResult.UNCHANGED)
        self.assertXmlEqualString(md_tree, "<p>Status: <b>Unchanged</b></p>")

    def test_incompatible_subtree(self) -> None:
        md_tree = elements_from_string("<article><p>Text originating from Markdown</p><p>Unchanged</p></article>")
        cf_tree = elements_from_string(
            '<article><p><ac:inline-comment-marker ac:ref="ID1">Text updated in Confluence</ac:inline-comment-marker></p>'
            '<p><ac:inline-comment-marker ac:ref="ID2">Unchanged</ac:inline-comment-marker></p></article>'
        )
        self.assertEqual(merge_comments(md_tree, cf_tree), MergeResult.INCOMPATIBLE)
        self.assertXmlEqualString(
            md_tree,
            '<article><p>Text originating from Markdown</p><p><ac:inline-comment-marker ac:ref="ID2">Unchanged</ac:inline-comment-marker></p></article>',
        )

    def test_updated_text(self) -> None:
        md_tree = elements_from_string("<p>Longer sample text from Markdown <b>unchanged</b></p>")
        cf_tree = elements_from_string(
            '<p>Longer sample text from Confluence <b><ac:inline-comment-marker ac:ref="ID">unchanged</ac:inline-comment-marker></b></p>'
        )

        self.assertEqual(merge_comments(md_tree, cf_tree), MergeResult.MERGED)
        self.assertXmlEqualString(
            md_tree, '<p>Longer sample text from Markdown <b><ac:inline-comment-marker ac:ref="ID">unchanged</ac:inline-comment-marker></b></p>'
        )

    def test_around_inline_macro(self) -> None:
        md_tree = elements_from_string(
            '<p>Status <ac:structured-macro ac:name="status"><ac:parameter ac:name="title">gray</ac:parameter></ac:structured-macro></p>'
        )
        cf_tree = elements_from_string(
            '<p><ac:inline-comment-marker ac:ref="ID">Status </ac:inline-comment-marker>'
            '<ac:inline-comment-marker ac:ref="ID">'
            '<ac:structured-macro ac:name="status"><ac:parameter ac:name="title">gray</ac:parameter></ac:structured-macro>'
            "</ac:inline-comment-marker></p>"
        )

        self.assertEqual(merge_comments(md_tree, cf_tree), MergeResult.MERGED)

        self.assertXmlEqualString(
            md_tree,
            '<p><ac:inline-comment-marker ac:ref="ID">Status </ac:inline-comment-marker>'
            '<ac:inline-comment-marker ac:ref="ID"><ac:structured-macro ac:name="status">'
            '<ac:parameter ac:name="title">gray</ac:parameter></ac:structured-macro></ac:inline-comment-marker></p>',
        )
        self.assertXmlEqualString(
            cf_tree,
            '<p><ac:inline-comment-marker ac:ref="ID">Status </ac:inline-comment-marker>'
            '<ac:inline-comment-marker ac:ref="ID"><ac:structured-macro ac:name="status">'
            '<ac:parameter ac:name="title">gray</ac:parameter></ac:structured-macro></ac:inline-comment-marker></p>',
        )

    def test_skip_attributes(self) -> None:
        md_tree = elements_from_string(
            '<ac:structured-macro ac:name="info" ac:schema-version="1">'
            "<ac:rich-text-body><p>This page has been generated with md2conf.</p></ac:rich-text-body>"
            "</ac:structured-macro>"
            "<p>First paragraph.</p>"
            "<p>Second paragraph.</p>"
        )
        cf_tree = elements_from_string(
            '<ac:structured-macro ac:name="info" ac:schema-version="1" ac:macro-id="00000000-0000-0000-0000-000000000000">'
            "<ac:rich-text-body><p>This page has been generated with md2conf.</p></ac:rich-text-body>"
            "</ac:structured-macro>"
            "<p>First paragraph.</p>"
            '<p>Second <ac:inline-comment-marker ac:ref="01234567-89ab-cdef-0123-456789abcdef">paragraph</ac:inline-comment-marker>.</p>'
        )
        merged = (
            '<ac:structured-macro ac:name="info" ac:schema-version="1">'
            "<ac:rich-text-body><p>This page has been generated with md2conf.</p></ac:rich-text-body>"
            "</ac:structured-macro>"
            "<p>First paragraph.</p>"
            '<p>Second <ac:inline-comment-marker ac:ref="01234567-89ab-cdef-0123-456789abcdef">paragraph</ac:inline-comment-marker>.</p>'
        )
        self.assertEqual(
            merge_comments(
                md_tree,
                cf_tree,
                ElementComparatorOptions(
                    skip_attributes=get_volatile_attributes(),
                    skip_elements=get_volatile_elements(),
                    orderless_elements=get_orderless_elements(),
                ),
            ),
            MergeResult.MERGED,
        )
        self.assertXmlEqualString(md_tree, merged)

    def test_insert_paragraph(self) -> None:
        md_tree = elements_from_string(
            "<p>First paragraph.</p>"
            "<p>Second paragraph.</p>"
            "<p>Third paragraph.</p>"
            "<p>Fourth paragraph.</p>"
            "<p>Fifth <i>paragraph</i>.</p>"
            "<p>Sixth paragraph.</p>"
        )
        cf_tree = elements_from_string(
            '<p>Second <ac:inline-comment-marker ac:ref="1">paragraph</ac:inline-comment-marker>.</p>'
            '<p><ac:inline-comment-marker ac:ref="2">Third paragraph.</ac:inline-comment-marker></p>'
            '<p>Fifth <i><ac:inline-comment-marker ac:ref="3">paragraph</ac:inline-comment-marker></i>.</p>'
        )
        merged = (
            "<p>First paragraph.</p>"
            '<p>Second <ac:inline-comment-marker ac:ref="1">paragraph</ac:inline-comment-marker>.</p>'
            '<p><ac:inline-comment-marker ac:ref="2">Third paragraph.</ac:inline-comment-marker></p>'
            "<p>Fourth paragraph.</p>"
            '<p>Fifth <i><ac:inline-comment-marker ac:ref="3">paragraph</ac:inline-comment-marker></i>.</p>'
            "<p>Sixth paragraph.</p>"
        )
        self.assertEqual(
            merge_comments(
                md_tree,
                cf_tree,
                ElementComparatorOptions(
                    skip_attributes=get_volatile_attributes(),
                    skip_elements=get_volatile_elements(),
                    orderless_elements=get_orderless_elements(),
                ),
            ),
            MergeResult.MERGED,
        )
        self.assertXmlEqualString(md_tree, merged)

    def test_prefers_best_match(self) -> None:
        md_tree = elements_from_string("<article><p><span>P</span></p><p><b>M</b></p><p><span>P</span><em>Q</em><i>R</i></p></article>")
        cf_tree = elements_from_string(
            "<article>"
            "<p><span>P</span><em>Q</em><i>R</i></p>"
            '<p><b><ac:inline-comment-marker ac:ref="ID1">M</ac:inline-comment-marker></b></p>'
            '<p><span><ac:inline-comment-marker ac:ref="ID2">P</ac:inline-comment-marker></span></p>'
            "</article>"
        )

        self.assertEqual(merge_comments(md_tree, cf_tree), MergeResult.MERGED)
        self.assertXmlEqualString(
            md_tree,
            "<article>"
            '<p><span><ac:inline-comment-marker ac:ref="ID2">P</ac:inline-comment-marker></span></p>'
            '<p><b><ac:inline-comment-marker ac:ref="ID1">M</ac:inline-comment-marker></b></p>'
            "<p><span>P</span><em>Q</em><i>R</i></p>"
            "</article>",
        )


if __name__ == "__main__":
    unittest.main()
