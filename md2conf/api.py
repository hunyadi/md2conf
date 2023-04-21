import json
import logging
import mimetypes
import os
import os.path
import typing
from contextlib import contextmanager
from dataclasses import dataclass
from types import TracebackType
from typing import Dict, Generator, List, Optional, Type, Union
from urllib.parse import urlencode, urlparse, urlunparse

import requests

from .converter import ParseError, sanitize_confluence

# a JSON type with possible `null` values
JsonType = Union[
    None,
    bool,
    int,
    float,
    str,
    Dict[str, "JsonType"],
    List["JsonType"],
]


def build_url(base_url: str, query: Optional[Dict[str, str]] = None) -> str:
    "Builds a URL with scheme, host, port, path and query string parameters."

    scheme, netloc, path, params, query_str, fragment = urlparse(base_url)

    if params:
        raise ValueError("expected: url with no parameters")
    if query_str:
        raise ValueError("expected: url with no query string")
    if fragment:
        raise ValueError("expected: url with no fragment")

    url_parts = (scheme, netloc, path, None, urlencode(query) if query else None, None)
    return urlunparse(url_parts)


LOGGER = logging.getLogger(__name__)


class ConfluenceError(RuntimeError):
    pass


@dataclass
class ConfluenceAttachment:
    id: str
    media_type: str
    file_size: int
    comment: str


@dataclass
class ConfluencePage:
    id: str
    title: str
    version: int
    content: str


class ConfluenceAPI:
    domain: str
    space_key: str
    user_name: str
    api_key: str

    session: Optional["ConfluenceSession"] = None

    def __init__(
        self,
        domain: Optional[str] = None,
        user_name: Optional[str] = None,
        api_key: Optional[str] = None,
        space_key: Optional[str] = None,
    ) -> None:
        opt_domain = domain or os.getenv("CONFLUENCE_DOMAIN")
        opt_user_name = user_name or os.getenv("CONFLUENCE_USER_NAME")
        opt_api_key = api_key or os.getenv("CONFLUENCE_API_KEY")
        opt_space_key = space_key or os.getenv("CONFLUENCE_SPACE_KEY")

        if not opt_domain:
            raise ConfluenceError("Confluence domain not specified")
        if not opt_user_name:
            raise ConfluenceError("Confluence user name not specified")
        if not opt_api_key:
            raise ConfluenceError("Confluence API key not specified")
        if not opt_space_key:
            raise ConfluenceError("Confluence space key not specified")

        if opt_domain.startswith(("http://", "https://")):
            raise ConfluenceError(
                "Confluence domain looks like a URL; only host name required"
            )

        self.domain = opt_domain
        self.user_name = opt_user_name
        self.api_key = opt_api_key
        self.space_key = opt_space_key

    def __enter__(self) -> "ConfluenceSession":
        session = requests.Session()
        session.auth = (self.user_name, self.api_key)
        self.session = ConfluenceSession(session, self.domain, self.space_key)
        return self.session

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if self.session is not None:
            self.session.close()
            self.session = None


