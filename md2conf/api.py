"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import enum
import io
import json
import logging
import mimetypes
import typing
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Optional, Union
from urllib.parse import urlencode, urlparse, urlunparse

import requests

from .converter import ParseError, sanitize_confluence
from .properties import (
    ArgumentError,
    ConfluenceConnectionProperties,
    ConfluenceError,
    PageError,
)

# a JSON type with possible `null` values
JsonType = Union[
    None,
    bool,
    int,
    float,
    str,
    dict[str, "JsonType"],
    list["JsonType"],
]


class ConfluenceVersion(enum.Enum):
    VERSION_1 = "rest/api"
    VERSION_2 = "api/v2"


class ConfluencePageParentContentType(enum.Enum):
    """
    Content types that can be a parent to a Confluence page
    """

    PAGE = "page"
    WHITEBOARD = "whiteboard"
    DATABASE = "database"
    EMBED = "embed"
    FOLDER = "folder"


def build_url(base_url: str, query: Optional[dict[str, str]] = None) -> str:
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
    space_id: str
    parent_id: str
    parent_type: Optional[ConfluencePageParentContentType]
    title: str
    version: int
    content: str


class ConfluenceAPI:
    properties: ConfluenceConnectionProperties
    session: Optional["ConfluenceSession"] = None

    def __init__(
        self, properties: Optional[ConfluenceConnectionProperties] = None
    ) -> None:
        self.properties = properties or ConfluenceConnectionProperties()

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
        exc_type: Optional[type[BaseException]],
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
    space_key: Optional[str]

    _space_id_to_key: dict[str, str]
    _space_key_to_id: dict[str, str]

    def __init__(
        self,
        session: requests.Session,
        domain: str,
        base_path: str,
        space_key: Optional[str] = None,
    ) -> None:
        self.session = session
        self.domain = domain
        self.base_path = base_path
        self.space_key = space_key

        self._space_id_to_key = {}
        self._space_key_to_id = {}

    def close(self) -> None:
        self.session.close()
        self.session = requests.Session()

    def _build_url(
        self,
        version: ConfluenceVersion,
        path: str,
        query: Optional[dict[str, str]] = None,
    ) -> str:
        """
        Builds a full URL for invoking the Confluence API.

        :param prefix: A URL path prefix that depends on the Confluence API version.
        :param path: Path of API endpoint to invoke.
        :param query: Query parameters to pass to the API endpoint.
        :returns: A full URL.
        """

        base_url = f"https://{self.domain}{self.base_path}{version.value}{path}"
        return build_url(base_url, query)

    def _invoke(
        self,
        version: ConfluenceVersion,
        path: str,
        query: Optional[dict[str, str]] = None,
    ) -> JsonType:
        "Execute an HTTP request via Confluence API."

        url = self._build_url(version, path, query)
        response = self.session.get(url)
        if response.text:
            LOGGER.debug("Received HTTP payload:\n%s", response.text)
        response.raise_for_status()
        return response.json()

    def _save(self, version: ConfluenceVersion, path: str, data: dict) -> None:
        url = self._build_url(version, path)
        response = self.session.put(
            url,
            data=json.dumps(data),
            headers={"Content-Type": "application/json"},
        )
        if response.text:
            LOGGER.debug("Received HTTP payload:\n%s", response.text)
        response.raise_for_status()

    def space_id_to_key(self, id: str) -> str:
        "Finds the Confluence space key for a space ID."

        key = self._space_id_to_key.get(id)
        if key is None:
            payload = self._invoke(
                ConfluenceVersion.VERSION_2,
                "/spaces",
                {"ids": id, "status": "current"},
            )
            payload = typing.cast(dict[str, JsonType], payload)
            results = typing.cast(list[JsonType], payload["results"])
            if len(results) != 1:
                raise ConfluenceError(f"unique space not found with id: {id}")

            result = typing.cast(dict[str, JsonType], results[0])
            key = typing.cast(str, result["key"])

            self._space_id_to_key[id] = key

        return key

    def space_key_to_id(self, key: str) -> str:
        "Finds the Confluence space ID for a space key."

        id = self._space_key_to_id.get(key)
        if id is None:
            payload = self._invoke(
                ConfluenceVersion.VERSION_2,
                "/spaces",
                {"keys": key, "status": "current"},
            )
            payload = typing.cast(dict[str, JsonType], payload)
            results = typing.cast(list[JsonType], payload["results"])
            if len(results) != 1:
                raise ConfluenceError(f"unique space not found with key: {key}")

            result = typing.cast(dict[str, JsonType], results[0])
            id = typing.cast(str, result["id"])

            self._space_key_to_id[key] = id

        return id

    def get_attachment_by_name(
        self, page_id: str, filename: str
    ) -> ConfluenceAttachment:
        path = f"/pages/{page_id}/attachments"
        query = {"filename": filename}
        data = typing.cast(
            dict[str, JsonType], self._invoke(ConfluenceVersion.VERSION_2, path, query)
        )

        results = typing.cast(list[JsonType], data["results"])
        if len(results) != 1:
            raise ConfluenceError(f"no such attachment on page {page_id}: {filename}")
        result = typing.cast(dict[str, JsonType], results[0])

        id = typing.cast(str, result["id"])
        media_type = typing.cast(str, result["mediaType"])
        file_size = typing.cast(int, result["fileSize"])
        comment = typing.cast(str, result.get("comment", ""))
        return ConfluenceAttachment(id, media_type, file_size, comment)

    def upload_attachment(
        self,
        page_id: str,
        attachment_name: str,
        *,
        attachment_path: Optional[Path] = None,
        raw_data: Optional[bytes] = None,
        content_type: Optional[str] = None,
        comment: Optional[str] = None,
        force: bool = False,
    ) -> None:
        if attachment_path is None and raw_data is None:
            raise ArgumentError("required: `attachment_path` or `raw_data`")

        if attachment_path is not None and raw_data is not None:
            raise ArgumentError("expected: either `attachment_path` or `raw_data`")

        if content_type is None:
            if attachment_path is not None:
                name = str(attachment_path)
            else:
                name = attachment_name
            content_type, _ = mimetypes.guess_type(name, strict=True)

        if attachment_path is not None and not attachment_path.is_file():
            raise PageError(f"file not found: {attachment_path}")

        try:
            attachment = self.get_attachment_by_name(page_id, attachment_name)

            if attachment_path is not None:
                if not force and attachment.file_size == attachment_path.stat().st_size:
                    LOGGER.info("Up-to-date attachment: %s", attachment_name)
                    return
            elif raw_data is not None:
                if not force and attachment.file_size == len(raw_data):
                    LOGGER.info("Up-to-date embedded image: %s", attachment_name)
                    return
            else:
                raise NotImplementedError("never occurs")

            id = attachment.id.removeprefix("att")
            path = f"/content/{page_id}/child/attachment/{id}/data"

        except ConfluenceError:
            path = f"/content/{page_id}/child/attachment"

        url = self._build_url(ConfluenceVersion.VERSION_1, path)

        if attachment_path is not None:
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
        elif raw_data is not None:
            LOGGER.info("Uploading raw data: %s", attachment_name)

            raw_file = io.BytesIO(raw_data)
            raw_file.name = attachment_name
            file_to_upload = {
                "comment": comment,
                "file": (
                    attachment_name,  # will truncate path component
                    raw_file,  # type: ignore
                    content_type,
                    {"Expires": "0"},
                ),
            }
            response = self.session.post(
                url,
                files=file_to_upload,  # type: ignore
                headers={"X-Atlassian-Token": "no-check"},
            )
        else:
            raise NotImplementedError("never occurs")

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
            "version": {"minorEdit": True, "number": version},
        }

        LOGGER.info("Updating attachment: %s", attachment_id)
        self._save(ConfluenceVersion.VERSION_1, path, data)

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
        path = "/pages"
        query = {
            "title": title,
        }
        coalesced_space_key = space_key or self.space_key
        if coalesced_space_key is not None:
            query["space-id"] = self.space_key_to_id(coalesced_space_key)

        payload = self._invoke(ConfluenceVersion.VERSION_2, path, query)
        payload = typing.cast(dict[str, JsonType], payload)

        results = typing.cast(list[JsonType], payload["results"])
        if len(results) != 1:
            raise ConfluenceError(f"unique page not found with title: {title}")

        result = typing.cast(dict[str, JsonType], results[0])
        id = typing.cast(str, result["id"])
        return id

    def get_page(self, page_id: str) -> ConfluencePage:
        """
        Retrieve Confluence wiki page details.

        :param page_id: The Confluence page ID.
        :returns: Confluence page info.
        """

        path = f"/pages/{page_id}"
        query = {"body-format": "storage"}
        payload = self._invoke(ConfluenceVersion.VERSION_2, path, query)
        data = typing.cast(dict[str, JsonType], payload)
        version = typing.cast(dict[str, JsonType], data["version"])
        body = typing.cast(dict[str, JsonType], data["body"])
        storage = typing.cast(dict[str, JsonType], body["storage"])

        return ConfluencePage(
            id=page_id,
            space_id=typing.cast(str, data["spaceId"]),
            parent_id=typing.cast(str, data["parentId"]),
            parent_type=(
                ConfluencePageParentContentType(typing.cast(str, data["parentType"]))
                if data["parentType"] is not None
                else None
            ),
            title=typing.cast(str, data["title"]),
            version=typing.cast(int, version["number"]),
            content=typing.cast(str, storage["value"]),
        )

    def get_page_version(self, page_id: str) -> int:
        """
        Retrieve a Confluence wiki page version.

        :param page_id: The Confluence page ID.
        :returns: Confluence page version.
        """

        path = f"/pages/{page_id}"
        payload = self._invoke(ConfluenceVersion.VERSION_2, path)
        data = typing.cast(dict[str, JsonType], payload)
        version = typing.cast(dict[str, JsonType], data["version"])
        return typing.cast(int, version["number"])

    def update_page(
        self,
        page_id: str,
        new_content: str,
        *,
        title: Optional[str] = None,
    ) -> None:
        """
        Update a page via the Confluence API.

        :param page_id: The Confluence page ID.
        :param new_content: Confluence Storage Format XHTML.
        :param title: New title to assign to the page. Needs to be unique within a space.
        """

        page = self.get_page(page_id)
        new_title = title or page.title

        try:
            old_content = sanitize_confluence(page.content)
            if page.title == new_title and old_content == new_content:
                LOGGER.info("Up-to-date page: %s", page_id)
                return
        except ParseError as exc:
            LOGGER.warning(exc)

        path = f"/pages/{page_id}"
        data = {
            "id": page_id,
            "status": "current",
            "title": new_title,
            "body": {"storage": {"value": new_content, "representation": "storage"}},
            "version": {"minorEdit": True, "number": page.version + 1},
        }

        LOGGER.info("Updating page: %s", page_id)
        self._save(ConfluenceVersion.VERSION_2, path, data)

    def create_page(
        self,
        parent_page_id: str,
        title: str,
        new_content: str,
        *,
        space_key: Optional[str] = None,
    ) -> ConfluencePage:
        """
        Create a new page via Confluence API.
        """

        coalesced_space_key = space_key or self.space_key
        if coalesced_space_key is None:
            raise ArgumentError("Confluence space key required for creating a new page")

        path = "/pages/"
        query = {
            "spaceId": self.space_key_to_id(coalesced_space_key),
            "status": "current",
            "title": title,
            "parentId": parent_page_id,
            "body": {"storage": {"value": new_content, "representation": "storage"}},
        }

        LOGGER.info("Creating page: %s", title)

        url = self._build_url(ConfluenceVersion.VERSION_2, path)
        response = self.session.post(
            url,
            data=json.dumps(query),
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()

        data = typing.cast(dict[str, JsonType], response.json())
        version = typing.cast(dict[str, JsonType], data["version"])
        body = typing.cast(dict[str, JsonType], data["body"])
        storage = typing.cast(dict[str, JsonType], body["storage"])

        return ConfluencePage(
            id=typing.cast(str, data["id"]),
            space_id=typing.cast(str, data["spaceId"]),
            parent_id=typing.cast(str, data["parentId"]),
            parent_type=(
                ConfluencePageParentContentType(typing.cast(str, data["parentType"]))
                if data["parentType"] is not None
                else None
            ),
            title=typing.cast(str, data["title"]),
            version=typing.cast(int, version["number"]),
            content=typing.cast(str, storage["value"]),
        )

    def delete_page(self, page_id: str, *, purge: bool = False) -> None:
        """
        Delete a page via Confluence API.

        :param page_id: The Confluence page ID.
        :param purge: True to completely purge the page, False to move to trash only.
        """

        path = f"/pages/{page_id}"

        # move to trash
        url = self._build_url(ConfluenceVersion.VERSION_2, path)
        LOGGER.info("Moving page to trash: %s", page_id)
        response = self.session.delete(url)
        response.raise_for_status()

        if purge:
            # purge from trash
            query = {"purge": "true"}
            url = self._build_url(ConfluenceVersion.VERSION_2, path, query)
            LOGGER.info("Permanently deleting page: %s", page_id)
            response = self.session.delete(url)
            response.raise_for_status()

    def page_exists(
        self, title: str, *, space_key: Optional[str] = None
    ) -> Optional[str]:
        path = "/pages"
        coalesced_space_key = space_key or self.space_key
        query = {"title": title}
        if coalesced_space_key is not None:
            query["space-id"] = self.space_key_to_id(coalesced_space_key)

        LOGGER.info("Checking if page exists with title: %s", title)

        url = self._build_url(ConfluenceVersion.VERSION_2, path)
        response = self.session.get(
            url, params=query, headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()

        data = typing.cast(dict[str, JsonType], response.json())
        results = typing.cast(list[JsonType], data["results"])

        if len(results) == 1:
            result = typing.cast(dict[str, JsonType], results[0])
            return typing.cast(str, result["id"])
        else:
            return None

    def get_or_create_page(
        self, title: str, parent_id: str, *, space_key: Optional[str] = None
    ) -> ConfluencePage:
        page_id = self.page_exists(title)

        if page_id is not None:
            LOGGER.debug("Retrieving existing page: %s", page_id)
            return self.get_page(page_id)
        else:
            LOGGER.debug("Creating new page with title: %s", title)
            return self.create_page(parent_id, title, "", space_key=space_key)
