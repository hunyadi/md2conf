"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os
import os.path
import shutil
import unittest
from datetime import datetime, timezone
from pathlib import Path

import lxml.etree as ET

from integration_tests.fixtures import IntegrationTestFixture
from md2conf.api import (
    ConfluenceAPI,
    ConfluenceAttachment,
    ConfluencePage,
    ConfluenceSession,
)
from md2conf.collection import ConfluencePageCollection
from md2conf.converter import (
    ConfluenceDocument,
    NodeVisitor,
    get_volatile_attributes,
    get_volatile_elements,
)
from md2conf.csf import elements_from_string, elements_to_string
from md2conf.domain import ConfluenceDocumentOptions, ConfluencePageID
from md2conf.extra import override
from md2conf.metadata import ConfluenceSiteMetadata
from md2conf.publisher import Publisher, SynchronizingProcessor
from md2conf.scanner import Scanner
from tests.utility import TypedTestCase

ElementType = ET._Element  # pyright: ignore [reportPrivateUsage]

TEST_PAGE_TITLE = "Publish Markdown to Confluence"
TEST_SPACE = "~hunyadi"
FEATURE_TEST_PAGE_ID: ConfluencePageID | None = None
IMAGE_TEST_PAGE_ID: ConfluencePageID | None = None


def setUpModule() -> None:
    """
    Create test pages before running tests and inject page IDs into sample files.

    This function:
    1. Creates test pages in Confluence (or reuses existing ones)
    2. Writes page IDs back into sample markdown files
    3. Makes tests runnable from scratch without manual setup
    """
    global FEATURE_TEST_PAGE_ID, IMAGE_TEST_PAGE_ID

    space_key = os.environ.get("CONFLUENCE_SPACE_KEY", TEST_SPACE)

    # Get parent page ID from environment or use default
    parent_id = os.environ.get("CONFLUENCE_INTEGRATION_TEST_PARENT_PAGE_ID")

    if not parent_id:
        logging.warning(
            "CONFLUENCE_INTEGRATION_TEST_PARENT_PAGE_ID not set. "
            "Tests require a parent page ID to create test pages. "
            "Please set CONFLUENCE_INTEGRATION_TEST_PARENT_PAGE_ID environment variable "
            "or manually create pages with IDs matching the tests."
        )
        return

    with ConfluenceAPI() as api:
        fixture = IntegrationTestFixture(api, space_key)

        # Create main test page
        main_page_id = fixture.get_or_create_test_page(
            title=TEST_PAGE_TITLE,
            space_key=space_key,
            parent_id=parent_id,
            body="<p>Test page for md2conf integration tests</p>",
        )
        FEATURE_TEST_PAGE_ID = ConfluencePageID(main_page_id)

        # Create image test page as child
        image_page_id = fixture.get_or_create_test_page(
            title="Test Page for Attachments",
            space_key=space_key,
            parent_id=main_page_id,
            body="<p>Test page for attachment testing</p>",
        )
        IMAGE_TEST_PAGE_ID = ConfluencePageID(image_page_id)

        logging.info(f"Setup: main={main_page_id}, image={image_page_id}")

        # Write page IDs back to sample markdown files
        _write_page_ids_to_samples(api, fixture, space_key, main_page_id)


def tearDownModule() -> None:
    """Clean up test pages if requested."""
    if os.environ.get("CLEANUP_TEST_PAGES", "false").lower() == "true":
        space_key = os.environ.get("CONFLUENCE_SPACE_KEY", TEST_SPACE)
        with ConfluenceAPI() as api:
            fixture = IntegrationTestFixture(api, space_key)
            fixture.cleanup(delete_pages=True)


