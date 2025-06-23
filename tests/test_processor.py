"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import shutil
import unittest
from pathlib import Path
from typing import Optional
from unittest.util import safe_repr

from md2conf.converter import ConfluenceDocumentOptions, ConfluencePageID
from md2conf.extra import override
from md2conf.local import LocalConverter
from md2conf.metadata import ConfluenceSiteMetadata

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestProcessor(unittest.TestCase):
    out_dir: Path
    sample_dir: Path

    def assertStartsWith(self, text: str, prefix: str, msg: Optional[str] = None) -> None:
        """Just like self.assertTrue(text.startswith(prefix)), but with a nicer default message."""

        if not text.startswith(prefix):
            standardMsg = "%s does not start with %s" % (
                safe_repr(text),
                safe_repr(prefix),
            )
            self.fail(self._formatMessage(msg, standardMsg))

    @override
    def setUp(self) -> None:
        self.maxDiff = 1024

        test_dir = Path(__file__).parent
        parent_dir = test_dir.parent

        self.out_dir = test_dir / "output"
        self.sample_dir = parent_dir / "sample"
        self.out_dir.mkdir(exist_ok=True, parents=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(self.out_dir)

    def create_converter(self, options: ConfluenceDocumentOptions) -> LocalConverter:
        site_metadata = ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY")
        return LocalConverter(options, site_metadata, self.out_dir)

    def test_process_document(self) -> None:
        options = ConfluenceDocumentOptions(
            root_page_id=ConfluencePageID("None"),
        )
        self.create_converter(options).process(self.sample_dir / "code.md")

        self.assertTrue((self.out_dir / "code.csf").exists())
        self.assertFalse((self.sample_dir / "code.csf").exists())

    def test_process_directory(self) -> None:
        options = ConfluenceDocumentOptions(
            root_page_id=ConfluencePageID("ROOT_PAGE_ID"),
        )

        self.create_converter(options).process(self.sample_dir)

        self.assertTrue((self.out_dir / "index.csf").exists())
        self.assertTrue((self.out_dir / "sibling.csf").exists())
        self.assertTrue((self.out_dir / "code.csf").exists())
        self.assertTrue((self.out_dir / "parent" / "child.csf").exists())
        self.assertFalse((self.sample_dir / "index.csf").exists())

    def test_generated_by(self) -> None:
        options = ConfluenceDocumentOptions(
            generated_by="<&> This page has been **generated** with [md2conf](https://github.com/hunyadi/md2conf)",
            root_page_id=ConfluencePageID("ROOT_PAGE_ID"),
        )
        self.create_converter(options).process(self.sample_dir / "index.md")

        csf_path = self.out_dir / "index.csf"
        self.assertTrue(csf_path.exists())

        with open(csf_path, "r", encoding="utf-8") as f:
            content = f.read()

        generated_by_html = (
            '<ac:structured-macro ac:name="info" ac:schema-version="1">'
            "<ac:rich-text-body>"
            '<p>&lt;&amp;&gt; This page has been <strong>generated</strong> with <a href="https://github.com/hunyadi/md2conf">md2conf</a></p>'
            "</ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        self.assertStartsWith(content, generated_by_html)


if __name__ == "__main__":
    unittest.main()
