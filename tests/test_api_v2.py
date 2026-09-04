"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import datetime
import logging
import unittest
from typing import Any, TypeVar

from requests import HTTPError, Response

from md2conf.api_types import ConfluencePageProperties, ConfluenceVersion
from md2conf.api_v2 import ConfluenceSessionV2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

T = TypeVar("T")

FOLDER_ID = "1234567890"

# as returned by `GET /wiki/api/v2/folders/{id}`: no body, `createdAt` in epoch
# milliseconds rather than ISO-8601, and no `lastOwnerId`
FOLDER_PAYLOAD: dict[str, Any] = {
    "id": FOLDER_ID,
    "type": "folder",
    "status": "current",
    "title": "Planning",
    "parentId": "1111111111",
    "parentType": "page",
    "position": 1781,
    "authorId": "AUTHOR_ID",
    "ownerId": "OWNER_ID",
    "spaceId": "SPACE_ID",
    "createdAt": 1785247544908,
    "version": {"number": 1, "minorEdit": False},
}


def _http_error(status_code: int) -> HTTPError:
    response = Response()
    response.status_code = status_code
    return HTTPError(f"{status_code} Client Error", response=response)


class StubSession(ConfluenceSessionV2):
    """
    A session whose only behavior is a canned `_get`.

    The base class constructor opens a connection to discover the site, which a unit test has no use for; this
    double supplies the single method `get_page_properties` relies on, and records the paths it was asked for.
    """

    paths: list[str]
    _pages_status: int

    def __init__(self, *, pages_status: int) -> None:
        self.paths = []
        self._pages_status = pages_status

    def _get(self, version: ConfluenceVersion, path: str, response_type: type[T], *, query: dict[str, str] | None = None) -> T:
        self.paths.append(path)
        if path.startswith("/pages/"):
            raise _http_error(self._pages_status)
        if path == f"/folders/{FOLDER_ID}":
            return dict(FOLDER_PAYLOAD)  # type: ignore[return-value]
        raise AssertionError(f"unexpected path: {path}")


class ApiV2Test(unittest.TestCase):
    def test_folder_is_returned_as_page_properties(self) -> None:
        "A folder ID resolves through the folder endpoint, so a folder can act as a page parent."

        session = StubSession(pages_status=404)
        properties = session.get_page_properties(FOLDER_ID)

        self.assertEqual(session.paths, [f"/pages/{FOLDER_ID}", f"/folders/{FOLDER_ID}"])
        self.assertIsInstance(properties, ConfluencePageProperties)
        self.assertEqual(properties.id, FOLDER_ID)
        self.assertEqual(properties.title, "Planning")
        self.assertEqual(properties.spaceId, "SPACE_ID")
        self.assertEqual(properties.parentId, "1111111111")

    def test_folder_timestamp_and_missing_owner_are_normalized(self) -> None:
        "Epoch milliseconds become a datetime, and the absent `lastOwnerId` becomes None."

        properties = StubSession(pages_status=404).get_page_properties(FOLDER_ID)

        self.assertEqual(
            properties.createdAt,
            datetime.datetime.fromtimestamp(1785247544908 / 1000, datetime.timezone.utc),
        )
        self.assertIsNone(properties.lastOwnerId)

    def test_error_other_than_not_found_is_raised(self) -> None:
        "Only HTTP 404 means 'perhaps a folder'; anything else is a failure to report, not to retry elsewhere."

        session = StubSession(pages_status=403)

        with self.assertRaises(HTTPError):
            session.get_page_properties(FOLDER_ID)

        self.assertEqual(session.paths, [f"/pages/{FOLDER_ID}"])


if __name__ == "__main__":
    unittest.main()