class ConfluenceSession:
    session: requests.Session
    domain: str
    space_key: str

    def __init__(self, session: requests.Session, domain: str, space_key: str) -> None:
        self.session = session
        self.domain = domain
        self.space_key = space_key

    def close(self) -> None:
        self.session.close()

    @contextmanager
    def switch_space(self, new_space_key: str) -> Generator[None, None, None]:
        old_space_key = self.space_key
        self.space_key = new_space_key
        try:
            yield
        finally:
            self.space_key = old_space_key

    def _build_url(self, path: str, query: Optional[Dict[str, str]] = None) -> str:
        base_url = f"https://{self.domain}/wiki/rest/api{path}"
        return build_url(base_url, query)

    def _invoke(self, path: str, query: Dict[str, str]) -> JsonType:
        url = self._build_url(path, query)
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def _save(self, path: str, data: dict) -> None:
        url = self._build_url(path)
        response = self.session.put(
            url,
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

    def get_attachment_by_name(
        self, page_id: str, filename: str
    ) -> ConfluenceAttachment:
        path = f"/content/{page_id}/child/attachment"
        query = {"spaceKey": self.space_key, "filename": filename}
        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))

        results = typing.cast(List[JsonType], data["results"])
        if len(results) != 1:
            raise ConfluenceError(f"no such attachment on page {page_id}: {filename}")
        result = typing.cast(Dict[str, JsonType], results[0])

        id = typing.cast(str, result["id"])
        extensions = typing.cast(Dict[str, JsonType], result["extensions"])
        media_type = typing.cast(str, extensions["mediaType"])
        file_size = typing.cast(int, extensions["fileSize"])
        comment = typing.cast(str, extensions["comment"])
        return ConfluenceAttachment(id, media_type, file_size, comment)

    def upload_attachment(
        self,
        page_id: str,
        attachment_path: str,
        attachment_name: str,
        comment: Optional[str] = None,
    ) -> None:
        content_type = mimetypes.guess_type(attachment_path, strict=True)[0]

        if not os.path.isfile(attachment_path):
            raise ConfluenceError(f"file not found: {attachment_path}")

        try:
            attachment = self.get_attachment_by_name(page_id, attachment_name)

            if attachment.file_size == os.path.getsize(attachment_path):
                LOGGER.info("Up-to-date attachment: %s", attachment_name)
                return

            id = attachment.id.removeprefix("att")
            path = f"/content/{page_id}/child/attachment/{id}/data"

        except ConfluenceError:
            path = f"/content/{page_id}/child/attachment"

        url = self._build_url(path)

        with open(attachment_path, "rb") as attachment_file:
            file_to_upload = {
                "comment": comment,
                "file": (
                    attachment_name,  # will truncate path component
                    attachment_file,
                    content_type,
                    {"Expires": "0"},
                ),
            }
            LOGGER.info("Uploading attachment: %s", attachment_name)
            response = self.session.post(
                url,
                files=file_to_upload,  # type: ignore
                headers={"X-Atlassian-Token": "no-check"},
            )

        response.raise_for_status()
        data = response.json()

        if "results" in data:
            result = data["results"][0]
        else:
            result = data

        attachment_id = result["id"]
        version = result["version"]["number"] + 1

        # ensure path component is retained in attachment name
        self._update_attachment(page_id, attachment_id, version, attachment_name)

    def _update_attachment(
        self, page_id: str, attachment_id: str, version: int, attachment_title: str
    ) -> None:
        id = attachment_id.removeprefix("att")
        path = f"/content/{page_id}/child/attachment/{id}"
        data = {
            "id": attachment_id,
            "type": "attachment",
            "status": "current",
            "title": attachment_title,
            "space": {"key": self.space_key},
            "version": {"minorEdit": True, "number": version},
        }

        LOGGER.info("Updating attachment: %s", attachment_id)
        self._save(path, data)

    def get_page_id_by_title(self, title: str) -> str:
        """
        Retrieve a Confluence wiki page details by title.

        :param title: The page title.
        :returns: Confluence page info.
        """

        LOGGER.info("Looking up page with title: %s", title)
        path = "/content"
        query = {"title": title, "spaceKey": self.space_key}
        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))

        results = typing.cast(List[JsonType], data["results"])
        if len(results) != 1:
            raise ConfluenceError(f"page not found with title: {title}")

        result = typing.cast(Dict[str, JsonType], results[0])
        id = typing.cast(str, result["id"])
        return id

    def get_page(self, page_id: str) -> ConfluencePage:
        path = f"/content/{page_id}"
        query = {
            "spaceKey": self.space_key,
            "expand": "body.storage,version",
        }
        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))
        version = typing.cast(Dict[str, JsonType], data["version"])
        body = typing.cast(Dict[str, JsonType], data["body"])
        storage = typing.cast(Dict[str, JsonType], body["storage"])

        return ConfluencePage(
            id=page_id,
            title=typing.cast(str, data["title"]),
            version=typing.cast(int, version["number"]),
            content=typing.cast(str, storage["value"]),
        )

    def get_page_version(self, page_id: str) -> int:
        path = f"/content/{page_id}"
        query = {
            "spaceKey": self.space_key,
            "expand": "version",
        }
        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))
        version = typing.cast(Dict[str, JsonType], data["version"])
        return typing.cast(int, version["number"])

    def update_page(self, page_id: str, new_content: str) -> None:
        page = self.get_page(page_id)

        try:
            old_content = sanitize_confluence(page.content)
            if old_content == new_content:
                LOGGER.info("Up-to-date page: %s", page_id)
                return
        except ParseError:
            pass

        path = f"/content/{page_id}"
        data = {
            "id": page_id,
            "type": "page",
            "title": page.title,
            "space": {"key": self.space_key},
            "body": {"storage": {"value": new_content, "representation": "storage"}},
            "version": {"minorEdit": True, "number": page.version + 1},
        }

        LOGGER.info("Updating page: %s", page_id)
        self._save(path, data)
