"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os.path
import unittest
from pathlib import Path

from md2conf.api import ConfluenceAPI
from md2conf.converter import content_to_string

TEST_SPACE = "~hunyadi"
TEST_PAGE_ID = "65713"


class TestConfluenceStorageFormat(unittest.TestCase):
    test_dir: Path

    def setUp(self) -> None:
        self.test_dir = Path(__file__).parent
        parent_dir = self.test_dir.parent

        self.sample_dir = parent_dir / "sample"

    def test_markdown(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page(TEST_PAGE_ID)

        with open(self.test_dir / "example.csf", "w") as f:
            f.write(content_to_string(page.content))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
    )

    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s"
    )

    (name, _) = os.path.splitext(os.path.basename(__file__))
    handler = logging.FileHandler(
        os.path.join(os.path.dirname(__file__), f"{name}.log"), "w", "utf-8"
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    unittest.main()
