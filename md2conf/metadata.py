"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConfluenceSiteMetadata:
    domain: str
    base_path: str
    space_key: Optional[str]


@dataclass
class ConfluencePageMetadata:
    page_id: str
    space_key: Optional[str]
    title: str
