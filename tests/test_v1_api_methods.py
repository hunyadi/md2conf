"""
Unit tests for Confluence REST API v1 method implementations.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from unittest.mock import MagicMock, patch

from md2conf.api import (
    ConfluenceError,
    ConfluenceSession,
    ConfluenceVersion,
)


class TestV1PageMethods(unittest.TestCase):
    """Test v1 API page operations."""

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

    def test_get_page_routes_to_v1(self):
        """Test get_page routes to v1 implementation."""
        self.session._get_page_v1 = MagicMock()
        self.session.get_page("123")
        self.session._get_page_v1.assert_called_once_with("123", retries=3, retry_delay=1.0)

    def test_create_page_routes_to_v1(self):
        """Test create_page routes to v1 implementation."""
        self.session._create_page_v1 = MagicMock()
        self.session.create_page(title="Test", content="<p>Content</p>", parent_id="456", space_id="TEST")
        self.session._create_page_v1.assert_called_once()

    def test_update_page_routes_to_v1(self):
        """Test update_page routes to v1 implementation."""
        self.session._update_page_v1 = MagicMock()
        self.session.update_page("123", "<p>Updated</p>", title="New Title", version=2, message="")
        self.session._update_page_v1.assert_called_once()

    def test_delete_page_routes_to_v1(self):
        """Test delete_page routes to v1 implementation."""
        self.session._delete_page_v1 = MagicMock()
        self.session.delete_page("123", purge=True)
        self.session._delete_page_v1.assert_called_once_with("123", purge=True)

    def test_page_exists_routes_to_v1(self):
        """Test page_exists routes to v1 implementation."""
        self.session._page_exists_v1 = MagicMock(return_value="123")
        result = self.session.page_exists("Test Page", space_id="TEST")
        self.session._page_exists_v1.assert_called_once_with("Test Page", space_key="TEST")
        self.assertEqual(result, "123")


class TestV1AttachmentMethods(unittest.TestCase):
    """Test v1 API attachment operations."""

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

    def test_get_attachment_routes_to_v1(self):
        """Test get_attachment_by_name routes to v1 implementation."""
        self.session._get_attachment_by_name_v1 = MagicMock()
        self.session.get_attachment_by_name("123", "test.png")
        self.session._get_attachment_by_name_v1.assert_called_once_with("123", "test.png")


class TestV1PropertyMethods(unittest.TestCase):
    """Test v1 API content property operations."""

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

    def test_get_properties_routes_to_v1(self):
        """Test get_content_properties_for_page routes to v1."""
        self.session._get_content_properties_for_page_v1 = MagicMock(return_value=[])
        self.session.get_content_properties_for_page("123")
        self.session._get_content_properties_for_page_v1.assert_called_once_with("123")

    def test_delete_property_routes_to_v1(self):
        """Test remove_content_property_from_page routes to v1."""
        from md2conf.api import ConfluenceContentVersion, ConfluenceIdentifiedContentProperty

        mock_prop = ConfluenceIdentifiedContentProperty(id="prop-id", key="test-key", value={"data": "value"}, version=ConfluenceContentVersion(number=1))
        self.session.get_content_properties_for_page = MagicMock(return_value=[mock_prop])
        self.session._delete_content_property_v1 = MagicMock()

        self.session.remove_content_property_from_page("123", "prop-id")
        self.session._delete_content_property_v1.assert_called_once_with("123", "test-key")


class TestV1PagePropertiesMethods(unittest.TestCase):
    """Test v1 API page properties operations."""

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

    def test_get_page_properties_routes_to_v1(self):
        """Test get_page_properties routes to v1 implementation."""
        self.session._get_page_properties_v1 = MagicMock()
        self.session.get_page_properties("123")
        self.session._get_page_properties_v1.assert_called_once_with("123")

    def test_get_page_properties_by_title_routes_to_v1(self):
        """Test get_page_properties_by_title routes to v1 implementation."""
        self.session._get_page_properties_by_title_v1 = MagicMock()
        self.session.get_page_properties_by_title("Test Page", space_id="TEST")
        self.session._get_page_properties_by_title_v1.assert_called_once_with("Test Page", space_key="TEST")


class TestV1SpaceHandling(unittest.TestCase):
    """Test v1 space key vs space ID handling."""

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

    def test_v1_uses_space_key_not_id(self):
        """Test that v1 methods use space keys instead of space IDs."""
        # For v1, space_id parameter actually contains space KEY
        self.session._page_exists_v1 = MagicMock(return_value=None)
        self.session.page_exists("Test", space_id="MYSPACE")
        # Verify it was passed as space_key
        self.session._page_exists_v1.assert_called_once_with("Test", space_key="MYSPACE")


class TestV1UploadAttachment(unittest.TestCase):
    """Test v1 attachment upload with Content-Type header handling."""

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

    @patch("pathlib.Path.is_file", return_value=True)
    @patch("pathlib.Path.stat")
    @patch("builtins.open", create=True)
    def test_v1_removes_content_type_header_during_upload(self, mock_open, mock_stat, mock_is_file):
        """Test that v1 removes Content-Type header during file upload."""
        # Set up session with Content-Type header
        self.session.session.headers = {"Content-Type": "application/json"}

        # Mock file operations
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_stat.return_value.st_size = 100

        # Mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [{"id": "att123", "version": {"number": 1}}]}
        mock_response.raise_for_status = MagicMock()
        self.session.session.post.return_value = mock_response

        # Mock get_attachment_by_name to raise error (no existing attachment)
        self.session.get_attachment_by_name = MagicMock(side_effect=ConfluenceError("not found"))

        # Mock _update_attachment
        self.session._update_attachment = MagicMock()

        # Upload attachment
        from pathlib import Path

        test_path = Path("/tmp/test.txt")
        self.session.upload_attachment("123", "test.txt", attachment_path=test_path)

        # Verify Content-Type was restored after upload
        self.assertEqual(self.session.session.headers.get("Content-Type"), "application/json")


if __name__ == "__main__":
    unittest.main()
