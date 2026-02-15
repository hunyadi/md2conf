"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import datetime
import logging
import random
import time
from dataclasses import dataclass
from typing import TypeVar, cast

import requests

from .api_base import ConfluenceSession
from .api_types import (
    ConfluenceAttachment,
    ConfluenceContentProperty,
    ConfluenceContentVersion,
    ConfluenceIdentifiedContentProperty,
    ConfluenceIdentifiedLabel,
    ConfluencePage,
    ConfluencePageBody,
    ConfluencePageParentContentType,
    ConfluencePageProperties,
    ConfluencePageStorage,
    ConfluenceRepresentation,
    ConfluenceStatus,
    ConfluenceVersion,
    ConfluenceVersionedContentProperty,
)
from .compatibility import override
from .environment import ConfluenceError
from .serializer import JsonType, json_to_object

LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class ConfluenceSpace:
    key: str


@dataclass(frozen=True)
class ConfluencePageRef:
    id: str


@dataclass(frozen=True)
class ConfluencePagePropertiesV1:
    id: str
    status: ConfluenceStatus
    title: str
    space: ConfluenceSpace
    version: ConfluenceContentVersion
    ancestors: list[ConfluencePageRef]


@dataclass(frozen=True)
class ConfluencePageV1(ConfluencePagePropertiesV1):
    body: ConfluencePageBody


@dataclass(frozen=True)
class ConfluenceAttachmentExtensions:
    comment: str | None = None
    mediaType: str = "application/octet-stream"
    fileSize: int = 0


@dataclass(frozen=True)
class ConfluenceAttachmentMetadata:
    comment: str | None = None


@dataclass(frozen=True)
class ConfluenceAttachmentLinks:
    webui: str = ""
    download: str = ""


@dataclass(frozen=True)
class ConfluenceAttachmentV1:
    id: str
    status: ConfluenceStatus
    title: str | None
    extensions: ConfluenceAttachmentExtensions
    metadata: ConfluenceAttachmentMetadata
    _links: ConfluenceAttachmentLinks


@dataclass(frozen=True)
class ConfluenceUpdatePageRequestV1:
    id: str
    type: str
    title: str
    space: ConfluenceSpace
    body: ConfluencePageBody
    version: ConfluenceContentVersion


@dataclass(frozen=True)
class ConfluenceCreatePageRequestV1:
    type: str
    title: str
    space: ConfluenceSpace
    body: ConfluencePageBody
    ancestors: list[ConfluencePageRef]


