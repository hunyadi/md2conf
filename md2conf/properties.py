import os
from typing import Dict, Optional


class ConfluenceError(RuntimeError):
    pass


class ConfluenceProperties:
    domain: str
    base_path: str
    space_key: str
    user_name: Optional[str]
    api_key: str
    headers: Optional[Dict[str, str]]

    def __init__(
        self,
        domain: Optional[str] = None,
        base_path: Optional[str] = None,
        user_name: Optional[str] = None,
        api_key: Optional[str] = None,
        space_key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> None:
        opt_domain = domain or os.getenv("CONFLUENCE_DOMAIN")
        opt_base_path = base_path or os.getenv("CONFLUENCE_PATH")
        opt_user_name = user_name or os.getenv("CONFLUENCE_USER_NAME")
        opt_api_key = api_key or os.getenv("CONFLUENCE_API_KEY")
        opt_space_key = space_key or os.getenv("CONFLUENCE_SPACE_KEY")

        if not opt_domain:
            raise ConfluenceError("Confluence domain not specified")
        if not opt_base_path:
            opt_base_path = "/wiki/"
        if not opt_api_key:
            raise ConfluenceError("Confluence API key not specified")
        if not opt_space_key:
            raise ConfluenceError("Confluence space key not specified")

        if opt_domain.startswith(("http://", "https://")) or opt_domain.endswith("/"):
            raise ConfluenceError(
                "Confluence domain looks like a URL; only host name required"
            )
        if not opt_base_path.startswith("/") or not opt_base_path.endswith("/"):
            raise ConfluenceError("Confluence base path must start and end with a '/'")

        self.domain = opt_domain
        self.base_path = opt_base_path
        self.user_name = opt_user_name
        self.api_key = opt_api_key
        self.space_key = opt_space_key
        self.headers = headers
