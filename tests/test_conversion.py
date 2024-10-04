import logging
import os
import os.path
import re
import unittest
from pathlib import Path

import md2conf.emoji as emoji
from md2conf.converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    elements_from_string,
    elements_to_string,
)
from md2conf.matcher import Matcher, MatcherOptions
from md2conf.mermaid import has_mmdc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


def canonicalize(content: str) -> str:
    "Converts a Confluence Storage Format (CSF) document to the normalized format."

    return elements_to_string(elements_from_string(content))


def standardize(content: str) -> str:
    "Converts a Confluence Storage Format (CSF) document to the normalized format, removing unique identifiers."

    uuid_pattern = re.compile(r"\b[0-9a-fA-F-]{36}\b")
    content = re.sub(uuid_pattern, "UUID", content)
    return canonicalize(content)


class TestConversion(unittest.TestCase):
    source_dir: Path
    target_dir: Path

    def setUp(self) -> None:
        self.maxDiff = None

        test_dir = Path(__file__).parent
        self.source_dir = test_dir / "source"
        self.target_dir = test_dir / "target"

    def test_markdown(self) -> None:
        if not os.path.exists(self.source_dir / "emoji.md"):
            emoji.generate_source(self.source_dir / "emoji.md")
        if not os.path.exists(self.target_dir / "emoji.xml"):
            emoji.generate_target(self.target_dir / "emoji.xml")

        matcher = Matcher(
            MatcherOptions(source=".mdignore", extension="md"), self.source_dir
        )

        for entry in os.scandir(self.source_dir):
            if matcher.is_excluded(entry.name, entry.is_dir()):
                continue

            name, _ = os.path.splitext(entry.name)

            with self.subTest(name=name):
                actual = ConfluenceDocument(
                    self.source_dir / f"{name}.md",
                    ConfluenceDocumentOptions(ignore_invalid_url=True),
                    {},
                ).xhtml()
                actual = standardize(actual)

                with open(self.target_dir / f"{name}.xml", "r", encoding="utf-8") as f:
                    expected = canonicalize(f.read())

                self.assertEqual(actual, expected)

    def test_heading_anchors(self) -> None:
        actual = ConfluenceDocument(
            self.source_dir / "sections.md",
            ConfluenceDocumentOptions(ignore_invalid_url=True, heading_anchors=True),
            {},
        ).xhtml()
        actual = standardize(actual)

        with open(self.target_dir / "anchors.xml", "r", encoding="utf-8") as f:
            expected = canonicalize(f.read())

        self.assertEqual(actual, expected)

    @unittest.skipUnless(has_mmdc(), "mmdc is not available")
    def test_mermaid_embedded_svg(self) -> None:
        document = ConfluenceDocument(
            self.source_dir / "mermaid.md",
            ConfluenceDocumentOptions(
                ignore_invalid_url=True,
                render_mermaid=True,
                diagram_output_format="svg",
            ),
            {},
        )
        self.assertEqual(len(document.embedded_images), 6)

    @unittest.skipUnless(has_mmdc(), "mmdc is not available")
    def test_mermaid_embedded_png(self) -> None:
        document = ConfluenceDocument(
            self.source_dir / "mermaid.md",
            ConfluenceDocumentOptions(
                ignore_invalid_url=True,
                render_mermaid=True,
                diagram_output_format="png",
            ),
            {},
        )
        self.assertEqual(len(document.embedded_images), 6)


if __name__ == "__main__":
    unittest.main()
