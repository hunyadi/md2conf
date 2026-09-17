"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import unittest
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from md2conf.api_base import ConfluenceSession
from md2conf.api_types import ConfluenceFolderProperties, ConfluencePageProperties
from md2conf.compatibility import override
from md2conf.environment import PageError
from md2conf.options import ConfluencePageID, ProcessorOptions
from md2conf.options_converter import ConverterOptions
from md2conf.publisher import AggregateOptions, DocumentHasher, Publisher
from md2conf.scanner import Scanner
from tests.api import MockConfluenceAPI, MockConfluenceSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


@contextmanager
def _create_temporary_directory() -> Generator[Path]:
    "Creates a temporary directory."

    with TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
        yield Path(temp_dir)


def _create_document(absolute_path: Path, source_dir: Path, *, has_frontmatter: bool) -> None:
    "Creates a Markdown document with some sample content."

    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    relative_path = absolute_path.relative_to(source_dir).as_posix()

    content: list[str] = [
        f"# {relative_path}: A sample document",
        "",
        "This is a document without an explicitly assigned Confluence page ID or space key.",
    ]

    frontmatter: list[str] = []
    if has_frontmatter:
        unique_string = f"md2conf/{relative_path}"
        digest = hashlib.sha1(unique_string.encode()).hexdigest()
        frontmatter.extend(
            [
                "---",
                f'title: "{relative_path}: {digest}"',
                "---",
                "",
            ]
        )

    absolute_path.write_text("\n".join(frontmatter + content), encoding="utf-8")


def _get_page_for_document(api: ConfluenceSession, absolute_path: Path) -> ConfluencePageProperties:
    "Retrieves the Confluence page corresponding to the given document path."

    document = Scanner().read(absolute_path)
    props = document.properties
    if props.page_id is None:
        raise ValueError(f"document does not have a page ID assigned: {absolute_path}")
    return api.get_page_properties(props.page_id)


def _get_folder_for_document(api: ConfluenceSession, absolute_path: Path) -> ConfluenceFolderProperties:
    """Retrieves the Confluence folder corresponding to the given descriptor path."""

    document = Scanner().read(absolute_path)
    folder_id = document.properties.folder_id
    if folder_id is None:
        raise ValueError(f"document does not have a folder ID assigned: {absolute_path}")
    return api.get_folder_properties(folder_id)


class MockConfluenceSessionV1(MockConfluenceSession):
    @property
    @override
    def supports_folders(self) -> bool:
        return False


class MockConfluenceAPIV1(MockConfluenceAPI):
    def __init__(self) -> None:
        self._session = MockConfluenceSessionV1()


