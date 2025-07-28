"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os.path
import shutil
import unittest
from pathlib import Path
from typing import Optional

import lxml.etree as ET

from md2conf.api import ConfluenceAPI, ConfluenceAttachment, ConfluencePage
from md2conf.application import Application
from md2conf.collection import ConfluencePageCollection
from md2conf.converter import ConfluenceDocument, NodeVisitor, get_volatile_attributes
from md2conf.csf import elements_from_string, elements_to_string
from md2conf.domain import ConfluenceDocumentOptions, ConfluencePageID
from md2conf.extra import override
from md2conf.metadata import ConfluenceSiteMetadata
from md2conf.scanner import Scanner

TEST_PAGE_TITLE = "Publish Markdown to Confluence"
TEST_SPACE = "~hunyadi"
TEST_PAGE_ID = ConfluencePageID("1933314")


class ConfluenceStorageFormatCleaner(NodeVisitor):
    "Removes volatile attributes from a Confluence storage format XHTML document."

    def transform(self, child: ET._Element) -> Optional[ET._Element]:
        for name in get_volatile_attributes():
            child.attrib.pop(name, None)
        return None


def sanitize_confluence(html: str) -> str:
    "Generates a sanitized version of a Confluence storage format XHTML document with no volatile attributes."

    if not html:
        return ""

    root = elements_from_string(html)
    ConfluenceStorageFormatCleaner().visit(root)
    return elements_to_string(root)


class TestAPI(unittest.TestCase):
    out_dir: Path
    sample_dir: Path

    @override
    def setUp(self) -> None:
        test_dir = Path(__file__).parent.resolve(True)
        parent_dir = test_dir.parent

        self.out_dir = test_dir / "output"
        self.sample_dir = parent_dir / "sample"
        os.makedirs(self.out_dir, exist_ok=True)

    @override
    def tearDown(self) -> None:
        shutil.rmtree(self.out_dir)

    def test_markdown(self) -> None:
        _, document = ConfluenceDocument.create(
            self.sample_dir / "index.md",
            ConfluenceDocumentOptions(),
            self.sample_dir,
            ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY"),
            ConfluencePageCollection(),
        )
        self.assertListEqual(document.links, [])
        self.assertListEqual(
            document.images,
            [
                self.sample_dir / "figure" / "interoperability.png",
                self.sample_dir / "figure" / "interoperability.png",  # preferred over `interoperability.svg`
                self.sample_dir / "figure" / "diagram.drawio",
                self.sample_dir / "figure" / "class.mmd",
            ],
        )

        with open(self.out_dir / "document.html", "w", encoding="utf-8") as f:
            f.write(document.xhtml())

    def test_find_page_by_title(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page_properties_by_title(TEST_PAGE_TITLE)
            self.assertEqual(page.id, TEST_PAGE_ID.page_id)

    def test_get_page(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page(TEST_PAGE_ID.page_id)
            self.assertIsInstance(page, ConfluencePage)

        with open(self.out_dir / "page.html", "w", encoding="utf-8") as f:
            f.write(sanitize_confluence(page.content))

    def test_get_attachment(self) -> None:
        with ConfluenceAPI() as api:
            data = api.get_attachment_by_name(TEST_PAGE_ID.page_id, "figure_interoperability.png")
            self.assertIsInstance(data, ConfluenceAttachment)

    def test_upload_attachment(self) -> None:
        with ConfluenceAPI() as api:
            api.upload_attachment(
                TEST_PAGE_ID.page_id,
                "figure_interoperability.png",
                attachment_path=self.sample_dir / "figure" / "interoperability.png",
                comment="A sample figure",
                force=True,
            )

    def test_synchronize(self) -> None:
        with ConfluenceAPI() as api:
            Application(api, ConfluenceDocumentOptions()).process(self.sample_dir / "index.md")

    def test_synchronize_page(self) -> None:
        with ConfluenceAPI() as api:
            Application(api, ConfluenceDocumentOptions()).process_page(self.sample_dir / "index.md")

    def test_synchronize_directory(self) -> None:
        with ConfluenceAPI() as api:
            Application(api, ConfluenceDocumentOptions()).process_directory(self.sample_dir)

    def test_synchronize_create(self) -> None:
        """
        Creates a Confluence page hierarchy from a set of Markdown files.

        Some documents have front-matter to test whether the title is extracted from front-matter when a Confluence page is about to be created.
        `index.md` documents don't have front-matter to verify if the implementation tackles the use case with no explicit title and duplicate file names.
        """

        source_dir = self.out_dir / "markdown"

        documents: list[Path] = [
            source_dir / "index.md",
            source_dir / "doc1.md",
            source_dir / "doc2.md",
            source_dir / "skip" / "nested" / "index.md",
            source_dir / "skip" / "nested" / "doc3.md",
            source_dir / "skip" / "nested" / "deep" / "index.md",
        ]

        for absolute_path in documents:
            os.makedirs(absolute_path.parent, exist_ok=True)
            relative_path = absolute_path.relative_to(source_dir).as_posix()

            with open(absolute_path, "w", encoding="utf-8") as f:
                content = [
                    f"# {relative_path}: A sample document",
                    "",
                    "This is a document without an explicitly assigned Confluence page ID or space key.",
                    "",
                    "UTF-8 test sequence: árvíztűrő tükörfúrógép.",
                ]

                frontmatter = []
                if absolute_path.name != "index.md":
                    unique_string = f"md2conf/{relative_path}"
                    digest = hashlib.sha1(unique_string.encode("utf-8")).hexdigest()
                    frontmatter.extend(
                        [
                            "---",
                            f'title: "{relative_path}: {digest}"',
                            "---",
                            "",
                        ]
                    )
                f.write("\n".join(frontmatter + content))

        with ConfluenceAPI() as api:
            Application(
                api,
                ConfluenceDocumentOptions(root_page_id=TEST_PAGE_ID),
            ).process_directory(source_dir)

        with ConfluenceAPI() as api:
            for absolute_path in reversed(documents):
                document = Scanner().read(absolute_path)
                self.assertIsNotNone(document.page_id)
                if document.page_id is None:
                    continue
                api.delete_page(document.page_id)


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
