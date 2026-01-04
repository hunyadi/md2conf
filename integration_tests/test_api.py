"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os.path
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar

import lxml.etree as ET

from md2conf.api import ConfluenceAPI, ConfluenceAttachment, ConfluencePage
from md2conf.compatibility import override
from md2conf.converter import NodeVisitor, get_volatile_attributes, get_volatile_elements
from md2conf.csf import elements_from_string, elements_to_string
from md2conf.options import ConfluencePageID, ConverterOptions, DocumentOptions
from md2conf.publisher import Publisher
from md2conf.scanner import Scanner
from tests.utility import TypedTestCase

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]

FEATURE_TEST_PAGE_TITLE = "Publish Markdown to Confluence"
IMAGE_TEST_PAGE_TITLE = "Images and documents"


class ConfluenceStorageFormatCleaner(NodeVisitor):
    "Removes volatile attributes from a Confluence storage format XHTML document."

    def transform(self, child: ElementType) -> ElementType | None:
        if child.tag in get_volatile_elements():
            child.clear(keep_tail=True)
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


class TestAPI(TypedTestCase):
    out_dir: Path
    sample_dir: Path

    feature_test_page_id: ClassVar[ConfluencePageID]
    image_test_page_id: ClassVar[ConfluencePageID]

    @override
    @classmethod
    def setUpClass(cls) -> None:
        with ConfluenceAPI() as api:
            if api.site.space_key is None:
                raise ValueError("expected: Confluence space key to run integration tests")

            space_id = api.space_key_to_id(api.site.space_key)
            homepage_id = api.get_homepage_id(space_id)
            cls.feature_test_page_id = ConfluencePageID(api.get_or_create_page(title=FEATURE_TEST_PAGE_TITLE, parent_id=homepage_id).id)
            cls.image_test_page_id = ConfluencePageID(api.get_or_create_page(title=IMAGE_TEST_PAGE_TITLE, parent_id=cls.feature_test_page_id.page_id).id)

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

    def test_find_page_by_title(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page_properties_by_title(FEATURE_TEST_PAGE_TITLE)
            self.assertGreater(datetime.now(timezone.utc), page.createdAt)
            self.assertEqual(page.id, self.feature_test_page_id.page_id)

    def test_get_page(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page(self.feature_test_page_id.page_id)
            self.assertIsInstance(page, ConfluencePage)

        with open(self.out_dir / "page.html", "w", encoding="utf-8") as f:
            f.write(sanitize_confluence(page.content))

    def test_attachment(self) -> None:
        with ConfluenceAPI() as api:
            api.upload_attachment(
                self.image_test_page_id.page_id,
                "figure_interoperability.png",
                attachment_path=self.sample_dir / "figure" / "interoperability.png",
                comment="A sample figure",
                force=True,
            )

        with ConfluenceAPI() as api:
            data = api.get_attachment_by_name(self.image_test_page_id.page_id, "figure_interoperability.png")
            self.assertIsInstance(data, ConfluenceAttachment)

    def test_synchronize(self) -> None:
        with ConfluenceAPI() as api:
            options = DocumentOptions(
                root_page_id=self.feature_test_page_id,
                converter=ConverterOptions(
                    render_mermaid=os.getenv("RENDER_MERMAID", "false").lower() == "true",
                    render_plantuml=os.getenv("RENDER_PLANTUML", "false").lower() == "true",
                    diagram_output_format=os.getenv("DIAGRAM_OUTPUT_FORMAT", "svg"),  # type: ignore
                ),
            )
            Publisher(api, options).process(self.sample_dir / "index.md")

    def test_synchronize_page(self) -> None:
        with ConfluenceAPI() as api:
            options = DocumentOptions(
                root_page_id=self.feature_test_page_id,
                converter=ConverterOptions(
                    render_mermaid=os.getenv("RENDER_MERMAID", "false").lower() == "true",
                    render_plantuml=os.getenv("RENDER_PLANTUML", "false").lower() == "true",
                    diagram_output_format=os.getenv("DIAGRAM_OUTPUT_FORMAT", "svg"),  # type: ignore
                ),
            )
            Publisher(api, options).process_page(self.sample_dir / "index.md")

    def test_synchronize_directory(self) -> None:
        with ConfluenceAPI() as api:
            options = DocumentOptions(
                root_page_id=self.feature_test_page_id,
                converter=ConverterOptions(
                    render_mermaid=os.getenv("RENDER_MERMAID", "false").lower() == "true",
                    render_plantuml=os.getenv("RENDER_PLANTUML", "false").lower() == "true",
                    diagram_output_format=os.getenv("DIAGRAM_OUTPUT_FORMAT", "svg"),  # type: ignore
                ),
            )
            Publisher(api, options).process_directory(self.sample_dir)

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
                content: list[str] = [
                    f"# {relative_path}: A sample document",
                    "",
                    "This is a document without an explicitly assigned Confluence page ID or space key.",
                    "",
                    "UTF-8 test sequence: árvíztűrő tükörfúrógép.",
                ]

                frontmatter: list[str] = []
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
            Publisher(
                api,
                DocumentOptions(root_page_id=self.feature_test_page_id),
            ).process_directory(source_dir)

        with ConfluenceAPI() as api:
            for absolute_path in reversed(documents):
                document = Scanner().read(absolute_path)
                props = document.properties
                self.assertIsNotNone(props.page_id)
                if props.page_id is None:
                    continue
                api.delete_page(props.page_id)


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
