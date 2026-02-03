"""
Unit tests for label endpoint routing between v1 and v2 APIs.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from unittest.mock import MagicMock

from md2conf.api import ConfluenceSession, ConfluenceVersion


class TestLabelEndpointRouting(unittest.TestCase):
    """Test that label methods use correct endpoints for v1 vs v2."""

    def test_v1_uses_label_endpoint(self):
        """Test that v1 uses /content/{pageId}/label endpoint."""
        mock_session = MagicMock()
        session = ConfluenceSession(
            mock_session, api_url="https://example.com", domain="example.com", base_path="/wiki/", space_key="TEST", api_version=ConfluenceVersion.VERSION_1
        )

        # Mock _fetch to capture the path
        session._fetch = MagicMock(return_value=[])

        session.get_labels("123")

        # Verify v1 endpoint was used
        call_args = session._fetch.call_args
        self.assertEqual(call_args[0][0], "/content/123/label")

    def test_v2_uses_labels_endpoint(self):
        """Test that v2 uses /pages/{pageId}/labels endpoint."""
        mock_session = MagicMock()
        session = ConfluenceSession(
            mock_session, api_url="https://example.com", domain="example.com", base_path="/wiki/", space_key="TEST", api_version=ConfluenceVersion.VERSION_2
        )

        # Mock _fetch to capture the path
        session._fetch = MagicMock(return_value=[])

        session.get_labels("123")

        # Verify v2 endpoint was used
        call_args = session._fetch.call_args
        self.assertEqual(call_args[0][0], "/pages/123/labels")


if __name__ == "__main__":
    unittest.main()
