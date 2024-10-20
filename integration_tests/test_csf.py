"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2024, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from pathlib import Path

from md2conf.api import ConfluenceAPI
from md2conf.converter import content_to_string

TEST_SPACE = "DAP"
TEST_PAGE_ID = "86918529216"


class TestConfluenceStorageFormat(unittest.TestCase):
    test_dir: Path

    def setUp(self) -> None:
        self.test_dir = Path(__file__).parent
        parent_dir = self.test_dir.parent

        self.sample_dir = parent_dir / "sample"

    def test_markdown(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page(TEST_PAGE_ID, space_key=TEST_SPACE)

        with open(self.test_dir / "example.csf", "w") as f:
            f.write(content_to_string(page.content))


if __name__ == "__main__":
    unittest.main()
