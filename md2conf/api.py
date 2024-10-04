import io
import json
import logging
import mimetypes
import typing
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Dict, Generator, List, Optional, Type, Union
from urllib.parse import urlencode, urlparse, urlunparse

import requests

from .converter import ParseError, sanitize_confluence
from .properties import ConfluenceError, ConfluenceProperties
from .util import removeprefix

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


@dataclass
class ConfluenceAttachment:
    id: str
    media_type: str
    file_size: int
    comment: str


@dataclass
class ConfluencePage:
    id: str
    space_key: str
    title: str
    version: int
    content: str


class ConfluenceAPI:
    properties: ConfluenceProperties
    session: Optional["ConfluenceSession"] = None

    def __init__(self, properties: Optional[ConfluenceProperties] = None) -> None:
        self.properties = properties or ConfluenceProperties()

    def __enter__(self) -> "ConfluenceSession":
        session = requests.Session()
        if self.properties.user_name:
            session.auth = (self.properties.user_name, self.properties.api_key)
        else:
            session.headers.update(
                {"Authorization": f"Bearer {self.properties.api_key}"}
            )

        if self.properties.headers:
            session.headers.update(self.properties.headers)

        self.session = ConfluenceSession(
            session,
            self.properties.domain,
            self.properties.base_path,
            self.properties.space_key,
        )
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
    base_path: str
    space_key: str

    def __init__(
        self, session: requests.Session, domain: str, base_path: str, space_key: str
    ) -> None:
        self.session = session
        self.domain = domain
        self.base_path = base_path
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
        base_url = f"https://{self.domain}{self.base_path}rest/api{path}"
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
        self, page_id: str, filename: str, *, space_key: Optional[str] = None
    ) -> ConfluenceAttachment:
        path = f"/content/{page_id}/child/attachment"
        query = {"spaceKey": space_key or self.space_key, "filename": filename}
        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))

        results = typing.cast(List[JsonType], data["results"])
        if len(results) != 1:
            raise ConfluenceError(f"no such attachment on page {page_id}: {filename}")
        result = typing.cast(Dict[str, JsonType], results[0])

        id = typing.cast(str, result["id"])
        extensions = typing.cast(Dict[str, JsonType], result["extensions"])
        media_type = typing.cast(str, extensions["mediaType"])
        file_size = typing.cast(int, extensions["fileSize"])
        comment = extensions.get("comment", "")
        comment = typing.cast(str, comment)
        return ConfluenceAttachment(id, media_type, file_size, comment)

    def upload_attachment(
        self,
        page_id: str,
        attachment_path: Path,
        attachment_name: str,
        raw_data: Optional[bytes] = None,
        comment: Optional[str] = None,
        *,
        space_key: Optional[str] = None,
        force: bool = False,
    ) -> None:
        content_type = mimetypes.guess_type(attachment_path, strict=True)[0]

        if not raw_data and not attachment_path.is_file():
            raise ConfluenceError(f"file not found: {attachment_path}")

        try:
            attachment = self.get_attachment_by_name(
                page_id, attachment_name, space_key=space_key
            )

            if not raw_data:
                if not force and attachment.file_size == attachment_path.stat().st_size:
                    LOGGER.info("Up-to-date attachment: %s", attachment_name)
                    return
            else:
                if not force and attachment.file_size == len(raw_data):
                    LOGGER.info("Up-to-date embedded image: %s", attachment_name)
                    return

            id = removeprefix(attachment.id, "att")
            path = f"/content/{page_id}/child/attachment/{id}/data"

        except ConfluenceError:
            path = f"/content/{page_id}/child/attachment"

        url = self._build_url(path)

        if not raw_data:
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
        else:
            LOGGER.info("Uploading raw data: %s", attachment_name)

            file_to_upload = {
                "comment": comment,
                "file": (
                    attachment_name,  # will truncate path component
                    io.BytesIO(raw_data),  # type: ignore
                    content_type,
                    {"Expires": "0"},
                ),
            }

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
        self._update_attachment(
            page_id, attachment_id, version, attachment_name, space_key=space_key
        )

    def _update_attachment(
        self,
        page_id: str,
        attachment_id: str,
        version: int,
        attachment_title: str,
        *,
        space_key: Optional[str] = None,
    ) -> None:
        id = removeprefix(attachment_id, "att")
        path = f"/content/{page_id}/child/attachment/{id}"
        data = {
            "id": attachment_id,
            "type": "attachment",
            "status": "current",
            "title": attachment_title,
            "space": {"key": space_key or self.space_key},
            "version": {"minorEdit": True, "number": version},
        }

        LOGGER.info("Updating attachment: %s", attachment_id)
        self._save(path, data)

    def get_page_id_by_title(
        self,
        title: str,
        *,
        space_key: Optional[str] = None,
    ) -> str:
        """
        Look up a Confluence wiki page ID by title.

        :param title: The page title.
        :param space_key: The Confluence space key (unless the default space is to be used).
        :returns: Confluence page ID.
        """

        LOGGER.info("Looking up page with title: %s", title)
        path = "/content"
        query = {"title": title, "spaceKey": space_key or self.space_key}
        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))

        results = typing.cast(List[JsonType], data["results"])
        if len(results) != 1:
            raise ConfluenceError(f"page not found with title: {title}")

        result = typing.cast(Dict[str, JsonType], results[0])
        id = typing.cast(str, result["id"])
        return id

    def get_page(
        self, page_id: str, *, space_key: Optional[str] = None
    ) -> ConfluencePage:
        """
        Retrieve Confluence wiki page details.

        :param page_id: The Confluence page ID.
        :param space_key: The Confluence space key (unless the default space is to be used).
        :returns: Confluence page info.
        """

        path = f"/content/{page_id}"
        query = {
            "spaceKey": space_key or self.space_key,
            "expand": "body.storage,version",
        }

        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))
        version = typing.cast(Dict[str, JsonType], data["version"])
        body = typing.cast(Dict[str, JsonType], data["body"])
        storage = typing.cast(Dict[str, JsonType], body["storage"])

        return ConfluencePage(
            id=page_id,
            space_key=space_key or self.space_key,
            title=typing.cast(str, data["title"]),
            version=typing.cast(int, version["number"]),
            content=typing.cast(str, storage["value"]),
        )

    def get_page_ancestors(
        self, page_id: str, *, space_key: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Retrieve Confluence wiki page ancestors.

        :param page_id: The Confluence page ID.
        :param space_key: The Confluence space key (unless the default space is to be used).
        :returns: Dictionary of ancestor page ID to title, with topmost ancestor first.
        """

        path = f"/content/{page_id}"
        query = {
            "spaceKey": space_key or self.space_key,
            "expand": "ancestors",
        }
        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))
        ancestors = typing.cast(List[JsonType], data["ancestors"])

        # from the JSON array of ancestors, extract the "id" and "title"
        results: Dict[str, str] = {}
        for node in ancestors:
            ancestor = typing.cast(Dict[str, JsonType], node)
            id = typing.cast(str, ancestor["id"])
            title = typing.cast(str, ancestor["title"])
            results[id] = title
        return results

    def get_page_version(
        self,
        page_id: str,
        *,
        space_key: Optional[str] = None,
    ) -> int:
        """
        Retrieve a Confluence wiki page version.

        :param page_id: The Confluence page ID.
        :param space_key: The Confluence space key (unless the default space is to be used).
        :returns: Confluence page version.
        """

        path = f"/content/{page_id}"
        query = {
            "spaceKey": space_key or self.space_key,
            "expand": "version",
        }
        data = typing.cast(Dict[str, JsonType], self._invoke(path, query))
        version = typing.cast(Dict[str, JsonType], data["version"])
        return typing.cast(int, version["number"])

    def update_page(
        self,
        page_id: str,
        new_content: str,
        *,
        space_key: Optional[str] = None,
    ) -> None:
        page = self.get_page(page_id, space_key=space_key)

        try:
            old_content = sanitize_confluence(page.content)
            if old_content == new_content:
                LOGGER.info("Up-to-date page: %s", page_id)
                return
        except ParseError as exc:
            LOGGER.warning(exc)

        path = f"/content/{page_id}"
        data = {
            "id": page_id,
            "type": "page",
            "title": page.title,  # title needs to be unique within a space so the original title is maintained
            "space": {"key": space_key or self.space_key},
            "body": {"storage": {"value": new_content, "representation": "storage"}},
            "version": {"minorEdit": True, "number": page.version + 1},
        }

        LOGGER.info("Updating page: %s", page_id)
        self._save(path, data)

    def create_page(
        self,
        parent_page_id: str,
        title: str,
        new_content: str,
        *,
        space_key: Optional[str] = None,
    ) -> ConfluencePage:
        path = "/content/"
        query = {
            "type": "page",
            "title": title,
            "space": {"key": space_key or self.space_key},
            "body": {"storage": {"value": new_content, "representation": "storage"}},
            "ancestors": [{"type": "page", "id": parent_page_id}],
        }

        LOGGER.info("Creating page: %s", title)

        url = self._build_url(path)
        response = self.session.post(
            url,
            data=json.dumps(query),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        data = typing.cast(Dict[str, JsonType], response.json())
        version = typing.cast(Dict[str, JsonType], data["version"])
        body = typing.cast(Dict[str, JsonType], data["body"])
        storage = typing.cast(Dict[str, JsonType], body["storage"])

        return ConfluencePage(
            id=typing.cast(str, data["id"]),
            space_key=space_key or self.space_key,
            title=typing.cast(str, data["title"]),
            version=typing.cast(int, version["number"]),
            content=typing.cast(str, storage["value"]),
        )

    def page_exists(
        self, title: str, *, space_key: Optional[str] = None
    ) -> Optional[str]:
        path = "/content"
        query = {
            "type": "page",
            "title": title,
            "spaceKey": space_key or self.space_key,
        }

        LOGGER.info("Checking if page exists with title: %s", title)

        url = self._build_url(path)
        response = self.session.get(
            url, params=query, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        data = typing.cast(Dict[str, JsonType], response.json())
        results = typing.cast(List, data["results"])

        if len(results) == 1:
            page_info = typing.cast(Dict[str, JsonType], results[0])
            return typing.cast(str, page_info["id"])
        else:
            return None

    def get_or_create_page(
        self, title: str, parent_id: str, *, space_key: Optional[str] = None
    ) -> ConfluencePage:
        page_id = self.page_exists(title)

        if page_id is not None:
            LOGGER.debug("Retrieving existing page: %d", page_id)
            return self.get_page(page_id)
        else:
            LOGGER.debug("Creating new page with title: %s", title)
            return self.create_page(parent_id, title, "", space_key=space_key)
