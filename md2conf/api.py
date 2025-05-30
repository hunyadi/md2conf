"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import enum
import functools
import hashlib
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
from requests import RequestException

from .converter import ParseError, sanitize_confluence
from .metadata import ConfluenceSiteMetadata
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
    """
    Confluence REST API version an HTTP request corresponds to.

    For some operations, Confluence Cloud supports v2 endpoints exclusively. However, for other operations, only v1 endpoints are available via REST API.
    Some versions of Confluence Server and Data Center, unfortunately, don't support v2 endpoints at all.

    The principal use case for *md2conf* is Confluence Cloud. As such, *md2conf* uses v2 endpoints when available, and resorts to v1 endpoints only when
    necessary.
    """

    VERSION_1 = "rest/api"
    VERSION_2 = "api/v2"


class ConfluencePageParentContentType(enum.Enum):
    """
    Content types that can be a parent to a Confluence page.
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


@dataclass(frozen=True)
class ConfluenceAttachment:
    """
    Holds data for an object uploaded to Confluence as a page attachment.

    :param id: Unique ID for the attachment.
    :param media_type: MIME type for the attachment.
    :param file_size: Size in bytes.
    :param comment: Description for the attachment.
    """

    id: str
    media_type: str
    file_size: int
    comment: str


@dataclass(frozen=True)
class ConfluencePageProperties:
    """
    Holds Confluence page properties used for page synchronization.

    :param id: Confluence page ID.
    :param space_id: Confluence space ID.
    :param parent_id: Confluence page ID of the immediate parent.
    :param parent_type: Identifies the content type of the parent.
    :param title: Page title.
    :param version: Page version. Incremented when the page is updated.
    """

    id: str
    space_id: str
    parent_id: str
    parent_type: Optional[ConfluencePageParentContentType]
    title: str
    version: int


@dataclass(frozen=True)
class ConfluencePage(ConfluencePageProperties):
    """
    Holds Confluence page data used for page synchronization.

    :param content: Page content in Confluence Storage Format.
    """

    content: str


@dataclass(frozen=True)
class ConfluenceLabel:
    """
    Holds information about a single label.

    :param id: ID of the label.
    :param name: Name of the label.
    :param prefix: Prefix of the label.
    """

    id: str
    name: str
    prefix: str


class ConfluenceAPI:
    """
    Represents an active connection to a Confluence server.
    """

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
    """
    Information about an open session to a Confluence server.
    """

    session: requests.Session
    site: ConfluenceSiteMetadata

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
        self.site = ConfluenceSiteMetadata(domain, base_path, space_key)

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

        base_url = (
            f"https://{self.site.domain}{self.site.base_path}{version.value}{path}"
        )
        return build_url(base_url, query)

    def _invoke(
        self,
        version: ConfluenceVersion,
        path: str,
        query: Optional[dict[str, str]] = None,
    ) -> JsonType:
        "Executes an HTTP request via Confluence API."

        url = self._build_url(version, path, query)
        response = self.session.get(url)
        if response.text:
            LOGGER.debug("Received HTTP payload:\n%s", response.text)
        response.raise_for_status()
        return response.json()

    def _fetch(
        self, path: str, query: Optional[dict[str, str]] = None
    ) -> list[JsonType]:
        "Retrieves all results of a REST API v2 paginated result-set."

        items: list[JsonType] = []
        url = self._build_url(ConfluenceVersion.VERSION_2, path, query)
        while True:
            response = self.session.get(url)
            response.raise_for_status()

            payload = typing.cast(dict[str, JsonType], response.json())
            results = typing.cast(list[JsonType], payload["results"])
            items.extend(results)

            links = typing.cast(dict[str, JsonType], payload.get("_links", {}))
            link = typing.cast(str, links.get("next", ""))
            if link:
                url = f"https://{self.site.domain}{link}"
            else:
                break

        return items

    def _save(self, version: ConfluenceVersion, path: str, data: JsonType) -> None:
        "Persists data via Confluence REST API."

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

    def get_space_id(
        self, *, space_id: Optional[str] = None, space_key: Optional[str] = None
    ) -> Optional[str]:
        """
        Coalesces a space ID or space key into a space ID, accounting for site default.

        :param space_id: A Confluence space ID.
        :param space_key: A Confluence space key.
        """

        if space_id is not None and space_key is not None:
            raise ConfluenceError("either space ID or space key is required; not both")

        if space_id is not None:
            return space_id

        space_key = space_key or self.site.space_key
        if space_key is not None:
            return self.space_key_to_id(space_key)

        # space ID and key are unset, and no default space is configured
        return None

    def get_attachment_by_name(
        self, page_id: str, filename: str
    ) -> ConfluenceAttachment:
        """
        Retrieves a Confluence page attachment by an unprefixed file name.
        """

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
        """
        Uploads a new attachment to a Confluence page.

        :param page_id: Confluence page ID.
        :param attachment_name: Unprefixed name unique to the page.
        :param attachment_path: Path to the file to upload as an attachment.
        :param raw_data: Raw data to upload as an attachment.
        :param content_type: Attachment MIME type.
        :param comment: Attachment description.
        :param force: Overwrite an existing attachment even if there seem to be no changes.
        """

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
        data: JsonType = {
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
        space_id: Optional[str] = None,
        space_key: Optional[str] = None,
    ) -> str:
        """
        Looks up a Confluence wiki page ID by title.

        :param title: The page title.
        :param space_id: The Confluence space ID (unless the default space is to be used). Exclusive with space key.
        :param space_key: The Confluence space key (unless the default space is to be used). Exclusive with space ID.
        :returns: Confluence page ID.
        """

        LOGGER.info("Looking up page with title: %s", title)
        path = "/pages"
        query = {
            "title": title,
        }
        space_id = self.get_space_id(space_id=space_id, space_key=space_key)
        if space_id is not None:
            query["space-id"] = space_id

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
        Retrieves Confluence wiki page details and content.

        :param page_id: The Confluence page ID.
        :returns: Confluence page info and content.
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

    @functools.cache
    def get_page_properties(self, page_id: str) -> ConfluencePageProperties:
        """
        Retrieves Confluence wiki page details.

        :param page_id: The Confluence page ID.
        :returns: Confluence page info.
        """

        path = f"/pages/{page_id}"
        payload = self._invoke(ConfluenceVersion.VERSION_2, path)
        data = typing.cast(dict[str, JsonType], payload)
        version = typing.cast(dict[str, JsonType], data["version"])

        return ConfluencePageProperties(
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
        )

    def get_page_version(self, page_id: str) -> int:
        """
        Retrieves a Confluence wiki page version.

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
        Updates a page via the Confluence API.

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
        data: JsonType = {
            "id": page_id,
            "status": "current",
            "title": new_title,
            "body": {"storage": {"value": new_content, "representation": "storage"}},
            "version": {"minorEdit": True, "number": page.version + 1},
        }

        LOGGER.info("Updating page: %s title: %s", page_id, new_title)
        self._save(ConfluenceVersion.VERSION_2, path, data)

    def create_page(
        self,
        parent_id: str,
        title: str,
        new_content: str,
        root_dir: Path,
        absolute_path: Path,
    ) -> ConfluencePage:
        """
        Creates a new page via Confluence API.
        """

        parent_page = self.get_page_properties(parent_id)
        path = "/pages/"
        query = {
            "spaceId": parent_page.space_id,
            "status": "current",
            "title": title,
            "parentId": parent_id,
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
        page_id = typing.cast(str, data["id"])
        version = typing.cast(dict[str, JsonType], data["version"])
        body = typing.cast(dict[str, JsonType], data["body"])
        storage = typing.cast(dict[str, JsonType], body["storage"])

        self._add_metadata(page_id, root_dir, absolute_path)

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

    def get_path_digest(self, root_dir: Path, absolute_path: Path) -> str:
        """
        Calculate a digest for the relative path of a file under the root directory.
        This is used to uniquely identify the file in Confluence metadata.
        """
        relative_path = absolute_path.relative_to(root_dir.parent)
        filepath_hash = hashlib.md5(relative_path.as_posix().encode("utf-8"))
        return "".join(f"{c:x}" for c in filepath_hash.digest())

    def _add_metadata(self, page_id: str, root_dir: Path, absolute_path: Path):
        """Add metadata to Confluence page"""

        digest = self.get_path_digest(root_dir, absolute_path)

        metadata = {"key": "md2conf", "value": {
            "digest": digest,
        }}
        url = self._build_url(ConfluenceVersion.VERSION_1, f"/content/{page_id}/property")
        response = self.session.post(url, data=json.dumps(metadata), headers={"Content-Type": "application/json"})
        response.raise_for_status()
        LOGGER.info("Added metadata: %s", absolute_path)

    def delete_page(self, page_id: str, *, purge: bool = False) -> None:
        """
        Deletes a page via Confluence API.

        :param page_id: The Confluence page ID.
        :param purge: `True` to completely purge the page, `False` to move to trash only.
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
        self,
        title: str,
        *,
        space_id: Optional[str] = None,
        space_key: Optional[str] = None,
    ) -> Optional[str]:
        """
        Checks if a Confluence page exists with the given title.

        :param title: Page title. Pages in the same Confluence space must have a unique title.
        :param space_key: Identifies the Confluence space.

        :returns: Confluence page ID of a matching page (if found), or `None`.
        """

        space_id = self.get_space_id(space_id=space_id, space_key=space_key)
        path = "/pages"
        query = {"title": title}
        if space_id is not None:
            query["space-id"] = space_id

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

    def get_existing_pages(self, parent_page_id: str) -> dict[str, str]:
        """Get all existing pages under a parent page"""

        all_data = []
        start = 0
        limit = 25

        LOGGER.info("Retrieving metadata for existing pages under parent page: %s", parent_page_id)

        while True:
            try:
                query = {
                    'start': start,
                    'limit': limit,
                    'expand': 'metadata.properties.md2conf'
                }

                url = self._build_url(ConfluenceVersion.VERSION_1, f"/content/{parent_page_id}/child/page")
                response = self.session.get(
                    url, params=query, headers={"Content-Type": "application/json"}
                )

                response.raise_for_status()

                json_response = response.json()
                json_results = json_response.get('results', [])

                filtered = [
                    result for result in json_results
                    if result.get('metadata', {}).get('properties', {}).get('md2conf', {}).get('value', {}).get('digest') is not None
                ]

                all_data.extend(filtered)

                if json_response['_links'].get('next') is None:
                    break  # No more pages

                start += limit

            except RequestException as e:
                print(f"Error during API request: {e}")
                return []

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON response: {e}")
                return []

            except Exception as e:
                print(f"An unexpected error occurred: {e}")
                return []

        # Process the results
        results = {
            item['metadata']['properties']['md2conf']['value']['digest']: item['id'] for item in all_data
        }

        child_items = {}
        for page_id in results.values():
            pages = self.get_existing_pages(page_id)
            for page in pages:
                child_items[page] = pages[page]

        # Add child items to the results
        for key in child_items:
            results[key] = child_items[key]

        return results

    def get_labels(self, page_id: str) -> list[ConfluenceLabel]:
        """
        Retrieves labels for a Confluence page.

        :param page_id: The Confluence page ID.
        :returns: A list of page labels.
        """

        items: list[ConfluenceLabel] = []
        path = f"/pages/{page_id}/labels"
        results = self._fetch(path)
        for r in results:
            result = typing.cast(dict[str, JsonType], r)
            id = typing.cast(str, result["id"])
            name = typing.cast(str, result["name"])
            prefix = typing.cast(str, result["prefix"])
            items.append(ConfluenceLabel(id, name, prefix))
        return items
