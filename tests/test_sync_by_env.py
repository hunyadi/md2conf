"""
Tests for a use-case of the Selective Synchronization feature.

This test demonstrates how to synchronize documents based on target environment,
as described in the README.
"""

import unittest
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


def sync_by_env(props: SynchronizableDocument, options: DocumentOptions) -> bool:
    # Get current environment from CLI params (defaults to 'dev')
    env = options.params.get("environment", "dev").lower()

    # Get target environments from front-matter
    if props.metadata is None:
        return True
    targets = props.metadata.get("target_environments")

    # If target_environments is not found, return True
    if targets is None:
        return True
    # If target_environments is not a list, raise an exception
    if not isinstance(targets, list):
        raise ValueError("target_environments must be a list")

    # Case-insensitive check if current env is in targets
    return any(env == t.lower() for t in targets if isinstance(t, str))


class TestSyncByEnv(unittest.TestCase):
    def setUp(self) -> None:
        self.site = ConfluenceSiteMetadata(domain="test.atlassian.net", base_path="/wiki/", space_key="TEST")

    def test_sync_by_env_match(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntarget_environments: [prod, staging]\n---\nBody")

            options = DocumentOptions(synchronize_if=sync_by_env, params={"environment": "PROD"})
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

    def test_sync_by_env_no_match(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntarget_environments: [prod]\n---\nBody")

            options = DocumentOptions(synchronize_if=sync_by_env, params={"environment": "dev"})
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)

    def test_sync_by_env_missing_metadata(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntitle: Only Title\n---\nBody")

            options = DocumentOptions(synchronize_if=sync_by_env, params={"environment": "prod"})
            processor = MockProcessor(options, self.site, tmp_path)
            node = processor._index_file(md_file)
            self.assertTrue(node.synchronized)

    def test_sync_by_env_invalid_type(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            md_file = tmp_path / "test.md"
            with open(md_file, "w") as f:
                f.write("---\ntarget_environments: prod\n---\nBody")

            options = DocumentOptions(synchronize_if=sync_by_env, params={"environment": "prod"})
            processor = MockProcessor(options, self.site, tmp_path)
            # Should fail gracefully due to ValueError in sync_by_env
            node = processor._index_file(md_file)
            self.assertFalse(node.synchronized)


if __name__ == "__main__":
    unittest.main()
