from __future__ import annotations

import json
import logging
import mimetypes
import os
import os.path
import urllib.parse
from dataclasses import dataclass
from typing import Dict

import requests

from .converter import ParseError, sanitize_confluence


def build_url(base_url: str, query: Dict[str, str] = None):
    "Builds a URL with scheme, host, port, path and query string parameters."

    scheme, netloc, path, params, query_str, fragment = urllib.parse.urlparse(base_url)

    if params:
        raise ValueError("expected: url with no parameters")
    if query_str:
        raise ValueError("expected: url with no query string")
    if fragment:
        raise ValueError("expected: url with no fragment")

    query_str = urllib.parse.urlencode(query) if query else None
    url_parts = (scheme, netloc, path, None, query_str, None)
    return urllib.parse.urlunparse(url_parts)


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

    session: ConfluenceSession

    def __init__(
        self,
        domain: str = None,
        user_name: str = None,
        api_key: str = None,
        space_key: str = None,
    ) -> None:
        self.domain = domain or os.getenv("CONFLUENCE_DOMAIN")
        self.user_name = user_name or os.getenv("CONFLUENCE_USER_NAME")
        self.api_key = api_key or os.getenv("CONFLUENCE_API_KEY")
        self.space_key = space_key or os.getenv("CONFLUENCE_SPACE_KEY")

        if not self.domain:
            raise ConfluenceError("Confluence domain not specified")
        if not self.user_name:
            raise ConfluenceError("Confluence user name not specified")
        if not self.api_key:
            raise ConfluenceError("Confluence API key not specified")

    def __enter__(self):
        session = requests.Session()
        session.auth = (self.user_name, self.api_key)
        self.session = ConfluenceSession(session, self.domain, self.space_key)
        return self.session

    def __exit__(self, type, value, traceback):
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

    def _build_url(self, path: str, query: Dict[str, str] = None) -> str:
        base_url = f"https://{self.domain}/wiki/rest/api{path}"
        return build_url(base_url, query)

    def _invoke(self, path: str, query: Dict[str, str]) -> str:
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
        data = self._invoke(path, query)

        results = data["results"]
        if len(results) != 1:
            raise ConfluenceError(f"no such attachment on page {page_id}: {filename}")

        id = results[0]["id"]
        extensions = results[0]["extensions"]
        media_type = extensions["mediaType"]
        file_size = extensions["fileSize"]
        comment = extensions["comment"]
        return ConfluenceAttachment(id, media_type, file_size, comment)

    def upload_attachment(
        self,
        page_id: str,
        attachment_path: str,
        attachment_name: str,
        comment: str = None,
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
                url, files=file_to_upload, headers={"X-Atlassian-Token": "no-check"}
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
        data = self._invoke(path, query)

        results = data["results"]
        if len(results) != 1:
            raise ConfluenceError(f"page not found with title: {title}")

        id = results[0]["id"]
        return id

    def get_page(self, page_id: str) -> ConfluencePage:
        path = f"/content/{page_id}"
        query = {
            "spaceKey": self.space_key,
            "expand": "body.storage,version",
        }
        data = self._invoke(path, query)

        return ConfluencePage(
            id=page_id,
            title=data["title"],
            version=data["version"]["number"],
            content=data["body"]["storage"]["value"],
        )

    def get_page_version(self, page_id: str) -> int:
        path = f"/content/{page_id}"
        query = {
            "spaceKey": self.space_key,
            "expand": "version",
        }
        data = self._invoke(path, query)
        return data["version"]["number"]

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
