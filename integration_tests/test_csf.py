"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os.path
import unittest
from pathlib import Path
from typing import ClassVar

from md2conf.api import ConfluenceAPI
from md2conf.api_types import ConfluenceContentType, ConfluenceTypedID
from md2conf.compatibility import override
from md2conf.csf import content_to_string
from tests.utility import TypedTestCase


class TestConfluenceStorageFormat(TypedTestCase):
    test_page_id: ClassVar[str]
    test_dir: Path

    @override
    @classmethod
    def setUpClass(cls) -> None:
        with ConfluenceAPI() as api:
            if api.site.space_key is None:
                raise ValueError("expected: Confluence space key to run integration tests")

            space_id = api.space_key_to_id(api.site.space_key)
            homepage_id = api.get_homepage_id(space_id)
            parent_id = ConfluenceTypedID(homepage_id, ConfluenceContentType.PAGE)
            cls.test_page_id = api.get_or_create_page(title="Publish Markdown to Confluence", parent_id=parent_id).id

    @override
    def setUp(self) -> None:
        self.test_dir = Path(__file__).parent
        parent_dir = self.test_dir.parent

        self.sample_dir = parent_dir / "sample"

    def test_markdown(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page(self.test_page_id)

        (self.test_dir / "example.csf").write_text(content_to_string(page.content), encoding="utf-8")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
    )

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s")

    (name, _) = os.path.splitext(os.path.basename(__file__))
    handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), f"{name}.log"), "w", "utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    unittest.main()
