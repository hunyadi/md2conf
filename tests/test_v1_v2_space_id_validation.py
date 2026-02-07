"""
Unit tests for space ID validation in API v2.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from unittest.mock import MagicMock

from md2conf.api import ConfluenceSession, ConfluenceVersion
from md2conf.environment import ArgumentError


class TestSpaceIDValidation(unittest.TestCase):
    """Test that v2 API methods validate space_id parameter."""

    def setUp(self):
        self.mock_session = MagicMock()
        self.session_v2 = ConfluenceSession(
            self.mock_session,
            api_url="https://example.com",
            domain="example.com",
            base_path="/wiki/",
            space_key="TEST",
            api_version=ConfluenceVersion.VERSION_2,
        )

    def test_get_homepage_id_requires_space_id(self):
        """Test that get_homepage_id raises error when space_id is None for v2."""
        with self.assertRaises(ArgumentError) as context:
            self.session_v2.get_homepage_id(space_id=None)
        self.assertIn("space_id is required", str(context.exception))

    def test_create_page_v2_requires_space_id(self):
        """Test that create_page in v2 requires space_id."""
        with self.assertRaises(ArgumentError) as context:
            self.session_v2.create_page(title="Test", content="<p>Content</p>", parent_id="123", space_id=None)
        self.assertIn("space_id is required", str(context.exception))

    def test_v1_create_page_works_without_space_id(self):
        """Test that v1 create_page works without explicit space_id."""
        session_v1 = ConfluenceSession(
            self.mock_session,
            api_url="https://example.com",
            domain="example.com",
            base_path="/wiki/",
            space_key="TEST",
            api_version=ConfluenceVersion.VERSION_1,
        )

        # Mock the v1 implementation
        session_v1._create_page_v1 = MagicMock()

        # Should not raise error - v1 uses default space_key
        session_v1.create_page(title="Test", content="<p>Content</p>", parent_id="123", space_id=None)

        # Verify v1 method was called
        session_v1._create_page_v1.assert_called_once()


if __name__ == "__main__":
    unittest.main()
