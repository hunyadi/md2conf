"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import os
from typing import Literal, overload


class ArgumentError(ValueError):
    "Raised when wrong arguments are passed to a function call."


class PageError(ValueError):
    "Raised in case there is an issue with a Confluence page."


class ConfluenceError(RuntimeError):
    "Raised when a Confluence API call fails."


@overload
def _validate_domain(domain: str) -> str: ...


@overload
def _validate_domain(domain: str | None) -> str | None: ...


def _validate_domain(domain: str | None) -> str | None:
    if domain is None:
        return None

    if domain.startswith(("http://", "https://")) or domain.endswith("/"):
        raise ArgumentError("Confluence domain looks like a URL; only host name required")

    return domain


@overload
def _validate_base_path(base_path: str) -> str: ...


@overload
def _validate_base_path(base_path: str | None) -> str | None: ...


def _validate_base_path(base_path: str | None) -> str | None:
    if base_path is None:
        return None

    if not base_path.startswith("/") or not base_path.endswith("/"):
        raise ArgumentError("Confluence base path must start and end with a '/'")

    return base_path


class ConfluenceSiteProperties:
    """
    Properties related to a Confluence site.

    :param domain: Domain name for Confluence site, e.g. `markdown-to-confluence.atlassian.net`.
    :param base_path: Base path for Confluence site, e.g. `/wiki/`.
    :param space_key: Confluence space key for pages to be published.
    """

    domain: str
    base_path: str
    space_key: str | None

    def __init__(
        self,
        domain: str | None = None,
        base_path: str | None = None,
        space_key: str | None = None,
    ) -> None:
        opt_domain = domain or os.getenv("CONFLUENCE_DOMAIN")
        opt_base_path = base_path or os.getenv("CONFLUENCE_PATH")
        opt_space_key = space_key or os.getenv("CONFLUENCE_SPACE_KEY")

        if not opt_domain:
            raise ArgumentError("Confluence domain not specified")
        if not opt_base_path:
            opt_base_path = "/wiki/"

        self.domain = _validate_domain(opt_domain)
        self.base_path = _validate_base_path(opt_base_path)
        self.space_key = opt_space_key


class ConnectionProperties:
    """
    Properties related to connecting to Confluence.

    :param domain: Domain name for Confluence site, e.g. `markdown-to-confluence.atlassian.net`.
    :param base_path: Base path for Confluence site, e.g. `/wiki/`.
    :param space_key: Confluence space key for pages to be published.
    :param api_url: Confluence API URL. Required for scoped tokens.
    :param user_name: Confluence user name.
    :param api_key: Confluence API key.
    :param api_version: Confluence REST API version to use (v2 for Cloud, v1 for Data Center/Server).
    :param headers: Additional HTTP headers to pass to Confluence REST API calls.
    """

    domain: str | None
    base_path: str | None
    space_key: str | None
    api_url: str | None
    user_name: str | None
    api_key: str
    api_version: Literal["v2", "v1"] | None
    headers: dict[str, str] | None

    def __init__(
        self,
        *,
        api_url: str | None = None,
        domain: str | None = None,
        base_path: str | None = None,
        user_name: str | None = None,
        api_key: str | None = None,
        space_key: str | None = None,
        headers: dict[str, str] | None = None,
        api_version: Literal["v2", "v1"] | None = None,
    ) -> None:
        opt_api_url = api_url or os.getenv("CONFLUENCE_API_URL")
        opt_domain = domain or os.getenv("CONFLUENCE_DOMAIN")
        opt_base_path = base_path or os.getenv("CONFLUENCE_PATH")
        opt_space_key = space_key or os.getenv("CONFLUENCE_SPACE_KEY")
        opt_user_name = user_name or os.getenv("CONFLUENCE_USER_NAME")
        opt_api_key = api_key or os.getenv("CONFLUENCE_API_KEY")
        if api_version is not None:
            opt_api_version = api_version
        else:
            match os.getenv("CONFLUENCE_API_VERSION"):
                case "v2":
                    opt_api_version = "v2"
                case "v1":
                    opt_api_version = "v1"
                case _:
                    opt_api_version = None

        if not opt_api_key:
            raise ArgumentError("Confluence API key not specified")
        if not opt_api_url and not opt_domain:
            raise ArgumentError("Confluence API URL or domain required")
        if not opt_api_url and not opt_base_path:
            opt_base_path = "/wiki/"

        self.api_url = opt_api_url
        self.domain = _validate_domain(opt_domain)
        self.base_path = _validate_base_path(opt_base_path)
        self.space_key = opt_space_key
        self.user_name = opt_user_name
        self.api_key = opt_api_key
        self.api_version = opt_api_version
        self.headers = headers
