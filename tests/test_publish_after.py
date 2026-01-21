import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from md2conf.converter import ConfluenceDocument
from md2conf.metadata import ConfluenceSiteMetadata
from md2conf.options import ConfluencePageID, DocumentOptions
from md2conf.processor import DocumentNode, Processor
from md2conf.types import SynchronizableDocument


class MockProcessor(Processor):
    def _synchronize_tree(self, tree: DocumentNode, root_id: ConfluencePageID | None) -> None:
        pass

    def _update_page(self, page_id: ConfluencePageID, document: ConfluenceDocument, path: Path) -> None:
        pass


def publish_after(props: SynchronizableDocument, options: DocumentOptions) -> bool:
    # Bypass check if --params ignore_publish_after=True is set
    if options.params.get("ignore_publish_after") == "True":
        return True

    # Get publish_after timestamp from front-matter
    if props.metadata is None:
        return True
    publish_after_val = props.metadata.get("publish_after")
    if not publish_after_val:
        return True

    if isinstance(publish_after_val, datetime):
        publish_time = publish_after_val
        if publish_time.tzinfo is None:
            publish_time = publish_time.replace(tzinfo=timezone.utc)
    else:
        # Assume string
        publish_time = datetime.fromisoformat(str(publish_after_val).replace("Z", "+00:00"))

    # Use fixed 'now' from params for consistency, or fallback to current time
    now_str = options.params.get("now")
    if now_str:
        now = datetime.fromisoformat(now_str.replace("Z", "+00:00"))
    else:
        now = datetime.now(timezone.utc)

    # Compare with publish time
    return now >= publish_time


class TestPublishAfter(unittest.TestCase):
    def setUp(self) -> None:
        self.site = ConfluenceSiteMetadata(domain="test.atlassian.net", base_path="/wiki/", space_key="TEST")

    def test_publish_after_future(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                # 2099 is definitely in the future
                f.write("---\npublish_after: 2099-01-01T00:00:00Z\n---\nBody")

            options = DocumentOptions(synchronize_if=publish_after)
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)

    def test_publish_after_past(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                # 2000 is definitely in the past
                f.write("---\npublish_after: 2000-01-01T00:00:00Z\n---\nBody")

            options = DocumentOptions(synchronize_if=publish_after)
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

    def test_publish_after_missing_metadata(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntitle: Only Title\n---\nBody")

            options = DocumentOptions(synchronize_if=publish_after)
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

    def test_publish_after_ignore_bypass(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\npublish_after: 2099-01-01T00:00:00Z\n---\nBody")

            options = DocumentOptions(synchronize_if=publish_after, params={"ignore_publish_after": "True"})
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

    def test_publish_after_consistency_now(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\npublish_after: 2026-01-21T12:00:00Z\n---\nBody")

            # Case: fixed now is after publish_after
            options = DocumentOptions(synchronize_if=publish_after, params={"now": "2026-01-21T12:00:01Z"})
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

            # Case: fixed now is before publish_after
            options = DocumentOptions(synchronize_if=publish_after, params={"now": "2026-01-21T11:59:59Z"})
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)


if __name__ == "__main__":
    unittest.main()
