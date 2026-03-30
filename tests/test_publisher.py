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
from md2conf.api_types import ConfluencePageProperties
from md2conf.options import ConfluencePageID, ConverterOptions, ProcessorOptions
from md2conf.publisher import Publisher
from md2conf.scanner import Scanner
from tests.api import MockConfluenceAPI

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


class TestPublisher(unittest.TestCase):
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

            self.assertIsNotNone(page_d.parentId)
            if page_d.parentId is not None:
                implicit_page = api.get_page_properties(page_d.parentId)
                self.assertEqual(page_d.parentId, implicit_page.id)
                self.assertEqual(implicit_page.parentId, page_a.id)

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


if __name__ == "__main__":
    unittest.main()
