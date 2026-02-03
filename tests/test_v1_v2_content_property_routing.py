"""
Test content property routing between API v1 and v2.
"""

import unittest
from unittest.mock import MagicMock

from md2conf.api import ConfluenceContentProperty, ConfluenceSession, ConfluenceVersion


class TestContentPropertyRouting(unittest.TestCase):
    """Test that content property methods route correctly based on API version."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = MagicMock()

    def test_get_content_property_routes_to_v1(self):
        """Test that get_content_property_for_page routes to v1 implementation."""
        session = ConfluenceSession(
            self.mock_session,
            api_url="https://example.com",
            domain="example.com",
            base_path="/wiki/",
            space_key="TEST",
            api_version=ConfluenceVersion.VERSION_1,
        )

        # Mock the v1 method
        session._get_content_property_v1 = MagicMock(return_value=None)

        # Call the public method
        session.get_content_property_for_page("123", "test-key")

        # Verify v1 method was called
        session._get_content_property_v1.assert_called_once_with("123", "test-key")

    def test_get_content_property_routes_to_v2(self):
        """Test that get_content_property_for_page routes to v2 implementation."""
        session = ConfluenceSession(
            self.mock_session,
            api_url="https://example.com",
            domain="example.com",
            base_path="/wiki/",
            space_key="TEST",
            api_version=ConfluenceVersion.VERSION_2,
        )

        # Mock the _fetch method used by v2
        session._fetch = MagicMock(return_value=[])

        # Call the public method
        session.get_content_property_for_page("123", "test-key")

        # Verify _fetch was called with v2 path
        session._fetch.assert_called_once()
        call_args = session._fetch.call_args
        self.assertEqual(call_args[0][0], "/pages/123/properties")

    def test_add_content_property_routes_to_v1(self):
        """Test that add_content_property_to_page routes to v1 implementation."""
        session = ConfluenceSession(
            self.mock_session,
            api_url="https://example.com",
            domain="example.com",
            base_path="/wiki/",
            space_key="TEST",
            api_version=ConfluenceVersion.VERSION_1,
        )

        # Mock the v1 method
        session._add_content_property_v1 = MagicMock()

        # Create test property
        prop = ConfluenceContentProperty(key="test", value={"data": "value"})

        # Call the public method
        session.add_content_property_to_page("123", prop)

        # Verify v1 method was called
        session._add_content_property_v1.assert_called_once_with("123", prop)

    def test_update_content_property_routes_to_v1(self):
        """Test that update_content_property_for_page routes to v1 implementation."""
        session = ConfluenceSession(
            self.mock_session,
            api_url="https://example.com",
            domain="example.com",
            base_path="/wiki/",
            space_key="TEST",
            api_version=ConfluenceVersion.VERSION_1,
        )

        # Mock the v1 method
        session._update_content_property_v1 = MagicMock()

        # Create test property
        prop = ConfluenceContentProperty(key="test", value={"data": "updated"})

        # Call the public method
        session.update_content_property_for_page("123", "prop-id", 2, prop)

        # Verify v1 method was called
        session._update_content_property_v1.assert_called_once_with("123", "prop-id", 2, prop)


if __name__ == "__main__":
    unittest.main()
