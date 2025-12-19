"""
Integration test fixtures for automatic test environment setup.

This module provides utilities to automatically create and manage test pages
in Confluence, eliminating the need for manual page setup before running tests.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import json
import logging
from pathlib import Path
from typing import Optional

from md2conf.api import ConfluenceSession

LOGGER = logging.getLogger(__name__)


class IntegrationTestFixture:
    """
    Manages test page lifecycle for integration tests.

    This class provides automatic creation and management of test pages,
    allowing integration tests to run without manual setup. It maintains
    a cache of created pages to avoid recreating them on subsequent runs.

    Example:
        >>> with ConfluenceAPI() as session:
        >>>     fixture = IntegrationTestFixture(session, "TEST_SPACE")
        >>>     page_id = fixture.get_or_create_test_page("My Test Page")
        >>>     # Run tests with page_id
        >>>     fixture.cleanup(delete_pages=False)
    """

    def __init__(
        self,
        session: ConfluenceSession,
        space_key: str,
        cache_file: Optional[Path] = None,
    ):
        """
        Initialize the test fixture.

        :param session: Active Confluence session from ConfluenceAPI context
        :param space_key: Default space key for test pages
        :param cache_file: Optional path to cache file
                          (defaults to .test_pages.json)
        """
        self.session = session
        self.default_space_key = space_key
        cache_path = cache_file or (Path(__file__).parent / ".test_pages.json")
        self.cache_file = cache_path
        self.page_cache: dict[str, str] = self._load_cache()

    def _load_cache(self) -> dict[str, str]:
        """Load page cache from disk."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache: dict[str, str] = json.load(f)
                    return cache
            except (json.JSONDecodeError, IOError) as e:
                LOGGER.warning(f"Could not load cache file: {e}")
        return {}

    def _save_cache(self) -> None:
        """Save page cache to disk."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.page_cache, f, indent=2)
        except IOError as e:
            LOGGER.warning(f"Could not save cache file: {e}")

    def _page_exists(self, page_id: str) -> bool:
        """Check if a page exists in Confluence."""
        try:
            self.session.get_page(page_id)
            return True
        except Exception:
            return False

    def _find_page_by_title(self, title: str, space_key: Optional[str] = None) -> Optional[str]:
        """
        Find a page by title in the specified space.

        :param title: Page title to search for
        :param space_key: Space key (uses default if not specified)
        :returns: Page ID if found, None otherwise
        """
        space = space_key or self.default_space_key
        try:
            page = self.session.get_page_properties_by_title(title=title, space_key=space)
            return page.id
        except Exception as e:
            LOGGER.warning(f"Error searching for page '{title}': {e}")
        return None

    def get_or_create_test_page(
        self,
        title: str,
        space_key: Optional[str] = None,
        parent_id: Optional[str] = None,
        body: str = "<p>Automated integration test page</p>",
    ) -> str:
        """
        Get an existing test page or create it if missing.

        This method follows a three-step approach:
        1. Check local cache for page ID and verify it exists
        2. Search Confluence for page by title
        3. Create new page if not found

        :param title: Page title
        :param space_key: Space key (uses default if not specified)
        :param parent_id: Parent page ID (optional)
        :param body: Initial page body content
        :returns: Page ID (either existing or newly created)
        """
        space = space_key or self.default_space_key
        cache_key = f"{space}:{title}"

        # Step 1: Check cache
        if cache_key in self.page_cache:
            cached_id = self.page_cache[cache_key]
            if self._page_exists(cached_id):
                LOGGER.info(f"Using cached page: {title} (ID: {cached_id})")
                return cached_id
            else:
                LOGGER.info(f"Cached page {title} no longer exists, will recreate")
                del self.page_cache[cache_key]

        # Step 2: Search for existing page
        existing_id = self._find_page_by_title(title, space)
        if existing_id:
            LOGGER.info(f"Found existing page: {title} (ID: {existing_id})")
            self.page_cache[cache_key] = str(existing_id)
            self._save_cache()
            return existing_id

        # Step 3: Create new page
        LOGGER.info(f"Creating new test page: {title}")
        try:
            # API requires parent_id; if not provided, needs different approach
            if parent_id is None:
                raise ValueError(
                    "parent_id is required to create a page. Please provide the parent page ID or use get_page_properties_by_title to find a suitable parent."
                )
            page = self.session.create_page(
                parent_id=parent_id,
                title=title,
                new_content=body,
            )
            page_id = page.id
            self.page_cache[cache_key] = page_id
            self._save_cache()
            LOGGER.info(f"Created page: {title} (ID: {page_id})")
            return page_id
        except Exception as e:
            LOGGER.error(f"Failed to create page '{title}': {e}")
            raise

    def update_test_page(
        self,
        page_id: str,
        body: str,
        title: Optional[str] = None,
    ) -> None:
        """
        Update an existing test page.

        :param page_id: Page ID to update
        :param body: New page body content
        :param title: New page title (optional, keeps existing if not
                     specified)
        """
        try:
            page = self.session.get_page(page_id)
            self.session.update_page(
                page_id=page_id,
                content=body,
                title=title or page.title,
                version=page.version.number,
            )
            LOGGER.info(f"Updated test page: {page_id}")
        except Exception as e:
            LOGGER.error(f"Failed to update page {page_id}: {e}")
            raise

    def cleanup(self, delete_pages: bool = False) -> None:
        """
        Cleanup test resources.

        :param delete_pages: If True, delete all test pages created by
                            this fixture. If False, only remove cache.
        """
        if delete_pages:
            LOGGER.info("Deleting test pages...")
            for cache_key, page_id in list(self.page_cache.items()):
                try:
                    self.session.delete_page(page_id)
                    LOGGER.info(f"Deleted test page: {cache_key} (ID: {page_id})")
                    del self.page_cache[cache_key]
                except Exception as e:
                    LOGGER.warning(f"Could not delete page {cache_key}: {e}")

        # Remove cache file
        if self.cache_file.exists():
            try:
                self.cache_file.unlink()
                LOGGER.info("Removed cache file")
            except IOError as e:
                LOGGER.warning(f"Could not remove cache file: {e}")

    def get_cached_pages(self) -> dict[str, str]:
        """
        Get all cached page IDs.

        :returns: Dictionary mapping "space:title" to page ID
        """
        return self.page_cache.copy()

    def clear_cache(self) -> None:
        """Clear the page cache without deleting pages."""
        self.page_cache.clear()
        self._save_cache()
        LOGGER.info("Cleared page cache")
