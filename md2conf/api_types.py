"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import datetime
import enum
from dataclasses import dataclass

from .serializer import JsonType


@enum.unique
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


@enum.unique
class ConfluencePageParentContentType(enum.Enum):
    """
    Content types that can be a parent to a Confluence page.
    """

    PAGE = "page"
    WHITEBOARD = "whiteboard"
    DATABASE = "database"
    EMBED = "embed"
    FOLDER = "folder"


@enum.unique
class ConfluenceRepresentation(enum.Enum):
    STORAGE = "storage"
    ATLAS = "atlas_doc_format"
    WIKI = "wiki"


@enum.unique
class ConfluenceStatus(enum.Enum):
    CURRENT = "current"
    DRAFT = "draft"
    ARCHIVED = "archived"


@enum.unique
class ConfluenceLegacyType(enum.Enum):
    ATTACHMENT = "attachment"


@dataclass(frozen=True)
class ConfluenceLinks:
    next: str
    base: str


@dataclass(frozen=True)
class ConfluenceResultSet:
    results: list[JsonType]
    _links: ConfluenceLinks


@dataclass(frozen=True)
class ConfluenceContentVersion:
    number: int
    minorEdit: bool = False
    createdAt: datetime.datetime | None = None
    message: str | None = None
    authorId: str | None = None


@dataclass(frozen=True)
class ConfluenceAttachment:
    """
    Holds data for an object uploaded to Confluence as a page attachment.

    :param id: Unique ID for the attachment.
    :param status: Attachment status.
    :param title: Attachment title.
    :param createdAt: Date and time when the attachment was created.
    :param pageId: The Confluence page that the attachment is coupled with.
    :param mediaType: MIME type for the attachment.
    :param mediaTypeDescription: Media type description for the attachment.
    :param comment: Description for the attachment.
    :param fileId: File ID of the attachment, distinct from the attachment ID.
    :param fileSize: Size in bytes.
    :param webuiLink: WebUI link of the attachment.
    :param downloadLink: Download link of the attachment.
    :param version: Version information for the attachment.
    """

    id: str
    status: ConfluenceStatus
    title: str | None
    createdAt: datetime.datetime
    pageId: str
    mediaType: str
    mediaTypeDescription: str | None
    comment: str | None
    fileId: str
    fileSize: int
    webuiLink: str
    downloadLink: str
    version: ConfluenceContentVersion


@dataclass(frozen=True)
class ConfluencePageProperties:
    """
    Holds Confluence page properties used for page synchronization.

    :param id: Confluence page ID.
    :param status: Page status.
    :param title: Page title.
    :param spaceId: Confluence space ID.
    :param parentId: Confluence page ID of the immediate parent.
    :param parentType: Identifies the content type of the parent.
    :param position: Position of child page within the given parent page tree.
    :param authorId: The account ID of the user who created this page originally.
    :param ownerId: The account ID of the user who owns this page.
    :param lastOwnerId: The account ID of the user who owned this page previously, or `None` if there is no previous owner.
    :param createdAt: Date and time when the page was created.
    :param version: Page version. Incremented when the page is updated.
    """

    id: str
    status: ConfluenceStatus
    title: str
    spaceId: str
    parentId: str | None
    parentType: ConfluencePageParentContentType | None
    position: int | None
    authorId: str
    ownerId: str
    lastOwnerId: str | None
    createdAt: datetime.datetime
    version: ConfluenceContentVersion


@dataclass(frozen=True)
class ConfluencePageStorage:
    """
    Holds Confluence page content.

    :param representation: Type of content representation used (e.g. Confluence Storage Format).
    :param value: Body of the content, in the format found in the representation field.
    """

    representation: ConfluenceRepresentation
    value: str


@dataclass(frozen=True)
class ConfluencePageBody:
    """
    Holds Confluence page content.

    :param storage: Encapsulates content with meta-information about its representation.
    """

    storage: ConfluencePageStorage


@dataclass(frozen=True)
class ConfluencePage(ConfluencePageProperties):
    """
    Holds Confluence page data used for page synchronization.

    :param body: Page content.
    """

    body: ConfluencePageBody

    @property
    def content(self) -> str:
        return self.body.storage.value


@dataclass(frozen=True, eq=True, order=True)
class ConfluenceLabel:
    """
    Holds information about a single label.

    :param name: Name of the label.
    :param prefix: Prefix of the label.
    """

    name: str
    prefix: str


@dataclass(frozen=True, eq=True, order=True)
class ConfluenceIdentifiedLabel(ConfluenceLabel):
    """
    Holds information about a single label.

    :param id: ID of the label.
    """

    id: str


@dataclass(frozen=True)
class ConfluenceContentProperty:
    """
    Represents a content property.

    :param key: Property key.
    :param value: Property value as JSON.
    """

    key: str
    value: JsonType


@dataclass(frozen=True)
class ConfluenceVersionedContentProperty(ConfluenceContentProperty):
    """
    Represents a content property.

    :param version: Version information about the property.
    """

    version: ConfluenceContentVersion


@dataclass(frozen=True)
class ConfluenceIdentifiedContentProperty(ConfluenceVersionedContentProperty):
    """
    Represents a content property.

    :param id: Property ID.
    """

    id: str
