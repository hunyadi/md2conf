"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConfluenceSiteMetadata:
    """
    Data associated with a Confluence wiki site.

    :param domain: Confluence organization domain (e.g. `levente-hunyadi.atlassian.net`).
    :param base_path: Base path for Confluence (default: `/wiki/`).
    :param space_key: Confluence space key for new pages (e.g. `~hunyadi` or `INST`).
    """

    domain: str
    base_path: str
    space_key: Optional[str]


@dataclass
class ConfluencePageMetadata:
    """
    Data associated with a Confluence page.

    :param page_id: Confluence page ID.
    :param space_key: Confluence space key.
    :param title: Document title.
    """

    page_id: str
    space_key: str
    title: str
