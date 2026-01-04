"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import os
import shutil
import unittest
from pathlib import Path

from md2conf.collection import ConfluencePageCollection
from md2conf.compatibility import override
from md2conf.converter import ConfluenceDocument
from md2conf.metadata import ConfluencePageMetadata, ConfluenceSiteMetadata
from md2conf.options import DocumentOptions
from tests.utility import TypedTestCase


class TestDocument(TypedTestCase):
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
        document_path = self.sample_dir / "index.md"
        metadata = ConfluencePageCollection()
        metadata.add(
            document_path,
            ConfluencePageMetadata(
                page_id="PAGE_ID",
                space_key="SPACE_KEY",
                title="Publish Markdown to Confluence",
                synchronized=False,
            ),
        )
        _, document = ConfluenceDocument.create(
            document_path,
            DocumentOptions(),
            self.sample_dir,
            ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY"),
            metadata,
        )
        self.assertListEqual(document.links, [])
        self.assertListEqual(document.images, [])

        with open(self.out_dir / "document.html", "w", encoding="utf-8") as f:
            f.write(document.xhtml())

    def test_markdown_attachments(self) -> None:
        document_path = self.sample_dir / "attachments.md"
        metadata = ConfluencePageCollection()
        metadata.add(
            document_path,
            ConfluencePageMetadata(
                page_id="PAGE_ID",
                space_key="SPACE_KEY",
                title="Images and documents",
                synchronized=False,
            ),
        )
        _, document = ConfluenceDocument.create(
            document_path,
            DocumentOptions(),
            self.sample_dir,
            ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY"),
            metadata,
        )
        self.assertListEqual(document.links, [])
        self.assertListEqual(
            [item.path for item in document.images],
            [
                self.sample_dir / "figure" / "interoperability.png",
                self.sample_dir / "figure" / "interoperability.png",  # preferred over `interoperability.svg`
                self.sample_dir / "figure" / "diagram.drawio",
                self.sample_dir / "figure" / "mermaid.mmd",
                self.sample_dir / "figure" / "plantuml.puml",
                self.sample_dir / "docs" / "sample.pdf",
                self.sample_dir / "docs" / "sample.docx",
                self.sample_dir / "docs" / "sample.xlsx",
                self.sample_dir / "docs" / "sample.odt",
                self.sample_dir / "docs" / "sample.ods",
            ],
        )

        with open(self.out_dir / "document.html", "w", encoding="utf-8") as f:
            f.write(document.xhtml())


if __name__ == "__main__":
    unittest.main()
