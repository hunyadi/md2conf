"""
Unit tests for Confluence REST API v1 support.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from unittest.mock import MagicMock, Mock, patch

from md2conf.api import ConfluenceVersion
from md2conf.environment import ArgumentError, ConnectionProperties


class TestAPIVersionParsing(unittest.TestCase):
    """Test API version parsing in ConnectionProperties."""

    def test_default_api_version_is_v2(self) -> None:
        """Test that API version defaults to v2 when not specified."""
        props = ConnectionProperties(api_key="test-key", domain="example.atlassian.net")
        self.assertEqual(props.api_version, "v2")

    def test_store_v1_string(self) -> None:
        """Test storing 'v1' string."""
        props = ConnectionProperties(api_key="test-key", domain="example.atlassian.net", api_version="v1")
        self.assertEqual(props.api_version, "v1")

    def test_store_v2_string(self) -> None:
        """Test storing 'v2' string."""
        props = ConnectionProperties(api_key="test-key", domain="example.atlassian.net", api_version="v2")
        self.assertEqual(props.api_version, "v2")

    def test_invalid_api_version_caught_on_session_creation(self) -> None:
        """Test that invalid API version string raises ArgumentError when creating session."""
        from md2conf.api import ConfluenceAPI

        props = ConnectionProperties(
            api_key="test-key",
            domain="example.atlassian.net",
            api_version="v3",  # Invalid but stored as-is
        )
        # Should be stored without error
        self.assertEqual(props.api_version, "v3")

        # Error should be raised when trying to create session
        api = ConfluenceAPI(props)
        with self.assertRaises(ArgumentError) as context:
            with api:
                pass
        self.assertIn("Invalid API version", str(context.exception))
        self.assertIn("v3", str(context.exception))


class TestURLConstruction(unittest.TestCase):
    """Test URL construction for different API versions."""

    def test_v1_url_prefix(self) -> None:
        """Test that v1 URLs use /rest/api prefix."""
        self.assertEqual(ConfluenceVersion.VERSION_1.value, "rest/api")

    def test_v2_url_prefix(self) -> None:
        """Test that v2 URLs use /api/v2 prefix."""
        self.assertEqual(ConfluenceVersion.VERSION_2.value, "api/v2")


class TestAPIVersionRouting(unittest.TestCase):
    """Test that API methods route to correct version implementations."""

    @patch("md2conf.api.requests.Session")
    def test_session_stores_api_version(self, mock_session_class: Mock) -> None:
        """Test that ConfluenceSession stores the API version."""
        from md2conf.api import ConfluenceSession

        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Test with v1
        session_v1 = ConfluenceSession(
            mock_session, api_url="https://example.com/", domain="example.com", base_path="/wiki/", space_key="TEST", api_version=ConfluenceVersion.VERSION_1
        )
        self.assertEqual(session_v1.api_version, ConfluenceVersion.VERSION_1)

        # Test with v2 (default)
        session_v2 = ConfluenceSession(mock_session, api_url="https://example.com/", domain="example.com", base_path="/wiki/", space_key="TEST")
        self.assertEqual(session_v2.api_version, ConfluenceVersion.VERSION_2)


class TestConfigurationValidation(unittest.TestCase):
    """Test configuration validation for API v1."""

    def test_v1_requires_domain(self) -> None:
        """Test that v1 requires domain to be specified."""
        # This should work - domain is provided
        props = ConnectionProperties(api_key="test-key", domain="example.atlassian.net", api_version="v1")
        self.assertEqual(props.api_version, "v1")

        # This should fail - no domain and no api_url
        with self.assertRaises(ArgumentError) as context:
            ConnectionProperties(api_key="test-key", api_version="v1")
        self.assertIn("domain", str(context.exception).lower())

    def test_v2_works_without_domain_if_api_url_provided(self) -> None:
        """Test that v2 can work with just api_url."""
        props = ConnectionProperties(api_key="test-key", api_url="https://api.atlassian.com/ex/confluence/cloud-id/", api_version="v2")
        self.assertEqual(props.api_version, "v2")


class TestBackwardCompatibility(unittest.TestCase):
    """Test backward compatibility - existing code should work unchanged."""

    def test_no_api_version_parameter_defaults_to_v2(self) -> None:
        """Test that omitting api_version parameter defaults to v2."""
        props = ConnectionProperties(api_key="test-key", domain="example.atlassian.net")
        self.assertEqual(props.api_version, "v2")

    def test_existing_connection_properties_still_work(self) -> None:
        """Test that existing ConnectionProperties usage patterns still work."""
        # This is how existing code creates ConnectionProperties
        props = ConnectionProperties(
            api_url="https://example.com/",
            domain="example.com",
            base_path="/wiki/",
            user_name="user",
            api_key="key",
            space_key="SPACE",
            headers={"Custom": "Header"},
        )
        # Should default to v2
        self.assertEqual(props.api_version, "v2")
        # All other properties should work as before
        self.assertEqual(props.api_url, "https://example.com/")
        self.assertEqual(props.domain, "example.com")
        self.assertEqual(props.base_path, "/wiki/")
        self.assertEqual(props.user_name, "user")
        self.assertEqual(props.api_key, "key")
        self.assertEqual(props.space_key, "SPACE")
        self.assertEqual(props.headers, {"Custom": "Header"})


if __name__ == "__main__":
    unittest.main()
