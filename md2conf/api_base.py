"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import io
import logging
import mimetypes
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar, overload
from urllib.parse import urlencode, urlparse, urlunparse

import requests

from .api_types import (
    ConfluenceAttachment,
    ConfluenceContentProperty,
    ConfluenceContentVersion,
    ConfluenceIdentifiedContentProperty,
    ConfluenceIdentifiedLabel,
    ConfluenceLabel,
    ConfluenceLegacyType,
    ConfluencePage,
    ConfluencePageProperties,
    ConfluenceStatus,
    ConfluenceVersion,
)
from .environment import ArgumentError, ConfluenceError, PageError
from .metadata import ConfluenceSiteMetadata
from .serializer import JsonType, json_to_object, object_to_json_payload

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


def build_url(base_url: str, query: dict[str, str] | None = None) -> str:
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


@overload
def response_cast(response_type: None, response: requests.Response) -> None: ...


@overload
def response_cast(response_type: type[T], response: requests.Response) -> T: ...


def response_cast(response_type: type[T] | None, response: requests.Response) -> T | None:
    "Converts a response body into the expected type."

    if response.text:
        LOGGER.debug("Received HTTP payload:\n%s", response.text)
    response.raise_for_status()
    if response_type is None:
        return None
    else:
        return json_to_object(response_type, response.json())


@dataclass(frozen=True)
class ConfluenceUpdateAttachmentRequest:
    id: str
    type: ConfluenceLegacyType
    status: ConfluenceStatus
    title: str
    version: ConfluenceContentVersion


