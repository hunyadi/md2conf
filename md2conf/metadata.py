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
    :param overwrite: True if operations are allowed to update document properties (e.g. title).
    """

    page_id: str
    space_key: Optional[str]
    title: str
    overwrite: bool
