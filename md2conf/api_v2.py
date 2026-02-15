"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import random
import time
import typing
from dataclasses import dataclass
from urllib.parse import urlparse

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
    ConfluencePageProperties,
    ConfluencePageStorage,
    ConfluenceRepresentation,
    ConfluenceResultSet,
    ConfluenceStatus,
    ConfluenceVersion,
    ConfluenceVersionedContentProperty,
)
from .compatibility import override
from .environment import ConfluenceError
from .serializer import JsonType, json_to_object

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfluenceCreatePageRequest:
    spaceId: str
    status: ConfluenceStatus | None
    title: str | None
    parentId: str | None
    body: ConfluencePageBody


@dataclass(frozen=True)
class ConfluenceUpdatePageRequest:
    id: str
    status: ConfluenceStatus
    title: str
    body: ConfluencePageBody
    version: ConfluenceContentVersion


class ConfluenceSessionV2(ConfluenceSession):
    """
    Represents an active connection to a Confluence server.
    """

    _space_id_to_key: dict[str, str]
    _space_key_to_id: dict[str, str]

    def __init__(self, session: requests.Session, *, api_url: str | None, domain: str | None, base_path: str | None, space_key: str | None) -> None:
        super().__init__(session)
        self._space_id_to_key = {}
        self._space_key_to_id = {}

        if api_url:
            self._api_url = api_url

            if not domain or not base_path:
                data = self._get(ConfluenceVersion.VERSION_2, "/spaces", ConfluenceResultSet, query={"limit": "1"})
                base_url = data._links.base  # pyright: ignore[reportPrivateUsage]

                _, domain, base_path, _, _, _ = urlparse(base_url)
                if not base_path.endswith("/"):
                    base_path = f"{base_path}/"

        self._init_site(domain=domain, base_path=base_path, space_key=space_key)

        if not api_url:
            # try to discover Cloud ID for scoped token support
            LOGGER.info("Discovering Confluence REST API URL")
            try:
                # obtain cloud ID to build URL for access with scoped token
                response = self._session.get(f"https://{self.site.domain}/_edge/tenant_info", headers={"Accept": "application/json"}, verify=True)
                if response.text:
                    LOGGER.debug("Received HTTP payload:\n%s", response.text)
                response.raise_for_status()
                cloud_id = response.json()["cloudId"]

                # try next-generation REST API URL
                LOGGER.info("Probing scoped Confluence REST API URL")
                self._api_url = f"https://api.atlassian.com/ex/confluence/{cloud_id}/"
                url = self._build_url(ConfluenceVersion.VERSION_2, "/spaces", {"limit": "1"})
                response = self._session.get(url, headers={"Accept": "application/json"}, verify=True)
                if response.text:
                    LOGGER.debug("Received HTTP payload:\n%s", response.text)
                response.raise_for_status()

                LOGGER.info("Configured scoped Confluence REST API URL: %s", self._api_url)
            except requests.exceptions.HTTPError:
                # fall back to classic REST API URL
                self._api_url = f"https://{self.site.domain}{self.site.base_path}"
                LOGGER.info("Configured classic Confluence REST API URL: %s", self._api_url)

    @override
    def _fetch(self, path: str, query: dict[str, str] | None = None) -> list[JsonType]:
        "Retrieves all results of a REST API v2 paginated result-set."

        items: list[JsonType] = []

        # cursor-based pagination with JSON `_links.next`
        url = self._build_url(ConfluenceVersion.VERSION_2, path, query)
        while True:
            response = self._session.get(url, headers={"Accept": "application/json"}, verify=True)
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

    @override
    def space_id_to_key(self, id: str) -> str:
        key = self._space_id_to_key.get(id)
        if key is None:
            data = self._get(
                ConfluenceVersion.VERSION_2,
                "/spaces",
                dict[str, JsonType],
                query={"ids": id, "status": "current"},
            )
            results = typing.cast(list[JsonType], data["results"])
            if len(results) != 1:
                raise ConfluenceError(f"unique space not found with id: {id}")

            result = typing.cast(dict[str, JsonType], results[0])
            key = typing.cast(str, result["key"])

            self._space_id_to_key[id] = key

        return key

    @override
    def space_key_to_id(self, key: str) -> str:
        id = self._space_key_to_id.get(key)
        if id is None:
            data = self._get(
                ConfluenceVersion.VERSION_2,
                "/spaces",
                dict[str, JsonType],
                query={"keys": key, "status": "current"},
            )
            results = typing.cast(list[JsonType], data["results"])
            if len(results) != 1:
                raise ConfluenceError(f"unique space not found with key: {key}")

            result = typing.cast(dict[str, JsonType], results[0])
            id = typing.cast(str, result["id"])

            self._space_key_to_id[key] = id

        return id

    @override
    def get_homepage_id(self, space_id: str) -> str:
        path = f"/spaces/{space_id}"
        data = self._get(ConfluenceVersion.VERSION_2, path, dict[str, JsonType])
        return typing.cast(str, data["homepageId"])

    @override
    def get_attachment_by_name(self, page_id: str, filename: str) -> ConfluenceAttachment:
        path = f"/pages/{page_id}/attachments"
        data = self._get(ConfluenceVersion.VERSION_2, path, dict[str, JsonType], query={"filename": filename})

        results = typing.cast(list[JsonType], data["results"])
        if len(results) != 1:
            raise ConfluenceError(f"no such attachment on page {page_id}: {filename}")
        result = typing.cast(dict[str, JsonType], results[0])
        return json_to_object(ConfluenceAttachment, result)

    @override
    def get_page_properties_by_title(self, title: str, *, space_id: str | None = None, space_key: str | None = None) -> ConfluencePageProperties:
        LOGGER.info("Looking up page with title: %s", title)
        path = "/pages"
        query = {
            "title": title,
        }
        space_id = self._get_space_id(space_id=space_id, space_key=space_key)
        if space_id is not None:
            query["space-id"] = space_id

        data = self._get(ConfluenceVersion.VERSION_2, path, dict[str, JsonType], query=query)
        results = typing.cast(list[JsonType], data["results"])
        if len(results) != 1:
            raise ConfluenceError(f"unique page not found with title: {title}")

        page = json_to_object(ConfluencePageProperties, results[0])
        return page

    @override
    def get_page(self, page_id: str, *, retries: int = 3, retry_delay: float = 1.0) -> ConfluencePage:
        path = f"/pages/{page_id}"
        last_error: requests.HTTPError | None = None

        for attempt in range(retries + 1):
            try:
                return self._get(ConfluenceVersion.VERSION_2, path, ConfluencePage, query={"body-format": "storage"})
            except requests.HTTPError as e:
                if e.response is not None and e.response.status_code == 404 and attempt < retries:
                    delay = retry_delay * (2**attempt) + random.uniform(0, 1)
                    LOGGER.debug("Page %s not found, retrying in %.1f seconds (attempt %d/%d)", page_id, delay, attempt + 1, retries)
                    time.sleep(delay)
                    last_error = e
                else:
                    raise

        # this should not be reached, but satisfies type checker
        if last_error is not None:
            raise last_error
        raise ConfluenceError(f"failed to get page: {page_id}")

    @override
    def get_page_properties(self, page_id: str) -> ConfluencePageProperties:
        path = f"/pages/{page_id}"
        return self._get(ConfluenceVersion.VERSION_2, path, ConfluencePageProperties)

    @override
    def update_page(self, page_id: str, content: str, *, title: str, version: int, message: str) -> None:
        """
        Updates a page via the Confluence API.

        :param page_id: The Confluence page ID.
        :param content: Confluence Storage Format XHTML.
        :param title: New title to assign to the page. Needs to be unique within a space.
        :param version: New version to assign to the page.
        :param message: Version message.
        """

        path = f"/pages/{page_id}"
        request = ConfluenceUpdatePageRequest(
            id=page_id,
            status=ConfluenceStatus.CURRENT,
            title=title,
            body=ConfluencePageBody(storage=ConfluencePageStorage(representation=ConfluenceRepresentation.STORAGE, value=content)),
            version=ConfluenceContentVersion(number=version, minorEdit=True, message=message),
        )
        LOGGER.info("Updating page: %s", page_id)
        self._put(ConfluenceVersion.VERSION_2, path, request, None)

    @override
    def create_page(self, *, title: str, content: str, parent_id: str, space_id: str) -> ConfluencePage:
        """
        Creates a new page via Confluence API.

        :param title: Page title.
        :param content: Page content in Confluence Storage Format.
        :param parent_id: Parent page ID.
        :param space_id: Space ID.
        :returns: Details about the newly created page.
        """

        LOGGER.info("Creating page: %s", title)

        path = "/pages/"
        request = ConfluenceCreatePageRequest(
            spaceId=space_id,
            status=ConfluenceStatus.CURRENT,
            title=title,
            parentId=parent_id,
            body=ConfluencePageBody(
                storage=ConfluencePageStorage(
                    representation=ConfluenceRepresentation.STORAGE,
                    value=content,
                )
            ),
        )
        return self._post(ConfluenceVersion.VERSION_2, path, request, ConfluencePage)

    @override
    def delete_page(self, page_id: str, *, purge: bool = False) -> None:
        """
        Deletes a page via Confluence API.

        :param page_id: The Confluence page ID.
        :param purge: `True` to completely purge the page, `False` to move to trash only.
        """

        path = f"/pages/{page_id}"

        # move to trash
        LOGGER.info("Moving page to trash: %s", page_id)
        self._delete(ConfluenceVersion.VERSION_2, path)

        if purge:
            # purge from trash
            LOGGER.info("Permanently deleting page: %s", page_id)
            self._delete(ConfluenceVersion.VERSION_2, path, query={"purge": "true"})

    @override
    def page_exists(self, title: str, *, space_id: str | None = None) -> str | None:
        path = "/pages"
        query = {"title": title}
        if space_id is not None:
            query["space-id"] = space_id

        LOGGER.info("Checking if page exists with title: %s", title)

        data = self._get(ConfluenceVersion.VERSION_2, path, dict[str, JsonType], query=query)
        results = json_to_object(list[ConfluencePageProperties], data["results"])

        if len(results) == 1:
            return results[0].id
        else:
            return None

    @override
    def get_labels(self, page_id: str) -> list[ConfluenceIdentifiedLabel]:
        path = f"/pages/{page_id}/labels"
        results = self._fetch(path)
        return json_to_object(list[ConfluenceIdentifiedLabel], results)

    @override
    def get_content_property_for_page(self, page_id: str, key: str) -> ConfluenceIdentifiedContentProperty | None:
        path = f"/pages/{page_id}/properties"
        results = self._fetch(path, query={"key": key})
        properties = json_to_object(list[ConfluenceIdentifiedContentProperty], results)
        if len(properties) == 1:
            return properties.pop()
        else:
            return None

    @override
    def get_content_properties_for_page(self, page_id: str) -> list[ConfluenceIdentifiedContentProperty]:
        path = f"/pages/{page_id}/properties"
        results = self._fetch(path)
        return json_to_object(list[ConfluenceIdentifiedContentProperty], results)

    @override
    def add_content_property_to_page(self, page_id: str, property: ConfluenceContentProperty) -> ConfluenceIdentifiedContentProperty:
        path = f"/pages/{page_id}/properties"
        return self._post(ConfluenceVersion.VERSION_2, path, property, ConfluenceIdentifiedContentProperty)

    @override
    def remove_content_property_from_page(self, page_id: str, property_id: str) -> None:
        path = f"/pages/{page_id}/properties/{property_id}"
        self._delete(ConfluenceVersion.VERSION_2, path)

    @override
    def update_content_property_for_page(
        self, page_id: str, property_id: str, version: int, property: ConfluenceContentProperty
    ) -> ConfluenceIdentifiedContentProperty:
        path = f"/pages/{page_id}/properties/{property_id}"
        return self._put(
            ConfluenceVersion.VERSION_2,
            path,
            ConfluenceVersionedContentProperty(
                key=property.key,
                value=property.value,
                version=ConfluenceContentVersion(number=version),
            ),
            ConfluenceIdentifiedContentProperty,
        )