class ConfluenceSession(ABC):
    _session: requests.Session
    _api_url: str

    site: ConfluenceSiteMetadata

    def __init__(self, session: requests.Session) -> None:
        self._session = session

    def _init_site(self, *, domain: str | None, base_path: str | None, space_key: str | None) -> None:
        if not domain:
            raise ArgumentError("Confluence domain not specified and cannot be inferred")
        if not base_path:
            raise ArgumentError("Confluence base path not specified and cannot be inferred")
        self.site = ConfluenceSiteMetadata(domain, base_path, space_key)

    def close(self) -> None:
        self._session.close()
        self._session = requests.Session()

    def _build_url(self, version: ConfluenceVersion, path: str, query: dict[str, str] | None = None) -> str:
        """
        Builds a full URL for invoking the Confluence API.

        :param prefix: A URL path prefix that depends on the Confluence API version.
        :param path: Path of API endpoint to invoke.
        :param query: Query parameters to pass to the API endpoint.
        :returns: A full URL.
        """

        base_url = f"{self._api_url}{version.value}{path}"
        return build_url(base_url, query)

    def _get(self, version: ConfluenceVersion, path: str, response_type: type[T], *, query: dict[str, str] | None = None) -> T:
        "Executes an HTTP request via Confluence API."

        return self._get_impl(version, path, response_type, query=query)

    def _get_impl(
        self, version: ConfluenceVersion, path: str, response_type: type[T], *, query: dict[str, str] | None = None, headers: dict[str, str] | None = None
    ) -> T:
        url = self._build_url(version, path, query)
        if headers is None:
            headers = {}
        headers["Accept"] = "application/json"
        response = self._session.get(url, headers=headers, verify=True)
        if response.text:
            LOGGER.debug("Received HTTP payload:\n%s", response.text)
        response.raise_for_status()
        return json_to_object(response_type, response.json())

    def _build_request(self, version: ConfluenceVersion, path: str, body: Any, response_type: type[T] | None) -> tuple[str, dict[str, str], bytes]:
        "Generates URL, headers and raw payload for a typed request/response."

        url = self._build_url(version, path)
        headers = {"Content-Type": "application/json"}
        if response_type is not None:
            headers["Accept"] = "application/json"
        data = object_to_json_payload(body)
        return url, headers, data

    @overload
    def _post(self, version: ConfluenceVersion, path: str, body: Any, response_type: None) -> None: ...

    @overload
    def _post(self, version: ConfluenceVersion, path: str, body: Any, response_type: type[T]) -> T: ...

    def _post(self, version: ConfluenceVersion, path: str, body: Any, response_type: type[T] | None) -> T | None:
        "Creates a new object via Confluence REST API."

        url, headers, data = self._build_request(version, path, body, response_type)
        response = self._session.post(url, data=data, headers=headers, verify=True)
        response.raise_for_status()
        return response_cast(response_type, response)

    @overload
    def _put(self, version: ConfluenceVersion, path: str, body: Any, response_type: None) -> None: ...

    @overload
    def _put(self, version: ConfluenceVersion, path: str, body: Any, response_type: type[T]) -> T: ...

    def _put(self, version: ConfluenceVersion, path: str, body: Any, response_type: type[T] | None) -> T | None:
        "Updates an existing object via Confluence REST API."

        url, headers, data = self._build_request(version, path, body, response_type)
        response = self._session.put(url, data=data, headers=headers, verify=True)
        response.raise_for_status()
        return response_cast(response_type, response)

    def _delete(self, version: ConfluenceVersion, path: str, *, query: dict[str, str] | None = None) -> None:
        "Deletes an existing object via Confluence REST API."

        self._delete_impl(version, path, query=query)

    def _delete_impl(self, version: ConfluenceVersion, path: str, *, query: dict[str, str] | None = None, headers: dict[str, str] | None = None) -> None:
        url = self._build_url(version, path, query)
        response = self._session.delete(url, headers=headers, verify=True)
        if response.text:
            LOGGER.debug("Received HTTP payload:\n%s", response.text)
        response.raise_for_status()

    @abstractmethod
    def _fetch(self, path: str, query: dict[str, str] | None = None) -> list[JsonType]:
        "Retrieves all results of a REST API paginated result-set."
        ...

    @abstractmethod
    def space_id_to_key(self, id: str) -> str:
        "Finds the Confluence space key for a space ID."
        ...

    @abstractmethod
    def space_key_to_id(self, key: str) -> str:
        "Finds the Confluence space ID for a space key."
        ...

    @overload
    def get_space_id(self, *, space_id: str | None = None) -> str | None: ...

    @overload
    def get_space_id(self, *, space_key: str | None = None) -> str | None: ...

    def get_space_id(self, *, space_id: str | None = None, space_key: str | None = None) -> str | None:
        return self._get_space_id(space_id=space_id, space_key=space_key)

    def _get_space_id(self, *, space_id: str | None = None, space_key: str | None = None) -> str | None:
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

    @abstractmethod
    def get_homepage_id(self, space_id: str) -> str:
        """
        Returns the page ID corresponding to the space home page.

        :param space_id: The Confluence space ID.
        :returns: Page ID of the space homepage.
        """
        ...

    @abstractmethod
    def get_attachment_by_name(self, page_id: str, filename: str) -> ConfluenceAttachment:
        """
        Retrieves a Confluence page attachment by an unprefixed file name.

        :param page_id: The Confluence page ID.
        :param filename: The attachment filename to search for.
        :returns: Confluence attachment information.
        """
        ...

    def upload_attachment(
        self,
        page_id: str,
        attachment_name: str,
        *,
        attachment_path: Path | None = None,
        raw_data: bytes | None = None,
        content_type: str | None = None,
        comment: str | None = None,
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

            if content_type is None:
                content_type = "application/octet-stream"

        if attachment_path is not None and not attachment_path.is_file():
            raise PageError(f"file not found: {attachment_path}")

        try:
            attachment = self.get_attachment_by_name(page_id, attachment_name)

            if attachment_path is not None:
                if not force and attachment.fileSize == attachment_path.stat().st_size:
                    LOGGER.info("Up-to-date attachment: %s", attachment_name)
                    return
            elif raw_data is not None:
                if not force and attachment.fileSize == len(raw_data):
                    LOGGER.info("Up-to-date embedded file: %s", attachment_name)
                    return
            else:
                raise NotImplementedError("parameter match not exhaustive")

            id = attachment.id.removeprefix("att")
            path = f"/content/{page_id}/child/attachment/{id}/data"

        except ConfluenceError:
            path = f"/content/{page_id}/child/attachment"

        url = self._build_url(ConfluenceVersion.VERSION_1, path)

        if attachment_path is not None:
            with open(attachment_path, "rb") as attachment_file:
                file_to_upload: dict[str, tuple[str | None, Any, str, dict[str, str]]] = {
                    "comment": (
                        None,
                        comment,
                        "text/plain; charset=utf-8",
                        {},
                    ),
                    "file": (
                        attachment_name,  # will truncate path component
                        attachment_file,
                        content_type,
                        {"Expires": "0"},
                    ),
                }
                LOGGER.info("Uploading attachment: %s", attachment_name)
                response = self._session.post(
                    url,
                    files=file_to_upload,
                    headers={
                        "X-Atlassian-Token": "no-check",
                        "Accept": "application/json",
                    },
                    verify=True,
                )
        elif raw_data is not None:
            LOGGER.info("Uploading raw data: %s", attachment_name)

            raw_file = io.BytesIO(raw_data)
            raw_file.name = attachment_name
            file_to_upload = {
                "comment": (
                    None,
                    comment,
                    "text/plain; charset=utf-8",
                    {},
                ),
                "file": (
                    attachment_name,  # will truncate path component
                    raw_file,
                    content_type,
                    {"Expires": "0"},
                ),
            }
            response = self._session.post(
                url,
                files=file_to_upload,
                headers={
                    "X-Atlassian-Token": "no-check",
                    "Accept": "application/json",
                },
                verify=True,
            )
        else:
            raise NotImplementedError("parameter match not exhaustive")

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

    def _update_attachment(self, page_id: str, attachment_id: str, version: int, attachment_title: str) -> None:
        id = attachment_id.removeprefix("att")
        path = f"/content/{page_id}/child/attachment/{id}"
        request = ConfluenceUpdateAttachmentRequest(
            id=attachment_id,
            type=ConfluenceLegacyType.ATTACHMENT,
            status=ConfluenceStatus.CURRENT,
            title=attachment_title,
            version=ConfluenceContentVersion(number=version, minorEdit=True),
        )

        LOGGER.info("Updating attachment: %s", attachment_id)
        self._put(ConfluenceVersion.VERSION_1, path, request, None)

    @abstractmethod
    def get_page_properties_by_title(self, title: str, *, space_id: str | None = None, space_key: str | None = None) -> ConfluencePageProperties:
        """
        Looks up a Confluence wiki page ID by title.

        :param title: The page title.
        :param space_id: The Confluence space ID (unless the default space is to be used). Exclusive with space key.
        :param space_key: The Confluence space key (unless the default space is to be used). Exclusive with space ID.
        :returns: Confluence page ID.
        """
        ...

    @abstractmethod
    def get_page(self, page_id: str, *, retries: int = 3, retry_delay: float = 1.0) -> ConfluencePage:
        """
        Retrieves Confluence wiki page details and content.

        Includes retry logic to handle eventual consistency issues when fetching
        a newly created page that may not be immediately available via the API.

        :param page_id: The Confluence page ID.
        :param retries: Number of retry attempts for 404 errors (default: 3).
        :param retry_delay: Initial delay in seconds between retries, doubles each attempt (default: 1.0).
        :returns: Confluence page info and content.
        """
        ...

    @abstractmethod
    def get_page_properties(self, page_id: str) -> ConfluencePageProperties:
        """
        Retrieves Confluence wiki page details.

        :param page_id: The Confluence page ID.
        :returns: Confluence page information.
        """
        ...

    def get_page_version(self, page_id: str) -> int:
        """
        Retrieves a Confluence wiki page version.

        :param page_id: The Confluence page ID.
        :returns: Confluence page version.
        """

        return self.get_page_properties(page_id).version.number

    @abstractmethod
    def update_page(self, page_id: str, content: str, *, title: str, version: int, message: str) -> None: ...
    @abstractmethod
    def create_page(self, *, title: str, content: str, parent_id: str, space_id: str) -> ConfluencePage: ...
    @abstractmethod
    def delete_page(self, page_id: str, *, purge: bool = False) -> None: ...

    @abstractmethod
    def page_exists(self, title: str, *, space_id: str | None = None) -> str | None:
        """
        Checks if a Confluence page exists with the given title.

        :param title: Page title. Pages in the same Confluence space must have a unique title.
        :param space_id: Identifies the Confluence space.
        :returns: Confluence page ID of a matching page (if found), or `None`.
        """
        ...

    def get_or_create_page(self, title: str, parent_id: str) -> ConfluencePage:
        """
        Finds a page with the given title, or creates a new page if no such page exists.

        :param title: Page title. Pages in the same Confluence space must have a unique title.
        :param parent_id: Identifies the parent page for a new child page.
        :returns: Confluence page info for the found or newly created page.
        """

        parent_page = self.get_page_properties(parent_id)
        space_id = parent_page.spaceId
        page_id = self.page_exists(title, space_id=space_id)

        if page_id is not None:
            LOGGER.debug("Retrieving existing page: %s", page_id)
            return self.get_page(page_id)
        else:
            LOGGER.debug("Creating new page with title: %s", title)
            return self.create_page(title=title, content="", parent_id=parent_id, space_id=space_id)

    @abstractmethod
    def get_labels(self, page_id: str) -> list[ConfluenceIdentifiedLabel]:
        """
        Retrieves labels for a Confluence page.

        :param page_id: The Confluence page ID.
        :returns: A list of page labels.
        """
        ...

    def add_labels(self, page_id: str, labels: list[ConfluenceLabel]) -> None:
        """
        Adds labels to a Confluence page.

        :param page_id: The Confluence page ID.
        :param labels: A list of page labels to add.
        """

        path = f"/content/{page_id}/label"
        self._post(ConfluenceVersion.VERSION_1, path, labels, None)

    def remove_labels(self, page_id: str, labels: list[ConfluenceLabel]) -> None:
        """
        Removes labels from a Confluence page.

        :param page_id: The Confluence page ID.
        :param labels: A list of page labels to remove.
        """

        path = f"/content/{page_id}/label"
        for label in labels:
            self._delete(ConfluenceVersion.VERSION_1, path, query={"name": label.name})

    def update_labels(self, page_id: str, labels: list[ConfluenceLabel], *, keep_existing: bool = False) -> None:
        """
        Assigns the specified labels to a Confluence page. Existing labels are removed.

        :param page_id: The Confluence page ID.
        :param labels: A list of page labels to assign.
        """

        new_labels = set(labels)
        old_labels = set(ConfluenceLabel(name=label.name, prefix=label.prefix) for label in self.get_labels(page_id))

        add_labels = list(new_labels - old_labels)
        remove_labels = list(old_labels - new_labels)

        if add_labels:
            add_labels.sort()
            self.add_labels(page_id, add_labels)
        if not keep_existing and remove_labels:
            remove_labels.sort()
            self.remove_labels(page_id, remove_labels)

    @abstractmethod
    def get_content_property_for_page(self, page_id: str, key: str) -> ConfluenceIdentifiedContentProperty | None:
        """
        Retrieves a content property for a Confluence page.

        :param page_id: The Confluence page ID.
        :param key: The name of the property to fetch (with case-sensitive match).
        :returns: The content property value, or `None` if not found.
        """
        ...

    @abstractmethod
    def get_content_properties_for_page(self, page_id: str) -> list[ConfluenceIdentifiedContentProperty]:
        """
        Retrieves content properties for a Confluence page.

        :param page_id: The Confluence page ID.
        :returns: A list of content properties.
        """
        ...

    @abstractmethod
    def add_content_property_to_page(self, page_id: str, property: ConfluenceContentProperty) -> ConfluenceIdentifiedContentProperty:
        """
        Adds a new content property to a Confluence page.

        :param page_id: The Confluence page ID.
        :param property: Content property to add.
        :returns: The created content property with ID and version.
        """
        ...

    @abstractmethod
    def remove_content_property_from_page(self, page_id: str, property_id: str) -> None:
        """
        Removes a content property from a Confluence page.

        :param page_id: The Confluence page ID.
        :param property_id: Property ID, which uniquely identifies the property.
        """
        ...

    @abstractmethod
    def update_content_property_for_page(
        self, page_id: str, property_id: str, version: int, property: ConfluenceContentProperty
    ) -> ConfluenceIdentifiedContentProperty:
        """
        Updates an existing content property associated with a Confluence page.

        :param page_id: The Confluence page ID.
        :param property_id: Property ID, which uniquely identifies the property.
        :param version: Version number to assign.
        :param property: Content property data to assign.
        :returns: Updated content property data.
        """
        ...

    def update_content_properties_for_page(self, page_id: str, properties: list[ConfluenceContentProperty], *, keep_existing: bool = False) -> None:
        """
        Updates content properties associated with a Confluence page.

        :param page_id: The Confluence page ID.
        :param properties: A list of content property data to update.
        :param keep_existing: Whether to keep content property data whose key is not included in the list of properties passed as an argument.
        """

        old_mapping = {p.key: p for p in self.get_content_properties_for_page(page_id)}
        new_mapping = {p.key: p for p in properties}

        new_props = set(p.key for p in properties)
        old_props = set(old_mapping.keys())

        add_props = list(new_props - old_props)
        remove_props = list(old_props - new_props)
        update_props = list(old_props & new_props)

        if add_props:
            add_props.sort()
            for key in add_props:
                self.add_content_property_to_page(page_id, new_mapping[key])
        if not keep_existing and remove_props:
            remove_props.sort()
            for key in remove_props:
                self.remove_content_property_from_page(page_id, old_mapping[key].id)
        if update_props:
            update_props.sort()
            for key in update_props:
                old_prop = old_mapping[key]
                new_prop = new_mapping[key]
                if old_prop.value == new_prop.value:
                    continue
                self.update_content_property_for_page(page_id, old_prop.id, old_prop.version.number + 1, new_prop)
