"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import shutil
import unittest
from pathlib import Path

from md2conf.converter import ConfluenceDocumentOptions, ConfluenceSiteMetadata
from md2conf.processor import Processor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestProcessor(unittest.TestCase):
    out_dir: Path

    def setUp(self) -> None:
        self.maxDiff = 1024

        test_dir = Path(__file__).parent
        parent_dir = test_dir.parent

        self.out_dir = test_dir / "output"
        self.sample_dir = parent_dir / "sample"
        self.out_dir.mkdir(exist_ok=True, parents=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.out_dir)

    def test_process_document(self) -> None:
        options = ConfluenceDocumentOptions(
            generated_by="Test Case",
            root_page_id="None",
        )

        site_metadata = ConfluenceSiteMetadata("example.com", "/wiki/", "SPACE_KEY")
        Processor(options, site_metadata).process(self.sample_dir / "code.md")

        self.assertTrue((self.sample_dir / "index.csf").exists())

    def test_process_directory(self) -> None:
        options = ConfluenceDocumentOptions(
            generated_by="The Author",
            root_page_id="ROOT_PAGE_ID",
        )

        site_metadata = ConfluenceSiteMetadata("example.com", "/wiki/", "SPACE_KEY")
        Processor(options, site_metadata).process(self.sample_dir)

        self.assertTrue((self.sample_dir / "index.csf").exists())
        self.assertTrue((self.sample_dir / "sibling.csf").exists())
        self.assertTrue((self.sample_dir / "code.csf").exists())
        self.assertTrue((self.sample_dir / "parent" / "child.csf").exists())


if __name__ == "__main__":
    unittest.main()
