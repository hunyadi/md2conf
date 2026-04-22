"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import datetime
import json
import logging
import sqlite3
from pathlib import Path
from typing import Literal
from uuid import uuid4

from md2conf.api_base import ConfluenceSession
from md2conf.api_types import (
    ConfluenceAttachment,
    ConfluenceContentProperty,
    ConfluenceContentVersion,
    ConfluenceIdentifiedContentProperty,
    ConfluenceIdentifiedLabel,
    ConfluenceLabel,
    ConfluencePage,
    ConfluencePageBody,
    ConfluencePageParentContentType,
    ConfluencePageProperties,
    ConfluencePageStorage,
    ConfluenceRepresentation,
    ConfluenceStatus,
    ConfluenceUser,
)
from md2conf.compatibility import override
from md2conf.environment import ConfluenceError
from md2conf.metadata import ConfluenceSiteMetadata

LOGGER = logging.getLogger(__name__)

HOMEPAGE_ID = "1000000000"


def _require_greater_version(source: int, target: int) -> None:
    if target <= source:
        raise ConfluenceError(f"expected: version greater than current version {source}; got: {target}")


class MockConfluenceSession(ConfluenceSession):
    """
    Emulates Confluence REST API calls for unit tests.

    Employs an in-memory SQLite database to store attachments, pages and content properties.
    The session is initialized with a single homepage in the root of the space.
    """

    _site: ConfluenceSiteMetadata
    _db: sqlite3.Connection

    def __init__(self) -> None:
        self._site = ConfluenceSiteMetadata(domain="example.atlassian.net", base_path="/wiki/", space_key="SPACE_KEY")
        self._db = sqlite3.connect(":memory:")
        self._db.row_factory = sqlite3.Row
        self._db.execute(
            """
            CREATE TABLE attachments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                createdAt INTEGER NOT NULL,  -- stored as UNIX timestamp
                pageId TEXT NOT NULL,
                fileSize INTEGER NOT NULL,
                version INTEGER NOT NULL,
                UNIQUE (pageId, title)
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE pages (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                parentId TEXT,
                createdAt INTEGER NOT NULL,  -- stored as UNIX timestamp
                version INTEGER NOT NULL,
                body TEXT NOT NULL
            )
            """
        )
        self._db.execute(
            """
            CREATE TABLE contentProperties (
                id TEXT PRIMARY KEY,
                pageId TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                version INTEGER NOT NULL,
                UNIQUE (pageId, key)
            )
            """
        )
        self._create_page(
            page_id=HOMEPAGE_ID,
            title="Home",
            content="<p>This is the root page of the space.</p>",
            parent_id=None,
            space_id="SPACE_ID",
        )
        self._db.commit()

    def _get_page_row(self, page_id: str) -> sqlite3.Row:
        row: sqlite3.Row | None = self._db.execute(
            "SELECT id, title, parentId, createdAt, version, body FROM pages WHERE id = ?",
            (page_id,),
        ).fetchone()
        if row is None:
            raise ConfluenceError(f"page not found with ID: {page_id}")
        return row

    def _get_content_property_row(self, page_id: str, property_id: str) -> sqlite3.Row:
        row: sqlite3.Row | None = self._db.execute(
            "SELECT id, key, value, version FROM contentProperties WHERE id = ? AND pageId = ?",
            (property_id, page_id),
        ).fetchone()
        if row is None:
            raise ConfluenceError(f"content property not found with ID: {property_id}")
        return row

    def _get_attachment_row(self, attachment_id: str) -> sqlite3.Row:
        row: sqlite3.Row | None = self._db.execute(
            "SELECT id, title, createdAt, pageId, fileSize, version FROM attachments WHERE id = ?",
            (attachment_id,),
        ).fetchone()
        if row is None:
            raise ConfluenceError(f"attachment not found with ID: {attachment_id}")
        return row

    def _row_to_attachment(self, row: sqlite3.Row) -> ConfluenceAttachment:
        return ConfluenceAttachment(
            id=row["id"],
            status=ConfluenceStatus.CURRENT,
            title=row["title"],
            createdAt=datetime.datetime.fromtimestamp(row["createdAt"], tz=datetime.timezone.utc),
            pageId=row["pageId"],
            mediaType="application/octet-stream",
            mediaTypeDescription=None,
            comment=None,
            fileId=row["id"],
            fileSize=row["fileSize"],
            webuiLink="",
            downloadLink="",
            version=ConfluenceContentVersion(number=row["version"]),
        )

    def _row_to_page_properties(self, row: sqlite3.Row) -> ConfluencePageProperties:
        return ConfluencePageProperties(
            id=row["id"],
            status=ConfluenceStatus.CURRENT,
            title=row["title"],
            spaceId="SPACE_ID",
            parentId=row["parentId"],
            parentType=ConfluencePageParentContentType.PAGE,
            position=0,
            authorId="AUTHOR_ID",
            ownerId="OWNER_ID",
            lastOwnerId=None,
            createdAt=datetime.datetime.fromtimestamp(row["createdAt"], tz=datetime.timezone.utc),
            version=ConfluenceContentVersion(number=row["version"]),
        )

    def _row_to_identified_content_property(self, row: sqlite3.Row) -> ConfluenceIdentifiedContentProperty:
        return ConfluenceIdentifiedContentProperty(
            id=row["id"],
            key=row["key"],
            value=json.loads(row["value"]),
            version=ConfluenceContentVersion(number=row["version"]),
        )

    def _row_to_page(self, row: sqlite3.Row) -> ConfluencePage:
        props = self._row_to_page_properties(row)
        return ConfluencePage(
            id=props.id,
            status=props.status,
            title=props.title,
            spaceId=props.spaceId,
            parentId=props.parentId,
            parentType=props.parentType,
            position=props.position,
            authorId=props.authorId,
            ownerId=props.ownerId,
            lastOwnerId=props.lastOwnerId,
            createdAt=props.createdAt,
            version=props.version,
            body=ConfluencePageBody(
                storage=ConfluencePageStorage(
                    representation=ConfluenceRepresentation.STORAGE,
                    value=row["body"],
                )
            ),
        )

    def get_attachment_count(self) -> int:
        row: sqlite3.Row = self._db.execute("SELECT COUNT(*) AS count FROM attachments").fetchone()
        return int(row["count"])

    def get_page_count(self) -> int:
        row: sqlite3.Row = self._db.execute("SELECT COUNT(*) AS count FROM pages").fetchone()
        return int(row["count"])

    @property
    def site(self) -> ConfluenceSiteMetadata:
        return self._site

    @override
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
        if attachment_path is not None:
            LOGGER.debug("attachment_name: %s, attachment_path: %s", attachment_name, attachment_path)
            file_size = attachment_path.stat().st_size
        elif raw_data is not None:
            LOGGER.debug("attachment_name: %s, raw_data: %d bytes", attachment_name, len(raw_data))
            file_size = len(raw_data)
        else:
            file_size = 0

        now = datetime.datetime.now(datetime.timezone.utc)
        row: sqlite3.Row | None = self._db.execute(
            "SELECT id, version FROM attachments WHERE pageId = ? AND title = ? LIMIT 1",
            (page_id, attachment_name),
        ).fetchone()
        if row is None:
            attachment_id = f"ATTACHMENT_{uuid4().hex[:8].upper()}"
            version = 1
            self._db.execute(
                "INSERT INTO attachments (id, title, createdAt, pageId, fileSize, version) VALUES (?, ?, ?, ?, ?, ?)",
                (attachment_id, attachment_name, int(now.timestamp()), page_id, file_size, version),
            )
        else:
            attachment_id = str(row["id"])
            version = int(row["version"]) + 1
            self._db.execute(
                "UPDATE attachments SET createdAt = ?, fileSize = ?, version = ? WHERE id = ?",
                (int(now.timestamp()), file_size, version, attachment_id),
            )
        self._db.commit()
        return None

    @override
    def close(self) -> None:
        self._db.close()

    @override
    def space_id_to_key(self, id: str) -> str:
        LOGGER.debug("space_id: %s", id)
        return "SPACE_KEY"

    @override
    def space_key_to_id(self, key: str) -> str:
        LOGGER.debug("space_key: %s", key)
        return "SPACE_ID"

    @override
    def get_homepage_id(self, space_id: str) -> str:
        LOGGER.debug("space_id: %s", space_id)
        return HOMEPAGE_ID

    @override
    def get_users(self, expr: str) -> list[ConfluenceUser]:
        return []

    @override
    def get_attachments(self, page_id: str) -> list[ConfluenceAttachment]:
        LOGGER.debug("page_id: %s", page_id)
        rows = self._db.execute(
            "SELECT id, title, createdAt, pageId, fileSize, version FROM attachments WHERE pageId = ? ORDER BY createdAt, title",
            (page_id,),
        ).fetchall()
        return [self._row_to_attachment(row) for row in rows]

    @override
    def get_attachment_by_name(self, page_id: str, filename: str) -> ConfluenceAttachment:
        LOGGER.debug("page_id: %s, filename: %s", page_id, filename)
        row: sqlite3.Row | None = self._db.execute(
            "SELECT id, title, createdAt, pageId, fileSize, version FROM attachments WHERE pageId = ? AND title = ? LIMIT 1",
            (page_id, filename),
        ).fetchone()
        if row is None:
            raise ConfluenceError(f"no such attachment on page {page_id}: {filename}")
        return self._row_to_attachment(row)

    @override
    def delete_attachment(self, attachment_id: str) -> None:
        LOGGER.debug("attachment_id: %s", attachment_id)
        self._get_attachment_row(attachment_id)
        self._db.execute("DELETE FROM attachments WHERE id = ?", (attachment_id,))
        self._db.commit()
        return None

    @override
    def get_page_properties_by_title(self, title: str, *, space_id: str | None = None, space_key: str | None = None) -> ConfluencePageProperties:
        LOGGER.debug("title: %s", title)
        row: sqlite3.Row | None = self._db.execute(
            "SELECT id, title, parentId, createdAt, version, body FROM pages WHERE title = ? LIMIT 1",
            (title,),
        ).fetchone()
        if row is None:
            raise ConfluenceError(f"unique page not found with title: {title}")
        return self._row_to_page_properties(row)

    @override
    def get_page(self, page_id: str) -> ConfluencePage:
        LOGGER.debug("page_id: %s", page_id)
        return self._row_to_page(self._get_page_row(page_id))

    @override
    def get_page_properties(self, page_id: str) -> ConfluencePageProperties:
        LOGGER.debug("page_id: %s", page_id)
        return self._row_to_page_properties(self._get_page_row(page_id))

    @override
    def update_page(self, page_id: str, content: str, *, title: str, version: int, message: str) -> None:
        LOGGER.debug("page_id: %s, title: %s", page_id, title)
        row = self._get_page_row(page_id)
        _require_greater_version(row["version"], version)
        cursor = self._db.execute(
            "UPDATE pages SET title = ?, version = ?, body = ? WHERE id = ?",
            (title, version, content, page_id),
        )
        self._db.commit()
        if cursor.rowcount == 0:
            raise ConfluenceError(f"page not found with ID: {page_id}")
        return None

    @override
    def create_page(self, *, title: str, content: str, parent_id: str, space_id: str) -> ConfluencePage:
        LOGGER.debug("parent_id: %s, title: %s", parent_id, title)
        page_id = str(uuid4().int % 9_000_000_000 + 1_000_000_000)
        return self._create_page(page_id, title, content, parent_id, space_id)

    def _create_page(self, page_id: str, title: str, content: str, parent_id: str | None, space_id: str) -> ConfluencePage:
        created_at = datetime.datetime.now(datetime.timezone.utc)
        version = 1
        self._db.execute(
            "INSERT INTO pages (id, title, parentId, createdAt, version, body) VALUES (?, ?, ?, ?, ?, ?)",
            (page_id, title, parent_id, int(created_at.timestamp()), version, content),
        )
        self._db.commit()
        return self.get_page(page_id)

    @override
    def delete_page(self, page_id: str, *, purge: bool = False) -> None:
        LOGGER.debug("page_id: %s", page_id)
        self._db.execute("DELETE FROM pages WHERE id = ?", (page_id,))
        self._db.commit()
        return None

    @override
    def page_exists(self, title: str, *, space_id: str | None = None) -> str | None:
        LOGGER.debug("title: %s", title)
        row = self._db.execute("SELECT id FROM pages WHERE title = ? LIMIT 1", (title,)).fetchone()
        if row is None:
            return None
        return str(row["id"])

    @override
    def move_page(self, page_id: str, position: Literal["before", "after", "append"], ref_id: str) -> None:
        pass

    @override
    def get_labels(self, page_id: str) -> list[ConfluenceIdentifiedLabel]:
        LOGGER.debug("page_id: %s", page_id)
        return []

    @override
    def add_labels(self, page_id: str, labels: list[ConfluenceLabel]) -> None:
        LOGGER.debug("page_id: %s", page_id)
        return None

    @override
    def remove_labels(self, page_id: str, labels: list[ConfluenceLabel]) -> None:
        LOGGER.debug("page_id: %s", page_id)
        return None

    @override
    def update_labels(self, page_id: str, labels: list[ConfluenceLabel], *, keep_existing: bool = False) -> None:
        LOGGER.debug("page_id: %s", page_id)
        return None

    @override
    def get_content_property_for_page(self, page_id: str, key: str) -> ConfluenceIdentifiedContentProperty | None:
        LOGGER.debug("page_id: %s, property_key: %s", page_id, key)
        row: sqlite3.Row | None = self._db.execute(
            "SELECT id, key, value, version FROM contentProperties WHERE pageId = ? AND key = ? LIMIT 1",
            (page_id, key),
        ).fetchone()
        return self._row_to_identified_content_property(row) if row is not None else None

    @override
    def get_content_properties_for_page(self, page_id: str) -> list[ConfluenceIdentifiedContentProperty]:
        LOGGER.debug("page_id: %s", page_id)
        rows = self._db.execute(
            "SELECT id, key, value, version FROM contentProperties WHERE pageId = ?",
            (page_id,),
        ).fetchall()
        return [self._row_to_identified_content_property(row) for row in rows]

    @override
    def add_content_property_to_page(self, page_id: str, property: ConfluenceContentProperty) -> ConfluenceIdentifiedContentProperty:
        LOGGER.debug("page_id: %s, property_key: %s", page_id, property.key)
        property_id = f"PROP_{uuid4().hex[:8].upper()}"
        self._db.execute(
            "INSERT INTO contentProperties (id, pageId, key, value, version) VALUES (?, ?, ?, ?, ?)",
            (property_id, page_id, property.key, json.dumps(property.value), 1),
        )
        self._db.commit()
        row = self._db.execute(
            "SELECT id, key, value, version FROM contentProperties WHERE id = ?",
            (property_id,),
        ).fetchone()
        return self._row_to_identified_content_property(row)

    @override
    def remove_content_property_from_page(self, page_id: str, property_id: str) -> None:
        LOGGER.debug("page_id: %s, property_id: %s", page_id, property_id)
        self._db.execute(
            "DELETE FROM contentProperties WHERE id = ? AND pageId = ?",
            (property_id, page_id),
        )
        self._db.commit()
        return None

    @override
    def update_content_property_for_page(
        self,
        page_id: str,
        property_id: str,
        version: int,
        property: ConfluenceContentProperty,
    ) -> ConfluenceIdentifiedContentProperty:
        LOGGER.debug("page_id: %s, property_id: %s", page_id, property_id)
        row = self._get_content_property_row(page_id, property_id)
        _require_greater_version(row["version"], version)
        cursor = self._db.execute(
            "UPDATE contentProperties SET key = ?, value = ?, version = ? WHERE id = ? AND pageId = ?",
            (property.key, json.dumps(property.value), version, property_id, page_id),
        )
        self._db.commit()
        if cursor.rowcount == 0:
            raise ConfluenceError(f"content property not found with ID: {property_id}")
        row = self._db.execute(
            "SELECT id, key, value, version FROM contentProperties WHERE id = ?",
            (property_id,),
        ).fetchone()
        return self._row_to_identified_content_property(row)


class MockConfluenceAPI:
    """
    Emulates Confluence REST API calls for unit tests.
    """

    _session: MockConfluenceSession

    def __init__(self) -> None:
        self._session = MockConfluenceSession()

    def __enter__(self) -> MockConfluenceSession:
        return self._session

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        self._session.close()