class TestPublisher(unittest.TestCase):
    def test_document_hash_includes_converter_version(self) -> None:
        "Checks if the document hash changes when the library version changes."

        with _create_temporary_directory() as source_dir:
            document_path = source_dir / "index.md"
            document_path.write_text("# Document\n", encoding="utf-8")

            current_digest = DocumentHasher("1.0.0", AggregateOptions(), document_path).digest()
            previous_digest = DocumentHasher("2.0.0", AggregateOptions(), document_path).digest()

            self.assertNotEqual(current_digest, previous_digest)

    def get_processor_options(self, api: ConfluenceSession, *, keep_hierarchy: bool, skip_update: bool) -> ProcessorOptions:
        return ProcessorOptions(
            root_page=ConfluencePageID(api.get_homepage_id("SPACE_ID")),
            keep_hierarchy=keep_hierarchy,
            skip_update=skip_update,
            converter=ConverterOptions(
                render_drawio=False,
                render_mermaid=False,
                render_plantuml=False,
                render_latex=False,
            ),
        )

    def test_synchronize_directory(self) -> None:
        "Checks if a directory of Markdown files is synchronized to Confluence."

        parent_dir = Path(__file__).parent.parent
        sample_dir = parent_dir / "sample"
        docs_dir = sample_dir / "docs"
        figure_dir = sample_dir / "figure"

        markdown_count = len(list(sample_dir.rglob("*.md")))
        docs_count = len(list(docs_dir.rglob("*.*")))
        figure_count = len(list(figure_dir.rglob("*.*")))

        with MockConfluenceAPI() as api:
            publisher = Publisher(api, self.get_processor_options(api, keep_hierarchy=False, skip_update=True))
            publisher.process(sample_dir)

            # add one to account for homepage
            self.assertEqual(api.get_page_count(), markdown_count + 1)

            # display pre-rendering may generate images if Mermaid/PlantUML is installed
            self.assertGreaterEqual(api.get_attachment_count(), docs_count + figure_count)

            publisher.process(sample_dir)

    def _synchronize_attachment(
        self,
        *,
        remove_checksum_after_first_upload: bool,
        change_content: bool,
    ) -> None:
        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            document_path = source_dir / "index.md"
            attachment_path = source_dir / "diagram.png"
            document_path.write_text("# Diagram\n\n![diagram](diagram.png)\n", encoding="utf-8")
            attachment_data = (Path(__file__).parent / "source" / "figure" / "raster.png").read_bytes()
            attachment_path.write_bytes(attachment_data)

            publisher = Publisher(api, self.get_processor_options(api, keep_hierarchy=False, skip_update=True))
            publisher.process_directory(source_dir)

            page = api.get_page_properties_by_title("Diagram")
            attachment = api.get_attachment_by_name(page.id, "diagram.png")
            first_version = attachment.version.number

            if remove_checksum_after_first_upload:
                property = api.get_content_property_for_attachment(attachment.id, "md2conf")
                self.assertIsNotNone(property)
                if property is not None:
                    api.remove_content_property_from_attachment(attachment.id, property.id)
            if change_content:
                attachment_path.write_bytes(attachment_data[:-1] + bytes([attachment_data[-1] ^ 1]))
            publisher.process_directory(source_dir)
            changed_version = api.get_attachment_by_name(page.id, "diagram.png").version.number
            self.assertEqual(changed_version, first_version + 1)

            publisher.process_directory(source_dir)
            unchanged_version = api.get_attachment_by_name(page.id, "diagram.png").version.number
            self.assertEqual(unchanged_version, changed_version)

    def test_synchronize_same_size_attachment_by_checksum(self) -> None:
        """Checks if REST API v2 detects attachment changes whose byte length is unchanged."""

        self._synchronize_attachment(
            remove_checksum_after_first_upload=False,
            change_content=True,
        )

    def test_synchronize_repeated_attachment_reference(self) -> None:
        """Checks if an image shown several times on a page is uploaded only once."""

        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            document_path = source_dir / "index.md"
            attachment_path = source_dir / "diagram.png"
            document_path.write_text(
                "# Diagram\n\n" + "![diagram](diagram.png)\n\n" * 3,
                encoding="utf-8",
            )
            attachment_path.write_bytes((Path(__file__).parent / "source" / "figure" / "raster.png").read_bytes())

            publisher = Publisher(api, self.get_processor_options(api, keep_hierarchy=False, skip_update=True))
            publisher.process_directory(source_dir)

            page = api.get_page_properties_by_title("Diagram")
            first_version = api.get_attachment_by_name(page.id, "diagram.png").version.number
            self.assertEqual(first_version, 1)

            publisher.process_directory(source_dir)
            unchanged_version = api.get_attachment_by_name(page.id, "diagram.png").version.number
            self.assertEqual(unchanged_version, first_version)

    def test_initialize_missing_attachment_checksum(self) -> None:
        """Checks if REST API v2 initializes a missing checksum with one upload."""

        self._synchronize_attachment(
            remove_checksum_after_first_upload=True,
            change_content=False,
        )

    def test_update(self) -> None:
        "Checks if Markdown files are updated with a page ID when synchronized."

        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            documents: list[Path] = [
                source_dir / "index.md",
                source_dir / "doc1.md",
                source_dir / "doc2.md",
            ]

            for absolute_path in documents:
                # no front-matter to verify if documents with inferred title are handled correctly
                _create_document(absolute_path, source_dir, has_frontmatter=False)

            Publisher(api, self.get_processor_options(api, keep_hierarchy=False, skip_update=False)).process_directory(source_dir)
            self.assertEqual(api.get_page_count(), len(documents) + 1)  # add one for the homepage

            for absolute_path in reversed(documents):
                page = _get_page_for_document(api, absolute_path)
                api.delete_page(page.id)
            self.assertEqual(api.get_page_count(), 1)

    def test_hierarchy(self) -> None:
        "Checks if a matching Confluence page hierarchy is created from a directory tree of Markdown files."

        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            documents: list[Path] = [
                doc_a := source_dir / "index.md",
                doc_b := source_dir / "doc1.md",
                doc_c := source_dir / "doc2.md",
                # implicit := source_dir / "parent" / "index.md",  # this document is created on the fly
                doc_d := source_dir / "parent" / "nested" / "index.md",
                doc_e := source_dir / "parent" / "nested" / "doc3.md",
                doc_f := source_dir / "parent" / "nested" / "deep" / "index.md",
            ]

            for absolute_path in documents:
                _create_document(absolute_path, source_dir, has_frontmatter=True)

            Publisher(api, self.get_processor_options(api, keep_hierarchy=True, skip_update=False)).process_directory(source_dir)
            self.assertEqual(api.get_page_count(), len(documents) + 2)  # add one for the homepage and one for the implicitly created page

            page_a = _get_page_for_document(api, doc_a)
            page_b = _get_page_for_document(api, doc_b)
            page_c = _get_page_for_document(api, doc_c)
            page_d = _get_page_for_document(api, doc_d)
            page_e = _get_page_for_document(api, doc_e)
            page_f = _get_page_for_document(api, doc_f)

            self.assertEqual(page_a.parentId, api.get_homepage_id("SPACE_ID"))
            self.assertEqual(page_b.parentId, page_a.id)
            self.assertEqual(page_c.parentId, page_a.id)
            self.assertNotEqual(page_d.parentId, page_a.id)
            self.assertEqual(page_e.parentId, page_d.id)
            self.assertEqual(page_f.parentId, page_d.id)

            # order has files first, directories last, sorted by name
            self.assertEqual(page_b.position, 0)
            self.assertEqual(page_c.position, 1)
            self.assertEqual(page_e.position, 0)
            self.assertEqual(page_f.position, 1)

            self.assertIsNotNone(page_d.parentId)
            if page_d.parentId is not None:
                implicit_page = api.get_page_properties(page_d.parentId)
                self.assertEqual(page_d.parentId, implicit_page.id)
                self.assertEqual(implicit_page.parentId, page_a.id)
                self.assertEqual(implicit_page.position, 2)

    def test_folder_hierarchy(self) -> None:
        """Checks if metadata-only index documents create an idempotent folder hierarchy."""

        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            root_descriptor = source_dir / "index.md"
            guides_descriptor = source_dir / "guides" / "index.md"
            guide = source_dir / "guides" / "getting-started.md"
            root_descriptor.write_text("---\ntitle: Documentation\ncontent_type: folder\n---\n", encoding="utf-8")
            guides_descriptor.parent.mkdir()
            guides_descriptor.write_text("---\ntitle: Product Guides\ncontent_type: folder\n---\n", encoding="utf-8")
            guide.write_text("# Getting Started\n", encoding="utf-8")

            publisher = Publisher(api, self.get_processor_options(api, keep_hierarchy=True, skip_update=False))
            publisher.process_directory(source_dir)

            root_folder = _get_folder_for_document(api, root_descriptor)
            guides_folder = _get_folder_for_document(api, guides_descriptor)
            guide_page = _get_page_for_document(api, guide)
            self.assertEqual(api.get_folder_count(), 2)
            self.assertEqual(api.get_page_count(), 2)  # homepage and guide page
            self.assertEqual(root_folder.parentId, api.get_homepage_id("SPACE_ID"))
            self.assertEqual(guides_folder.parentId, root_folder.id)
            self.assertEqual(guide_page.parentId, guides_folder.id)
            self.assertNotIn("confluence-page-id", root_descriptor.read_text(encoding="utf-8"))
            self.assertIn(f"<!-- confluence-folder-id: {root_folder.id} -->", root_descriptor.read_text(encoding="utf-8"))
            self.assertNotIn("folder_id:", root_descriptor.read_text(encoding="utf-8"))

            publisher.process_directory(source_dir)
            self.assertEqual(api.get_folder_count(), 2)
            self.assertEqual(api.get_page_count(), 2)

    def test_reuse_existing_folder_by_title_and_parent(self) -> None:
        """Checks if an existing direct child folder is reused by implicit association."""

        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            homepage_id = api.get_homepage_id("SPACE_ID")
            existing = api.create_folder(title="Documentation", parent_id=homepage_id, space_id="SPACE_ID")
            descriptor = source_dir / "index.md"
            descriptor.write_text("---\ntitle: Documentation\ncontent_type: folder\n---\n", encoding="utf-8")

            Publisher(api, self.get_processor_options(api, keep_hierarchy=True, skip_update=False)).process_directory(source_dir)

            self.assertEqual(_get_folder_for_document(api, descriptor).id, existing.id)
            self.assertEqual(api.get_folder_count(), 1)

    def test_explicit_folder_id(self) -> None:
        """Checks if `folder_id` binds a descriptor to a folder without treating it as a page ID."""

        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            existing = api.create_folder(
                title="Documentation",
                parent_id=api.get_homepage_id("SPACE_ID"),
                space_id="SPACE_ID",
            )
            descriptor = source_dir / "index.md"
            descriptor.write_text(f'---\ntitle: Documentation\nfolder_id: "{existing.id}"\n---\n', encoding="utf-8")

            Publisher(api, self.get_processor_options(api, keep_hierarchy=True, skip_update=False)).process_directory(source_dir)

            self.assertEqual(api.get_folder_count(), 1)
            self.assertEqual(api.get_page_count(), 1)

    def test_folder_descriptor_rejects_markdown_body(self) -> None:
        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            (source_dir / "index.md").write_text("---\ncontent_type: folder\n---\n\nNot allowed.\n", encoding="utf-8")
            with self.assertRaisesRegex(PageError, "no Markdown body"):
                Publisher(api, self.get_processor_options(api, keep_hierarchy=True, skip_update=False)).process_directory(source_dir)

    def test_folder_descriptor_rejects_rest_api_v1(self) -> None:
        with MockConfluenceAPIV1() as api, _create_temporary_directory() as source_dir:
            (source_dir / "index.md").write_text("---\ncontent_type: folder\n---\n", encoding="utf-8")
            with self.assertRaisesRegex(PageError, "require REST API v2"):
                Publisher(api, self.get_processor_options(api, keep_hierarchy=True, skip_update=False)).process_directory(source_dir)

    def test_toplevel(self) -> None:
        "Checks if a missing top-level document is handled correctly."

        with MockConfluenceAPI() as api, _create_temporary_directory() as source_dir:
            documents: list[Path] = [
                doc_a := source_dir / "a" / "index.md",
                doc_b := source_dir / "a" / "doc.md",
                doc_c := source_dir / "b" / "skip" / "nested" / "index.md",
                doc_d := source_dir / "b" / "skip" / "nested" / "doc.md",
                doc_e := source_dir / "doc.md",
            ]

            for absolute_path in documents:
                _create_document(absolute_path, source_dir, has_frontmatter=True)

            Publisher(api, self.get_processor_options(api, keep_hierarchy=False, skip_update=False)).process_directory(source_dir)
            self.assertEqual(api.get_page_count(), len(documents) + 1)  # add one for the homepage

            page_a = _get_page_for_document(api, doc_a)
            page_b = _get_page_for_document(api, doc_b)
            page_c = _get_page_for_document(api, doc_c)
            page_d = _get_page_for_document(api, doc_d)
            page_e = _get_page_for_document(api, doc_e)

            homepage_id = api.get_homepage_id("SPACE_ID")
            self.assertEqual(page_a.parentId, homepage_id)
            self.assertEqual(page_b.parentId, page_a.id)
            self.assertEqual(page_c.parentId, homepage_id)
            self.assertEqual(page_d.parentId, page_c.id)
            self.assertEqual(page_e.parentId, homepage_id)

            # order has files first, directories last, sorted by name
            self.assertEqual(page_e.position, 0)
            self.assertEqual(page_a.position, 1)
            self.assertEqual(page_c.position, 2)
            self.assertEqual(page_b.position, 0)
            self.assertEqual(page_d.position, 0)

    def test_move_page_positions(self) -> None:
        "Checks if moving pages updates parent and child positions exactly as expected."

        with MockConfluenceAPI() as api:
            space_id = "SPACE_ID"
            homepage_id = api.get_homepage_id(space_id)

            page_a = api.create_page(title="A", content="", parent_id=homepage_id, space_id=space_id)
            page_b = api.create_page(title="B", content="", parent_id=homepage_id, space_id=space_id)
            page_c = api.create_page(title="C", content="", parent_id=homepage_id, space_id=space_id)
            page_parent = api.create_page(title="Parent", content="", parent_id=homepage_id, space_id=space_id)
            page_child = api.create_page(title="Child", content="", parent_id=page_parent.id, space_id=space_id)

            self.assertEqual(api.get_page_properties(page_a.id).position, 0)
            self.assertEqual(api.get_page_properties(page_b.id).position, 1)
            self.assertEqual(api.get_page_properties(page_c.id).position, 2)
            self.assertEqual(api.get_page_properties(page_parent.id).position, 3)
            self.assertEqual(api.get_page_properties(page_child.id).position, 0)

            api.move_page(page_c.id, "before", page_a.id)
            self.assertEqual(api.get_page_properties(page_c.id).position, 0)
            self.assertEqual(api.get_page_properties(page_a.id).position, 1)
            self.assertEqual(api.get_page_properties(page_b.id).position, 2)
            self.assertEqual(api.get_page_properties(page_parent.id).position, 3)

            api.move_page(page_a.id, "after", page_b.id)
            self.assertEqual(api.get_page_properties(page_c.id).position, 0)
            self.assertEqual(api.get_page_properties(page_b.id).position, 1)
            self.assertEqual(api.get_page_properties(page_a.id).position, 2)
            self.assertEqual(api.get_page_properties(page_parent.id).position, 3)

            api.move_page(page_b.id, "append", page_parent.id)

            moved_page = api.get_page_properties(page_b.id)
            child_page = api.get_page_properties(page_child.id)
            top_c = api.get_page_properties(page_c.id)
            top_a = api.get_page_properties(page_a.id)
            top_parent = api.get_page_properties(page_parent.id)

            self.assertEqual(moved_page.parentId, page_parent.id)
            self.assertEqual(moved_page.position, 1)
            self.assertEqual(child_page.position, 0)

            self.assertEqual(top_c.position, 0)
            self.assertEqual(top_a.position, 1)
            self.assertEqual(top_parent.position, 2)


if __name__ == "__main__":
    unittest.main()
