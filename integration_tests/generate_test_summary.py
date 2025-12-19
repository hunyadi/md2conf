#!/usr/bin/env python3
"""
Generate GitHub Actions step summary with Confluence test page URLs.

This script reads the test page cache and generates a formatted summary
with clickable links to the Confluence pages created during integration tests.
"""

import json
import os
import sys
from pathlib import Path


def generate_page_url(domain: str, base_path: str, page_id: str) -> str:
    """
    Generate a Confluence page URL.

    :param domain: Confluence domain (e.g., 'example.atlassian.net')
    :param base_path: Base path (e.g., '/wiki/')
    :param page_id: Page ID
    :returns: Full URL to the page
    """
    # Remove trailing slash from base_path if present
    base_path = base_path.rstrip("/")

    # Construct URL
    return f"https://{domain}{base_path}/pages/viewpage.action?pageId={page_id}"


def get_page_title_from_cache_key(cache_key: str) -> str:
    """
    Extract page title from cache key format 'SPACE:Title'.

    :param cache_key: Cache key in format 'SPACE:Title'
    :returns: Page title
    """
    if ":" in cache_key:
        return cache_key.split(":", 1)[1]
    return cache_key


def main() -> None:
    """Generate test summary and write to GitHub step summary."""
    # Get environment variables
    domain = os.getenv("CONFLUENCE_DOMAIN")
    base_path = os.getenv("CONFLUENCE_PATH", "/wiki/")
    space_key = os.getenv("CONFLUENCE_SPACE_KEY")

    if not domain:
        print("Error: CONFLUENCE_DOMAIN not set", file=sys.stderr)
        sys.exit(1)

    # Read test page cache
    cache_file = Path(__file__).parent / ".test_pages.json"

    if not cache_file.exists():
        print("No test page cache found - tests may not have created pages")
        summary = "## Integration Test Results\n\n"
        summary += "⚠️ No test pages found. Tests may have failed before creating pages.\n"
    else:
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                page_cache = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error reading cache file: {e}", file=sys.stderr)
            sys.exit(1)

        # Generate summary
        summary = "## Integration Test Results\n\n"

        if not page_cache:
            summary += "⚠️ No test pages were created during this run.\n"
        else:
            summary += f"### Test Pages in Space: `{space_key}`\n\n"
            summary += "The following pages were created/used for testing. "
            summary += "Click the links to view them in Confluence:\n\n"

            # Sort by title for consistent output
            sorted_pages = sorted(page_cache.items(), key=lambda x: get_page_title_from_cache_key(x[0]))

            for cache_key, page_id in sorted_pages:
                title = get_page_title_from_cache_key(cache_key)
                url = generate_page_url(domain, base_path, page_id)
                summary += f"- [{title}]({url}) (ID: `{page_id}`)\n"

            summary += "\n### Quick Links\n\n"
            summary += f"- [View Space](https://{domain}{base_path.rstrip('/')}/spaces/{space_key}/overview)\n"
            summary += f"- [Pages in Space](https://{domain}{base_path.rstrip('/')}/spaces/{space_key}/pages)\n"

    # Write to GitHub step summary if available
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write(summary)
            print("✓ Test summary written to GitHub Actions")
        except IOError as e:
            print(f"Error writing summary: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Not in GitHub Actions, print to stdout
        print(summary)

    print("\nTest Summary:")
    print("=" * 60)
    print(summary)


if __name__ == "__main__":
    main()
