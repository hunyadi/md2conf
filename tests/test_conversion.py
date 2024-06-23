import logging
import os
import os.path
import re
import shutil
import unittest
from pathlib import Path

from md2conf.converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestConversion(unittest.TestCase):
    out_dir: Path

    def setUp(self) -> None:
        self.maxDiff = 1024

        test_dir = Path(__file__).parent
        parent_dir = test_dir.parent

        self.out_dir = test_dir / "output"
        self.sample_dir = parent_dir / "sample"
        os.makedirs(self.out_dir, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.out_dir)

    @staticmethod
    def make_canonical(content: str) -> str:
        uuid_pattern = re.compile(r'\b[0-9a-fA-F-]{36}\b')
        content = re.sub(uuid_pattern, 'UUID', content)
        content = content.strip()
        return content

    def test_markdown(self) -> None:
        actual = ConfluenceDocument(
            self.sample_dir / "example.md",
            ConfluenceDocumentOptions(ignore_invalid_url=True),
            {},
        ).xhtml()
        actual = self.make_canonical(actual)

        with open(self.sample_dir / "expected" / "example.xml", "r") as f:
            expected = f.read().strip()

        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
