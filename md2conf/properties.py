"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import os
from typing import Optional


class ArgumentError(ValueError):
    "Raised when wrong arguments are passed to a function call."


class PageError(ValueError):
    "Raised in case there is an issue with a Confluence page."


class ConfluenceError(RuntimeError):
    "Raised when a Confluence API call fails."


class ConfluenceSiteProperties:
    domain: str
    base_path: str
    space_key: Optional[str]

    def __init__(
        self,
        domain: Optional[str] = None,
        base_path: Optional[str] = None,
        space_key: Optional[str] = None,
    ) -> None:
        opt_domain = domain or os.getenv("CONFLUENCE_DOMAIN")
        opt_base_path = base_path or os.getenv("CONFLUENCE_PATH")
        opt_space_key = space_key or os.getenv("CONFLUENCE_SPACE_KEY")

        if not opt_domain:
            raise ArgumentError("Confluence domain not specified")
        if not opt_base_path:
            opt_base_path = "/wiki/"

        if opt_domain.startswith(("http://", "https://")) or opt_domain.endswith("/"):
            raise ArgumentError(
                "Confluence domain looks like a URL; only host name required"
            )
        if not opt_base_path.startswith("/") or not opt_base_path.endswith("/"):
            raise ArgumentError("Confluence base path must start and end with a '/'")

        self.domain = opt_domain
        self.base_path = opt_base_path
        self.space_key = opt_space_key


class ConfluenceConnectionProperties(ConfluenceSiteProperties):
    "Properties related to connecting to Confluence."

    user_name: Optional[str]
    api_key: str
    headers: Optional[dict[str, str]]

    def __init__(
        self,
        domain: Optional[str] = None,
        base_path: Optional[str] = None,
        user_name: Optional[str] = None,
        api_key: Optional[str] = None,
        space_key: Optional[str] = None,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(domain, base_path, space_key)

        opt_user_name = user_name or os.getenv("CONFLUENCE_USER_NAME")
        opt_api_key = api_key or os.getenv("CONFLUENCE_API_KEY")

        if not opt_api_key:
            raise ArgumentError("Confluence API key not specified")

        self.user_name = opt_user_name
        self.api_key = opt_api_key
        self.headers = headers
