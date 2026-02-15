"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import mimetypes
import ssl
from types import TracebackType
from typing import Any, TypeVar

import requests
import truststore
from requests.adapters import HTTPAdapter

from .api_base import ConfluenceSession
from .api_v1 import ConfluenceSessionV1
from .api_v2 import ConfluenceSessionV2
from .compatibility import override
from .environment import ConnectionProperties

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


class TruststoreAdapter(HTTPAdapter):
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

        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        super().init_poolmanager(connections, maxsize, block, ssl_context=ctx, **pool_kwargs)  # type: ignore[no-untyped-call]


class ConfluenceAPI:
    """
    Encapsulates operations that can be invoked via the [Confluence REST API](https://developer.atlassian.com/cloud/confluence/rest/v2/).
    """

    properties: ConnectionProperties
    session: "ConfluenceSession | None" = None

    def __init__(self, properties: ConnectionProperties | None = None) -> None:
        self.properties = properties or ConnectionProperties()

    def __enter__(self) -> "ConfluenceSession":
        """
        Opens a connection to a Confluence server.
        """

        session = requests.Session()
        session.mount("https://", TruststoreAdapter())

        if self.properties.user_name:
            session.auth = (self.properties.user_name, self.properties.api_key)
        else:
            session.headers.update({"Authorization": f"Bearer {self.properties.api_key}"})

        if self.properties.headers:
            session.headers.update(self.properties.headers)

        match self.properties.api_version:
            case "v2":
                self.session = ConfluenceSessionV2(
                    session,
                    api_url=self.properties.api_url,
                    domain=self.properties.domain,
                    base_path=self.properties.base_path,
                    space_key=self.properties.space_key,
                )
            case "v1":
                self.session = ConfluenceSessionV1(
                    session,
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
