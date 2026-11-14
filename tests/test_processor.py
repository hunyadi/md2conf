"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import shutil
import unittest
from pathlib import Path

from md2conf.api_types import ConfluenceContentType, ConfluenceTypedID
from md2conf.compatibility import override
from md2conf.local import LocalConverter, LocalProcessor
from md2conf.metadata import ConfluenceSiteMetadata
from md2conf.options import ConfluencePageID, Markdown, ProcessorOptions
from md2conf.options_converter import ConverterOptions
from md2conf.processor import Node, ProcessorError
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestProcessor(TypedTestCase):
    out_dir: Path
    sample_dir: Path

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

    def create_converter(self, options: ProcessorOptions) -> LocalConverter:
        site_metadata = ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY")
        return LocalConverter(options, site_metadata, self.out_dir)

    def test_process_document(self) -> None:
        options = ProcessorOptions(
            root_page=ConfluencePageID("None"),
        )
        self.create_converter(options).process(self.sample_dir / "code.md")

        self.assertTrue((self.out_dir / "code.csf").is_file())
        self.assertFalse((self.sample_dir / "code.csf").is_file())

    def test_process_directory(self) -> None:
        options = ProcessorOptions(
            root_page=ConfluencePageID("ROOT_PAGE_ID"),
            converter=ConverterOptions(
                render_drawio=False,
                render_mermaid=False,
                render_plantuml=False,
                render_latex=False,
            ),
        )

        self.create_converter(options).process(self.sample_dir)

        self.assertTrue((self.out_dir / "index.csf").is_file())
        self.assertTrue((self.out_dir / "sibling.csf").is_file())
        self.assertTrue((self.out_dir / "code.csf").is_file())
        self.assertTrue((self.out_dir / "parent" / "child.csf").is_file())
        self.assertFalse((self.sample_dir / "index.csf").is_file())

    def test_generated_by(self) -> None:
        options = ProcessorOptions(
            title_prefix="[PAGE]",  # impacts only Confluence title
            generated_by=Markdown("<&> This page has been **generated** with [md2conf](https://github.com/hunyadi/md2conf)"),
            root_page=ConfluencePageID("ROOT_PAGE_ID"),
            converter=ConverterOptions(
                render_drawio=False,
                render_mermaid=False,
                render_plantuml=False,
                render_latex=False,
            ),
        )
        self.create_converter(options).process(self.sample_dir / "index.md")

        csf_path = self.out_dir / "index.csf"
        self.assertTrue(csf_path.exists())
        content = csf_path.read_text(encoding="utf-8")

        generated_by_html = (
            '<ac:structured-macro ac:name="info" ac:schema-version="1">'
            "<ac:rich-text-body>"
            '<p>&lt;&amp;&gt; This page has been <strong>generated</strong> with <a href="https://github.com/hunyadi/md2conf">md2conf</a></p>'
            "</ac:rich-text-body>"
            "</ac:structured-macro>"
        )
        self.assertStartsWith(content, generated_by_html)
        self.assertNotIn("[PAGE]", content)


class TestValidation(unittest.TestCase):
    def create_processor(self) -> LocalProcessor:
        return LocalProcessor(
            ProcessorOptions(keep_hierarchy=True),
            ConfluenceSiteMetadata(domain="example.com", base_path="/wiki/", space_key="SPACE_KEY"),
            out_dir=None,
            root_dir=Path(__file__).parent,
        )

    def create_node(self, path: Path, title: str, object_id: str | None = None, *, content_type: ConfluenceContentType = ConfluenceContentType.PAGE) -> Node:
        return Node(
            absolute_path=Path(__file__).parent / path,
            object_id=ConfluenceTypedID(object_id, content_type) if object_id is not None else None,
            content_type=content_type,
            title=title,
        )

    def test_duplicate_page_ids_rejected(self) -> None:
        root = self.create_node(Path("index.md"), "Root folder", "123", content_type=ConfluenceContentType.FOLDER)
        first = self.create_node(Path("first.md"), "First page", "123")
        second = self.create_node(Path("second.md"), "Second page", "123")
        nested = self.create_node(Path("nested") / "index.md", "Nested folder")
        third = self.create_node(Path("nested") / "third.md", "Third page", "123")
        fourth = self.create_node(Path("fourth.md"), "Fourth page", "456")
        fifth = self.create_node(Path("fifth.md"), "Fifth page", "456")
        root.add_child(first)
        root.add_child(second)
        root.add_child(nested)
        root.add_child(fourth)
        root.add_child(fifth)
        nested.add_child(third)

        processor = self.create_processor()
        with self.assertRaises(ProcessorError) as raised:
            processor.check_documents(root)

        for node in (root, first, second, third, fourth, fifth):
            self.assertIn(str(node.absolute_path), str(raised.exception))
        self.assertEqual(len(processor.page_metadata), 0)

    def test_duplicate_titles_rejected(self) -> None:
        root = self.create_node(Path("index.md"), "Root node")
        first = self.create_node(Path("first.md"), "Same title", "123")
        second = self.create_node(Path("second.md"), "Same title", "456")
        root.add_child(first)
        root.add_child(second)

        with self.assertRaises(ProcessorError) as raised:
            self.create_processor().check_documents(root)

        for node in (first, second):
            self.assertIn(str(node.absolute_path), str(raised.exception))

    def test_distinct_and_missing_page_ids_with_folder_ids(self) -> None:
        root = self.create_node(Path("index.md"), "Root folder", "100", content_type=ConfluenceContentType.FOLDER)
        nested = self.create_node(Path("nested") / "index.md", "Nested folder", "200", content_type=ConfluenceContentType.FOLDER)
        root.add_child(nested)
        root.add_child(self.create_node(Path("first.md"), "First", "123"))
        root.add_child(self.create_node(Path("second.md"), "Second", "456"))
        nested.add_child(self.create_node(Path("nested") / "third.md", "Third"))
        nested.add_child(self.create_node(Path("nested") / "fourth.md", "Fourth"))

        self.create_processor().check_documents(root)


if __name__ == "__main__":
    unittest.main()
