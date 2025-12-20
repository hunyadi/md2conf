"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os.path
import unittest
from pathlib import Path
from typing import ClassVar

from md2conf.api import ConfluenceAPI, ConfluenceContentProperty, ConfluenceLabel
from md2conf.csf import content_to_string
from md2conf.extra import override
from tests.utility import TypedTestCase


class TestConfluenceStorageFormat(TypedTestCase):
    test_page_id: ClassVar[str]
    test_dir: Path

    @classmethod
    def setUpClass(cls) -> None:
        with ConfluenceAPI() as api:
            if api.site.space_key is None:
                raise ValueError("expected: Confluence space key required to run integration tests")

            space_id = api.space_key_to_id(api.site.space_key)
            homepage_id = api.get_homepage_id(space_id)
            cls.test_page_id = api.get_or_create_page(title="Confluence Storage Format", parent_id=homepage_id).id

    @override
    def setUp(self) -> None:
        self.test_dir = Path(__file__).parent
        parent_dir = self.test_dir.parent

        self.sample_dir = parent_dir / "sample"

    def test_markdown(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page(self.test_page_id)

        with open(self.test_dir / "example.csf", "w") as f:
            f.write(content_to_string(page.content))

    def test_labels(self) -> None:
        with ConfluenceAPI() as api:
            expected_labels = [
                ConfluenceLabel(name="advanced", prefix="global"),
                ConfluenceLabel(name="code", prefix="global"),
            ]
            api.update_labels(self.test_page_id, expected_labels)
            assigned_labels = sorted(ConfluenceLabel(name=label.name, prefix=label.prefix) for label in api.get_labels(self.test_page_id))
            self.assertListEqual(assigned_labels, expected_labels)

    def test_properties(self) -> None:
        with ConfluenceAPI() as api:
            properties = api.get_content_properties_for_page(self.test_page_id)
            self.assertGreater(len(properties), 0)

            api.update_content_properties_for_page(
                self.test_page_id,
                [
                    ConfluenceContentProperty(key="content-appearance-published", value="full-width"),
                    ConfluenceContentProperty(key="content-appearance-draft", value="full-width"),
                ],
            )


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
