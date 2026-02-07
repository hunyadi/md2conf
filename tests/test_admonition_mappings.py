"""
Unit tests for admonition type mappings.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from pathlib import Path

from md2conf.collection import ConfluencePageCollection
from md2conf.converter import ConfluenceDocument
from md2conf.metadata import ConfluenceSiteMetadata
from md2conf.options import ConverterOptions, DocumentOptions


class TestAdmonitionMappings(unittest.TestCase):
    """Test that new admonition types map correctly to Confluence macros."""

    def setUp(self):
        self.test_dir = Path(__file__).parent
        self.source_dir = self.test_dir / "source"
        self.site_metadata = ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="TEST")
        self.page_metadata = ConfluencePageCollection()

    def test_abstract_maps_to_note(self):
        """Test that 'abstract' admonition maps to 'note' macro."""
        md_content = '!!! abstract "Summary"\n    This is an abstract.'
        self._assert_admonition_maps_to_macro(md_content, "note")

    def test_bug_maps_to_warning(self):
        """Test that 'bug' admonition maps to 'warning' macro."""
        md_content = '!!! bug "Bug Report"\n    This is a bug.'
        self._assert_admonition_maps_to_macro(md_content, "warning")

    def test_example_maps_to_info(self):
        """Test that 'example' admonition maps to 'info' macro."""
        md_content = '!!! example "Example"\n    This is an example.'
        self._assert_admonition_maps_to_macro(md_content, "info")

    def test_failure_maps_to_warning(self):
        """Test that 'failure' admonition maps to 'warning' macro."""
        md_content = '!!! failure "Failure"\n    This failed.'
        self._assert_admonition_maps_to_macro(md_content, "warning")

    def test_question_maps_to_info(self):
        """Test that 'question' admonition maps to 'info' macro."""
        md_content = '!!! question "Question"\n    This is a question.'
        self._assert_admonition_maps_to_macro(md_content, "info")

    def test_quote_maps_to_info(self):
        """Test that 'quote' admonition maps to 'info' macro."""
        md_content = '!!! quote "Quote"\n    This is a quote.'
        self._assert_admonition_maps_to_macro(md_content, "info")

    def test_success_maps_to_info(self):
        """Test that 'success' admonition maps to 'info' macro."""
        md_content = '!!! success "Success"\n    This succeeded.'
        self._assert_admonition_maps_to_macro(md_content, "info")

    def _assert_admonition_maps_to_macro(self, md_content: str, expected_macro: str):
        """Helper to test admonition mapping."""
        # Create temporary markdown file with page ID
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(f"<!-- confluence-page-id: 123456 -->\n# Test\n\n{md_content}")
            temp_path = Path(f.name)

        try:
            _, doc = ConfluenceDocument.create(
                temp_path,
                DocumentOptions(converter=ConverterOptions(use_panel=False)),
                temp_path.parent,
                self.site_metadata,
                self.page_metadata,
            )
            xhtml = doc.xhtml()
            self.assertIn(f'ac:name="{expected_macro}"', xhtml)
        finally:
            temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
