import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from md2conf.converter import ConfluenceDocument
from md2conf.metadata import ConfluenceSiteMetadata
from md2conf.options import ConfluencePageID, DocumentOptions
from md2conf.processor import DocumentNode, Processor
from md2conf.scanner import Scanner
from md2conf.types import SynchronizableDocument


class MockProcessor(Processor):
    def _synchronize_tree(self, tree: DocumentNode, root_id: ConfluencePageID | None) -> None:
        pass

    def _update_page(self, page_id: ConfluencePageID, document: ConfluenceDocument, path: Path) -> None:
        pass


class TestSynchronizeCallable(unittest.TestCase):
    def test_metadata_passthrough(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntitle: Test\ncustom_field: value\n---\nBody")

            scanner = Scanner()
            doc = scanner.read(md_file)
            assert doc.properties.metadata is not None
            self.assertEqual(doc.properties.metadata["custom_field"], "value")

    def test_synchronize_if_callable(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntitle: Test\nsync_me: true\n---\nBody")

            def sync_filter(props: SynchronizableDocument, options: DocumentOptions) -> bool:
                assert props.metadata is not None
                self.assertEqual(props.absolute_path, md_file)
                return props.metadata.get("sync_me") is True

            options = DocumentOptions(synchronize_if=sync_filter)
            site = ConfluenceSiteMetadata(domain="test.atlassian.net", base_path="/wiki/", space_key="TEST")

            processor = MockProcessor(options, site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

            # Test False case
            with open(md_file, "w") as f:
                f.write("---\ntitle: Test\nsync_me: false\n---\nBody")

            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)

    def test_synchronize_if_with_params(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntitle: Test\n---\nBody")

            def sync_filter(props: SynchronizableDocument, options: DocumentOptions) -> bool:
                return options.params.get("allow_sync") is True

            options = DocumentOptions(synchronize_if=sync_filter, params={"allow_sync": True})
            site = ConfluenceSiteMetadata(domain="test.atlassian.net", base_path="/wiki/", space_key="TEST")

            processor = MockProcessor(options, site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

            options.params["allow_sync"] = False
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)

    def test_synchronize_if_raises(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntitle: Test\n---\nBody")

            def sync_filter(props: SynchronizableDocument, options: DocumentOptions) -> bool:
                raise ValueError("Custom error")

            options = DocumentOptions(synchronize_if=sync_filter)
            site = ConfluenceSiteMetadata(domain="test.atlassian.net", base_path="/wiki/", space_key="TEST")

            processor = MockProcessor(options, site, tmp_path)
            # Should not raise exception
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)

    def test_synchronize_if_none(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            # Default case (no frontmatter)
            with open(md_file, "w") as f:
                f.write("Body")

            options = DocumentOptions(synchronize_if=None)
            site = ConfluenceSiteMetadata(domain="test.atlassian.net", base_path="/wiki/", space_key="TEST")

            processor = MockProcessor(options, site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

            # Frontmatter false
            with open(md_file, "w") as f:
                f.write("---\nsynchronized: false\n---\nBody")
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)

    def test_synchronize_if_non_boolean_fails(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("Body")

            def sync_filter(props: SynchronizableDocument, options: DocumentOptions) -> bool:
                return "yes"  # type: ignore

            options = DocumentOptions(synchronize_if=sync_filter)
            site = ConfluenceSiteMetadata(domain="test.atlassian.net", base_path="/wiki/", space_key="TEST")

            processor = MockProcessor(options, site, tmp_path)
            # Should be False because non-boolean return is treated as error
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)

    def test_precedence_frontmatter_wins(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            # Frontmatter has synchronized: false, predicate returns True
            with open(md_file, "w") as f:
                f.write("---\nsynchronized: false\n---\nBody")

            def sync_filter(props: SynchronizableDocument, options: DocumentOptions) -> bool:
                return True

            options = DocumentOptions(synchronize_if=sync_filter)
            site = ConfluenceSiteMetadata(domain="test.atlassian.net", base_path="/wiki/", space_key="TEST")

            processor = MockProcessor(options, site, tmp_path)
            # Frontmatter should win
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)


if __name__ == "__main__":
    unittest.main()