def _write_page_ids_to_samples(
    api: ConfluenceSession,
    fixture: IntegrationTestFixture,
    space_key: str,
    parent_id: str,
) -> None:
    """
    Create pages for sample files and write IDs into markdown files.

    This function reuses the existing SynchronizingProcessor._update_markdown()
    method to inject page IDs, maintaining consistency with the main codebase.

    :param api: Active Confluence session
    :param fixture: Test fixture for page management
    :param space_key: Confluence space key
    :param parent_id: Parent page ID for creating sample pages
    """
    # Get the sample directory
    test_dir = Path(__file__).parent.resolve(True)
    sample_dir = test_dir.parent / "sample"

    # Create a processor instance to reuse _update_markdown method
    processor = SynchronizingProcessor(
        api=api,
        options=ConfluenceDocumentOptions(),
        root_dir=sample_dir,
    )

    # Define sample files and their expected titles
    sample_files = {
        "index.md": "Publish Markdown to Confluence",
        "code.md": "Fenced code blocks",
        "attachments.md": "Images and documents",
        "panel.md": "Admonitions and alerts",
        "plantuml.md": "PlantUML Diagrams",
        "parent/index.md": "🏠 Markdown parent page",
        "parent/child.md": "Markdown child page",
    }

    for file_rel_path, title in sample_files.items():
        file_path = sample_dir / file_rel_path
        if not file_path.exists():
            logging.warning(f"Sample file not found: {file_rel_path}")
            continue

        # Create or find page for this sample file
        page_id = fixture.get_or_create_test_page(
            title=title,
            space_key=space_key,
            parent_id=parent_id,
            body=f"<p>Sample page: {title}</p>",
        )

        # Reuse existing logic to write page ID into markdown file
        processor._update_markdown(file_path, page_id=page_id, space_key=space_key)
        logging.info(f"Wrote page ID {page_id} to {file_rel_path}")


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
        self.assertListEqual(document.images, [])

        with open(self.out_dir / "document.html", "w", encoding="utf-8") as f:
            f.write(document.xhtml())

    def test_markdown_attachments(self) -> None:
        _, document = ConfluenceDocument.create(
            self.sample_dir / "attachments.md",
            ConfluenceDocumentOptions(),
            self.sample_dir,
            ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY"),
            ConfluencePageCollection(),
        )
        self.assertListEqual(document.links, [])
        self.assertListEqual(
            [item.path for item in document.images],
            [
                self.sample_dir / "figure" / "interoperability.png",
                self.sample_dir / "figure" / "interoperability.png",  # preferred over `interoperability.svg`
                self.sample_dir / "figure" / "diagram.drawio",
                self.sample_dir / "figure" / "class.mmd",
                self.sample_dir / "docs" / "sample.pdf",
                self.sample_dir / "docs" / "sample.docx",
                self.sample_dir / "docs" / "sample.xlsx",
                self.sample_dir / "docs" / "sample.odt",
                self.sample_dir / "docs" / "sample.ods",
            ],
        )

        with open(self.out_dir / "document.html", "w", encoding="utf-8") as f:
            f.write(document.xhtml())

    def test_find_page_by_title(self) -> None:
        if FEATURE_TEST_PAGE_ID is None:
            self.skipTest("Test page not created")
        with ConfluenceAPI() as api:
            page = api.get_page_properties_by_title(TEST_PAGE_TITLE)
            self.assertGreater(datetime.now(timezone.utc), page.createdAt)
            self.assertEqual(page.id, FEATURE_TEST_PAGE_ID.page_id)

    def test_get_page(self) -> None:
        if FEATURE_TEST_PAGE_ID is None:
            self.skipTest("Test page not created")
        with ConfluenceAPI() as api:
            page = api.get_page(FEATURE_TEST_PAGE_ID.page_id)
            self.assertIsInstance(page, ConfluencePage)

        with open(self.out_dir / "page.html", "w", encoding="utf-8") as f:
            f.write(sanitize_confluence(page.content))

    def test_get_attachment(self) -> None:
        if IMAGE_TEST_PAGE_ID is None:
            self.skipTest("Test page not created")
        # First upload the attachment so it exists
        with ConfluenceAPI() as api:
            api.upload_attachment(
                IMAGE_TEST_PAGE_ID.page_id,
                "figure_interoperability.png",
                attachment_path=self.sample_dir / "figure" / "interoperability.png",
                comment="Test attachment",
                force=True,
            )
            data = api.get_attachment_by_name(IMAGE_TEST_PAGE_ID.page_id, "figure_interoperability.png")
            self.assertIsInstance(data, ConfluenceAttachment)

    def test_upload_attachment(self) -> None:
        if IMAGE_TEST_PAGE_ID is None:
            self.skipTest("Test page not created")
        with ConfluenceAPI() as api:
            api.upload_attachment(
                IMAGE_TEST_PAGE_ID.page_id,
                "figure_interoperability.png",
                attachment_path=self.sample_dir / "figure" / "interoperability.png",
                comment="A sample figure",
                force=True,
            )

    def test_synchronize(self) -> None:
        with ConfluenceAPI() as api:
            Publisher(api, ConfluenceDocumentOptions()).process(self.sample_dir / "index.md")

    def test_synchronize_page(self) -> None:
        with ConfluenceAPI() as api:
            Publisher(api, ConfluenceDocumentOptions()).process_page(self.sample_dir / "index.md")

    def test_synchronize_directory(self) -> None:
        with ConfluenceAPI() as api:
            Publisher(api, ConfluenceDocumentOptions()).process_directory(self.sample_dir)

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
                ConfluenceDocumentOptions(root_page_id=FEATURE_TEST_PAGE_ID),
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
