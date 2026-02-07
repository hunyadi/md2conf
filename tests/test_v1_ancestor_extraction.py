"""
Unit tests for v1 API ancestor extraction and parent ID handling.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from unittest.mock import MagicMock

from md2conf.api import ConfluenceSession, ConfluenceVersion


class TestV1AncestorExtraction(unittest.TestCase):
    """Test extraction of parent page ID from ancestors array in v1 API."""

    def setUp(self):
        self.mock_session = MagicMock()
        self.session = ConfluenceSession(
            self.mock_session,
            api_url="https://example.com",
            domain="example.com",
            base_path="/wiki/",
            space_key="TEST",
            api_version=ConfluenceVersion.VERSION_1,
        )

    def test_extract_parent_from_single_ancestor(self):
        """Test extracting parent ID when there's one ancestor."""
        data = {"ancestors": [{"id": "parent-123"}]}
        parent_id = self.session._extract_parent_id_from_ancestors_v1(data)
        self.assertEqual(parent_id, "parent-123")

    def test_extract_parent_from_multiple_ancestors(self):
        """Test extracting parent ID when there are multiple ancestors."""
        data = {"ancestors": [{"id": "grandparent-456"}, {"id": "parent-123"}]}
        # Should return the last ancestor (immediate parent)
        parent_id = self.session._extract_parent_id_from_ancestors_v1(data)
        self.assertEqual(parent_id, "parent-123")

    def test_extract_parent_with_no_ancestors(self):
        """Test extracting parent ID when there are no ancestors."""
        data = {"ancestors": []}
        parent_id = self.session._extract_parent_id_from_ancestors_v1(data)
        self.assertIsNone(parent_id)

    def test_extract_parent_with_missing_ancestors_key(self):
        """Test extracting parent ID when ancestors key is missing."""
        data = {}
        parent_id = self.session._extract_parent_id_from_ancestors_v1(data)
        self.assertIsNone(parent_id)


class TestV1PageParsing(unittest.TestCase):
    """Test parsing of v1 API page responses."""

    def setUp(self):
        self.mock_session = MagicMock()
        self.session = ConfluenceSession(
            self.mock_session,
            api_url="https://example.com",
            domain="example.com",
            base_path="/wiki/",
            space_key="TEST",
            api_version=ConfluenceVersion.VERSION_1,
        )

    def test_parse_page_v1_with_parent(self):
        """Test parsing v1 page response with parent."""
        data = {
            "id": "123",
            "status": "current",
            "title": "Test Page",
            "space": {"key": "TEST"},
            "version": {"number": 1, "minorEdit": False},
            "body": {"storage": {"value": "<p>Content</p>", "representation": "storage"}},
            "ancestors": [{"id": "parent-456"}],
        }

        page = self.session._parse_page_v1(data)

        self.assertEqual(page.id, "123")
        self.assertEqual(page.title, "Test Page")
        self.assertEqual(page.spaceId, "TEST")  # v1 stores space KEY in spaceId
        self.assertEqual(page.parentId, "parent-456")
        self.assertEqual(page.version.number, 1)

    def test_parse_page_v1_without_parent(self):
        """Test parsing v1 page response without parent."""
        data = {
            "id": "123",
            "status": "current",
            "title": "Root Page",
            "space": {"key": "TEST"},
            "version": {"number": 1, "minorEdit": False},
            "body": {"storage": {"value": "<p>Content</p>", "representation": "storage"}},
            "ancestors": [],
        }

        page = self.session._parse_page_v1(data)

        self.assertEqual(page.id, "123")
        self.assertIsNone(page.parentId)
        self.assertIsNone(page.parentType)


if __name__ == "__main__":
    unittest.main()