class ConfluenceSessionV1(ConfluenceSession):
    """
    Represents an active connection to a Confluence server.

    Start a Confluence container:
    ```
    docker run -d -p 8090:8090 atlassian/confluence
    ```
    """

    def __init__(self, session: requests.Session, *, domain: str | None, base_path: str | None, space_key: str | None) -> None:
        super().__init__(session)
        self._init_site(domain=domain, base_path=base_path, space_key=space_key)

        LOGGER.info("Configuring classic Confluence REST API URL")
        self._api_url = f"https://{self.site.domain}{self.site.base_path}"
        LOGGER.info("Configured classic Confluence REST API URL: %s", self._api_url)

        # many Confluence Data Center/Server versions are buggy, they require a `Content-Type` header even though an HTTP GET or DELETE request has no payload
        self._session.headers.update({"Content-Type": "application/json"})

    @override
    def _fetch(self, path: str, query: dict[str, str] | None = None) -> list[JsonType]:
        "Retrieves all results of a REST API v1 paginated result-set."

        items: list[JsonType] = []

        # offset-based pagination with start and limit parameters
        start = 0
        limit = 50

        while True:
            page_query = dict(query) if query else {}
            page_query["start"] = str(start)
            page_query["limit"] = str(limit)

            data = self._get(ConfluenceVersion.VERSION_1, path, dict[str, JsonType], query=page_query)
            results = cast(list[JsonType], data["results"])
            items.extend(results)

            # End pagination when we receive fewer results than the limit
            if len(results) < limit:
                break

            start += limit

        return items

    @override
    def space_id_to_key(self, id: str) -> str:
        return id

    @override
    def space_key_to_id(self, key: str) -> str:
        return key

    def optional_space_id_to_key(self, space_id: str | None) -> str:
        if space_id is not None:
            return self.space_id_to_key(space_id)
        elif self.site.space_key is not None:
            return self.site.space_key
        else:
            return ""

    @override
    def get_homepage_id(self, space_id: str) -> str:
        path = f"/space/{self.space_id_to_key(space_id)}"
        query = {"expand": "homepage"}
        data = self._get(ConfluenceVersion.VERSION_1, path, dict[str, JsonType], query=query)

        homepage_data = cast(dict[str, JsonType], data.get("homepage", {}))
        return cast(str, homepage_data["id"])

    @override
    def get_attachment_by_name(self, page_id: str, filename: str) -> ConfluenceAttachment:
        path = f"/content/{page_id}/child/attachment"
        query = {"filename": filename}
        data = self._get(ConfluenceVersion.VERSION_1, path, dict[str, JsonType], query=query)

        results = cast(list[JsonType], data["results"])
        if len(results) != 1:
            raise ConfluenceError(f"no such attachment on page {page_id}: {filename}")
        attachment = json_to_object(ConfluenceAttachmentV1, results[0])
        return self._parse_attachment(page_id, attachment)

    def _parse_attachment(self, page_id: str, att: ConfluenceAttachmentV1) -> ConfluenceAttachment:
        """
        Parses an API v1 attachment response into an attachment object.
        """

        # Get comment from extensions or metadata
        comment = att.extensions.comment or att.metadata.comment

        # v1 doesn't always include createdAt in attachment responses
        created_at = datetime.datetime.now()

        return ConfluenceAttachment(
            id=att.id,
            status=att.status,
            title=att.title,
            createdAt=created_at,
            pageId=page_id,  # v1 doesn't include pageId in response, use parameter
            mediaType=att.extensions.mediaType,
            mediaTypeDescription=None,  # v1 doesn't include this
            comment=comment,
            fileId=att.id,  # v1 uses same ID for file and attachment
            fileSize=att.extensions.fileSize,
            webuiLink=att._links.webui,  # pyright: ignore[reportPrivateUsage]
            downloadLink=att._links.download,  # pyright: ignore[reportPrivateUsage]
            version=ConfluenceContentVersion(
                number=1,  # v1 doesn't include version in basic attachment response
                minorEdit=False,
            ),
        )

    @override
    def get_page_properties_by_title(self, title: str, *, space_id: str | None = None, space_key: str | None = None) -> ConfluencePageProperties:
        LOGGER.info("Looking up page with title: %s", title)
        space_id = self._get_space_id(space_id=space_id, space_key=space_key)
        path = "/content"
        query = {"title": title, "type": "page", "spaceKey": space_key or "", "expand": "space,version,ancestors"}

        data = self._get(ConfluenceVersion.VERSION_1, path, dict[str, JsonType], query=query)
        results = cast(list[JsonType], data["results"])

        if len(results) != 1:
            raise ConfluenceError(f"unique page not found with title: {title}")

        page = json_to_object(ConfluencePagePropertiesV1, results[0])
        return self._parse_page_properties(page)

    @override
    def get_page(self, page_id: str, *, retries: int = 3, retry_delay: float = 1.0) -> ConfluencePage:
        path = f"/content/{page_id}"
        query = {"expand": "body.storage,version,space,ancestors"}

        last_error: requests.HTTPError | None = None
        for attempt in range(retries + 1):
            try:
                page = self._get(ConfluenceVersion.VERSION_1, path, ConfluencePageV1, query=query)
                return self._parse_page(page)
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404 and attempt < retries:
                    delay = retry_delay * (2**attempt) + random.uniform(0, 1)
                    LOGGER.debug("Page %s not found, retrying in %.1f seconds (attempt %d/%d)", page_id, delay, attempt + 1, retries)
                    time.sleep(delay)
                    last_error = e
                else:
                    raise

        if last_error is not None:
            raise last_error
        raise ConfluenceError(f"failed to get page: {page_id}")

    def _parse_page(self, page: ConfluencePageV1) -> ConfluencePage:
        """
        Parses a REST API v1 page response into a page data-class object.

        :param page: Page response from REST API v1.
        :returns: Page object.
        """

        parent_id = page.ancestors[-1].id if page.ancestors else None
        return ConfluencePage(
            id=page.id,
            status=page.status,
            title=page.title,
            spaceId=self.space_key_to_id(page.space.key),
            parentId=parent_id,
            parentType=ConfluencePageParentContentType.PAGE if parent_id else None,
            position=None,
            authorId="",  # REST API v1 doesn't include this in basic response
            ownerId="",
            lastOwnerId=None,
            createdAt=datetime.datetime.now(),  # REST API v1 doesn't include this in basic response
            version=page.version,
            body=page.body,
        )

    def _parse_page_properties(self, page: ConfluencePagePropertiesV1) -> ConfluencePageProperties:
        """
        Parses a REST API v1 page details response into a page properties data-class object.

        :param page: Page details response from REST API v1.
        :returns: Page properties without body content.
        """

        parent_id = page.ancestors[-1].id if page.ancestors else None
        return ConfluencePageProperties(
            id=page.id,
            status=page.status,
            title=page.title,
            spaceId=self.space_key_to_id(page.space.key),
            parentId=parent_id,
            parentType=ConfluencePageParentContentType.PAGE if parent_id else None,
            position=None,
            authorId="",  # REST API v1 doesn't include this in basic response
            ownerId="",
            lastOwnerId=None,
            createdAt=datetime.datetime.now(),  # REST API v1 doesn't include this in basic response
            version=page.version,
        )

    @override
    def get_page_properties(self, page_id: str) -> ConfluencePageProperties:
        path = f"/content/{page_id}"
        query = {"expand": "space,version,ancestors"}

        page = self._get(ConfluenceVersion.VERSION_1, path, ConfluencePagePropertiesV1, query=query)
        return self._parse_page_properties(page)

    @override
    def update_page(self, page_id: str, content: str, *, title: str, version: int, message: str) -> None:
        """
        Updates a page using the Confluence REST API v1.

        :param page_id: The Confluence page ID.
        :param content: Confluence Storage Format XHTML.
        :param title: New title to assign to the page. Needs to be unique within a space.
        :param version: New version to assign to the page.
        :param message: Version message.
        """

        LOGGER.info("Updating page: %s", page_id)
        path = f"/content/{page_id}"
        body = ConfluenceUpdatePageRequestV1(
            id=page_id,
            type="page",
            title=title,
            space=ConfluenceSpace(key=self.site.space_key or ""),
            body=ConfluencePageBody(storage=ConfluencePageStorage(representation=ConfluenceRepresentation.STORAGE, value=content)),
            version=ConfluenceContentVersion(number=version, minorEdit=True),
        )
        self._put(ConfluenceVersion.VERSION_1, path, body, None)

    @override
    def create_page(self, *, title: str, content: str, parent_id: str, space_id: str | None = None) -> ConfluencePage:
        """
        Creates a new page using Confluence REST API v1.
        ```

        :param title: Page title.
        :param content: Page content in Confluence Storage Format.
        :param parent_id: Parent page ID.
        :param space_id: Space ID.
        :returns: Details about the newly created page.
        """

        LOGGER.info("Creating page: %s", title)

        space_key = self.optional_space_id_to_key(space_id)
        path = "/content"
        body = ConfluenceCreatePageRequestV1(
            type="page",
            title=title,
            space=ConfluenceSpace(key=space_key),
            body=ConfluencePageBody(storage=ConfluencePageStorage(representation=ConfluenceRepresentation.STORAGE, value=content)),
            ancestors=[ConfluencePageRef(id=parent_id)],
        )
        page = self._post(ConfluenceVersion.VERSION_1, path, body, ConfluencePageV1)
        return self._parse_page(page)

    @override
    def delete_page(self, page_id: str, *, purge: bool = False) -> None:
        """
        Deletes a page using Confluence REST API v1.

        API v1 endpoint: DELETE /rest/api/content/{id} - moves to trash
        API v1 endpoint: DELETE /rest/api/content/{id}?status=trashed - purges from trash

        :param page_id: The Confluence page ID.
        :param purge: `True` to completely purge the page, `False` to move to trash only.
        """

        path = f"/content/{page_id}"

        if purge:
            # Move to trash
            LOGGER.info("Moving page to trash: %s", page_id)
            self._delete(ConfluenceVersion.VERSION_1, path)

            # Purge from trash
            LOGGER.info("Permanently deleting page: %s", page_id)
            self._delete(ConfluenceVersion.VERSION_1, path, query={"status": "trashed"})
        else:
            # Just move to trash
            LOGGER.info("Moving page to trash: %s", page_id)
            self._delete(ConfluenceVersion.VERSION_1, path)

    @override
    def page_exists(self, title: str, *, space_id: str | None = None) -> str | None:
        space_key = self.optional_space_id_to_key(space_id)
        path = "/content"
        query = {"title": title, "type": "page", "spaceKey": space_key}

        LOGGER.info("Checking if page exists with title: %s", title)

        data = self._get(ConfluenceVersion.VERSION_1, path, dict[str, JsonType], query=query)
        results = cast(list[JsonType], data["results"])

        if len(results) == 1:
            result = cast(dict[str, JsonType], results[0])
            return cast(str, result["id"])
        else:
            return None

    @override
    def get_labels(self, page_id: str) -> list[ConfluenceIdentifiedLabel]:
        path = f"/content/{page_id}/label"
        results = self._fetch(path)
        return json_to_object(list[ConfluenceIdentifiedLabel], results)

    @override
    def get_content_property_for_page(self, page_id: str, key: str) -> ConfluenceIdentifiedContentProperty | None:
        path = f"/content/{page_id}/property/{key}"
        try:
            return self._get(ConfluenceVersion.VERSION_1, path, ConfluenceIdentifiedContentProperty)
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    @override
    def get_content_properties_for_page(self, page_id: str) -> list[ConfluenceIdentifiedContentProperty]:
        path = f"/content/{page_id}/property"
        results = self._fetch(path)
        return json_to_object(list[ConfluenceIdentifiedContentProperty], results)

    @override
    def add_content_property_to_page(self, page_id: str, property: ConfluenceContentProperty) -> ConfluenceIdentifiedContentProperty:
        path = f"/content/{page_id}/property"
        return self._post(ConfluenceVersion.VERSION_1, path, property, ConfluenceIdentifiedContentProperty)

    @override
    def remove_content_property_from_page(self, page_id: str, property_id: str) -> None:
        # For v1, we need to get the property first to find its key
        # since v1 uses key-based deletion, not ID-based
        # We'll need to fetch all properties and find the one with matching ID
        properties = self.get_content_properties_for_page(page_id)
        property_key = None
        for prop in properties:
            if prop.id == property_id:
                property_key = prop.key
                break
        if property_key is None:
            raise ConfluenceError(f"Property with ID {property_id} not found on page {page_id}")
        self._delete_content_property(page_id, property_key)

    def _delete_content_property(self, page_id: str, property_key: str) -> None:
        """
        Removes a content property from a Confluence page using API v1.

        API v1 endpoint: DELETE /rest/api/content/{pageId}/property/{key}

        :param page_id: The Confluence page ID.
        :param property_key: Property key, which uniquely identifies the property.
        """

        path = f"/content/{page_id}/property/{property_key}"
        self._delete(ConfluenceVersion.VERSION_1, path)

    @override
    def update_content_property_for_page(
        self, page_id: str, property_id: str, version: int, property: ConfluenceContentProperty
    ) -> ConfluenceIdentifiedContentProperty:
        path = f"/content/{page_id}/property/{property.key}"
        return self._put(
            ConfluenceVersion.VERSION_1,
            path,
            ConfluenceVersionedContentProperty(key=property.key, value=property.value, version=ConfluenceContentVersion(number=version)),
            ConfluenceIdentifiedContentProperty,
        )
