"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os
import os.path
import re
import unittest
from pathlib import Path

from md2conf.collection import ConfluencePageCollection
from md2conf.converter import ConfluenceDocument, attachment_name
from md2conf.csf import elements_from_string, elements_to_string
from md2conf.domain import ConfluenceDocumentOptions
from md2conf.extra import override
from md2conf.latex import LATEX_ENABLED
from md2conf.matcher import Matcher, MatcherOptions
from md2conf.mermaid import has_mmdc
from md2conf.metadata import ConfluenceSiteMetadata
from tests import emoji
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


def canonicalize(content: str) -> str:
    "Converts a Confluence Storage Format (CSF) document to the normalized format."

    root = elements_from_string(content)
    return elements_to_string(root)


def substitute(root_dir: Path, content: str) -> str:
    "Converts a Confluence Storage Format (CSF) expectation template into a concrete match."

    def _repl_embed(m: re.Match[str]) -> str:
        "Replaces an embedding placeholder with the concrete attachment file name computed using a hash algorithm."

        relative_path = m.group(1)
        absolute_path = root_dir / relative_path
        with open(absolute_path, "r", encoding="utf-8") as f:
            content = f.read().rstrip()
        hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        extension = absolute_path.suffix
        return attachment_name(f"embedded_{hash}{extension}")

    embed_pattern = re.compile(r"EMBED\(([^()]+)\)")
    content = embed_pattern.sub(_repl_embed, content)

    return canonicalize(content)


def standardize(content: str) -> str:
    "Converts a Confluence Storage Format (CSF) document to the normalized format, removing unique identifiers."

    uuid_pattern = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F-]{36})(?![0-9a-fA-F])")
    content = uuid_pattern.sub("UUID", content)

    return canonicalize(content)


class TestConversion(TypedTestCase):
    source_dir: Path
    target_dir: Path
    site_metadata: ConfluenceSiteMetadata

    @override
    def setUp(self) -> None:
        self.maxDiff = None

        test_dir = Path(__file__).parent
        self.source_dir = test_dir / "source"
        self.target_dir = test_dir / "target"
        self.site_metadata = ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY")
        self.page_metadata = ConfluencePageCollection()

    def test_markdown(self) -> None:
        emoji.generate_source(self.source_dir / "emoji.md")
        emoji.generate_target(self.target_dir / "emoji.xml")

        matcher = Matcher(MatcherOptions(source=".mdignore", extension="md"), self.source_dir)

        entries: list[os.DirEntry[str]] = []
        for entry in os.scandir(self.source_dir):
            if entry.is_dir():
                continue

            if matcher.is_excluded(entry):
                continue

            entries.append(entry)

        entries.sort(key=lambda e: e.name)
        for entry in entries:
            name, _ = os.path.splitext(entry.name)

            with self.subTest(name=name):
                _, doc = ConfluenceDocument.create(
                    self.source_dir / f"{name}.md",
                    ConfluenceDocumentOptions(prefer_raster=False, render_drawio=True),
                    self.source_dir,
                    self.site_metadata,
                    self.page_metadata,
                )
                actual = standardize(doc.xhtml())

                with open(self.target_dir / f"{name}.xml", "r", encoding="utf-8") as f:
                    expected = substitute(self.target_dir, f.read())

                self.assertEqual(actual, expected)

    def test_admonitions(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "admonition.md",
            ConfluenceDocumentOptions(use_panel=True),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Admonitions")
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "panel.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_broken_links(self) -> None:
        with self.assertLogs(level=logging.WARNING) as cm:
            _, doc = ConfluenceDocument.create(
                self.source_dir / "missing.md",
                ConfluenceDocumentOptions(ignore_invalid_url=True),
                self.source_dir,
                self.site_metadata,
                self.page_metadata,
            )
            self.assertEqual(doc.title, "Broken links")
            actual = standardize(doc.xhtml())

        # check if 2 broken links have been found (anchor `href` & image `src`)
        self.assertEqual(len(cm.records), 5)

        with open(self.target_dir / "missing.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_heading_anchors(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "anchors.md",
            ConfluenceDocumentOptions(heading_anchors=True),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Anchors")
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "anchors.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_images(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "images" / "images.md",
            ConfluenceDocumentOptions(),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        actual = standardize(doc.xhtml())

        with open(self.target_dir / "images" / "images.xml", "r", encoding="utf-8") as f:
            expected = substitute(self.target_dir, f.read())

        self.assertEqual(actual, expected)

    def test_missing_title(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "title.md",
            ConfluenceDocumentOptions(),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertIsNone(doc.title)

    def test_unique_title(self) -> None:
        _, doc = ConfluenceDocument.create(
            self.source_dir / "sections.md",
            ConfluenceDocumentOptions(),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(doc.title, "Sections")

    @unittest.skipUnless(has_mmdc(), "mmdc is not available")
    @unittest.skipUnless(os.getenv("TEST_MERMAID"), "mermaid tests are disabled")
    def test_mermaid_embedded_svg(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "mermaid.md",
            ConfluenceDocumentOptions(
                render_mermaid=True,
                diagram_output_format="svg",
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(len(document.embedded_files), 6)

    @unittest.skipUnless(has_mmdc(), "mmdc is not available")
    @unittest.skipUnless(os.getenv("TEST_MERMAID"), "mermaid tests are disabled")
    def test_mermaid_embedded_png(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "mermaid.md",
            ConfluenceDocumentOptions(
                render_mermaid=True,
                diagram_output_format="png",
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(len(document.embedded_files), 6)

    @unittest.skipUnless(LATEX_ENABLED, "matplotlib not installed")
    def test_latex_svg(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "math.md",
            ConfluenceDocumentOptions(
                render_latex=True,
                diagram_output_format="svg",
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(len(document.embedded_files), 4)

    @unittest.skipUnless(LATEX_ENABLED, "matplotlib not installed")
    def test_latex_png(self) -> None:
        _, document = ConfluenceDocument.create(
            self.source_dir / "math.md",
            ConfluenceDocumentOptions(
                render_latex=True,
                diagram_output_format="png",
            ),
            self.source_dir,
            self.site_metadata,
            self.page_metadata,
        )
        self.assertEqual(len(document.embedded_files), 4)


if __name__ == "__main__":
    unittest.main()
