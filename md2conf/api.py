"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import mimetypes
import ssl
from collections.abc import Mapping
from types import TracebackType
from typing import Any, TypeVar

from requests import PreparedRequest, Response, Session
from requests.adapters import HTTPAdapter
from truststore import SSLContext
from urllib3.util import Retry

from .api_base import ConfluenceSession
from .api_v1 import ConfluenceSessionV1
from .api_v2 import ConfluenceSessionV2
from .compatibility import override
from .environment import ConnectionProperties
from .options_api import ConfluenceSessionOptions

T = TypeVar("T")

# spellchecker: disable
mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx", strict=True)
mimetypes.add_type("text/vnd.mermaid", ".mmd", strict=True)
mimetypes.add_type("text/vnd.plantuml", ".puml", strict=True)
mimetypes.add_type("application/vnd.oasis.opendocument.presentation", ".odp", strict=True)
mimetypes.add_type("application/vnd.oasis.opendocument.spreadsheet", ".ods", strict=True)
mimetypes.add_type("application/vnd.oasis.opendocument.text", ".odt", strict=True)
mimetypes.add_type("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx", strict=True)
mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx", strict=True)
# spellchecker: enable


LOGGER = logging.getLogger(__name__)


class RetryAdapter(HTTPAdapter):
    """
    Retries with exponential back-off to handle rate-limited endpoints (HTTP 429) and eventual consistency (HTTP 404).
    """

    _retry_rate_limit: Retry
    _retry_eventual_consistency: Retry

    def __init__(self) -> None:
        # spellchecker: disable
        self._retry_rate_limit = Retry(
            total=3, allowed_methods=["GET", "POST", "PUT", "DELETE"], status_forcelist=[429], backoff_factor=1, raise_on_redirect=False, raise_on_status=False
        )
        self._retry_eventual_consistency = Retry(
            total=3, allowed_methods=["GET"], status_forcelist=[404, 429], backoff_factor=1, raise_on_redirect=False, raise_on_status=False
        )
        # spellchecker: enable
        super().__init__()

    @override
    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: float | tuple[float, float] | tuple[float, None] | None = None,
        verify: bool | str = True,
        cert: bytes | str | tuple[bytes | str, bytes | str] | None = None,
        proxies: Mapping[str, str] | None = None,
    ) -> Response:
        self.max_retries = self._retry_eventual_consistency if request.method == "GET" else self._retry_rate_limit
        return super().send(request, stream, timeout, verify, cert, proxies)


class TruststoreRetryAdapter(RetryAdapter):
    """
    Provides a general-case interface for HTTPS sessions to connect to HTTPS URLs.

    This class implements the Transport Adapter interface in the Python library `requests`.

    This class will usually be created by the :class:`requests.Session` class under the covers.
    """

    @override
    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any) -> None:
        """
        Adapts the pool manager to use the provided SSL context instead of the default.
        """

        ctx = SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        super().init_poolmanager(connections, maxsize, block, ssl_context=ctx, **pool_kwargs)  # type: ignore[no-untyped-call]


class ConfluenceAPI:
    """
    Encapsulates operations that can be invoked via the [Confluence REST API](https://developer.atlassian.com/cloud/confluence/rest/v2/).
    """

    properties: ConnectionProperties
    session: "ConfluenceSession | None" = None
    options: ConfluenceSessionOptions

    def __init__(self, properties: ConnectionProperties | None = None, options: ConfluenceSessionOptions | None = None) -> None:
        self.properties = properties or ConnectionProperties()
        self.options = options or ConfluenceSessionOptions()

    def __enter__(self) -> "ConfluenceSession":
        """
        Opens a connection to a Confluence server.
        """

        session = Session()
        session.mount("https://", TruststoreRetryAdapter())
        session.mount("http://", RetryAdapter())

        if self.properties.user_name:
            session.auth = (self.properties.user_name, self.properties.api_key)
        else:
            session.headers.update({"Authorization": f"Bearer {self.properties.api_key}"})

        match self.properties.api_version:
            case "v2" | None:
                self.session = ConfluenceSessionV2(
                    session,
                    options=self.options,
                    api_url=self.properties.api_url,
                    domain=self.properties.domain,
                    base_path=self.properties.base_path,
                    space_key=self.properties.space_key,
                )
            case "v1":
                self.session = ConfluenceSessionV1(
                    session,
                    options=self.options,
                    domain=self.properties.domain,
                    base_path=self.properties.base_path,
                    space_key=self.properties.space_key,
                )

        return self.session

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: TracebackType | None) -> None:
        """
        Closes an open connection.
        """

        if self.session is not None:
            self.session.close()
            self.session = None
