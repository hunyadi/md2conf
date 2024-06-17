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

    def test_mermaid(self) -> None:
        actual = ConfluenceDocument(
            self.sample_dir / "with_mermaid.md",
            ConfluenceDocumentOptions(
                ignore_invalid_url=True,
                render_mermaid=False,
            ),
            {},
        ).xhtml()
        actual = self.make_canonical(actual)

        with open(self.sample_dir / "expected" / "with_mermaid.xml", "r") as f:
            expected = f.read().strip()

        self.assertEqual(actual, expected)

    def test_mermaid_with_kroki(self) -> None:
        document = ConfluenceDocument(
            self.sample_dir / "with_mermaid.md",
            ConfluenceDocumentOptions(
                ignore_invalid_url=True,
                render_mermaid=True,
                kroki_output_format='svg'
            ),
            {},
        )

        self.assertIn('embedded_70e2677fa2ad7c42464193fe5d7f8eb1.svg', document.embedded_images)

    def test_mermaid_with_kroki_png(self) -> None:
        document = ConfluenceDocument(
            self.sample_dir / "with_mermaid.md",
            ConfluenceDocumentOptions(
                ignore_invalid_url=True,
                render_mermaid=True,
                kroki_output_format='png'
            ),
            {},
        )

        self.assertIn('embedded_d953c781dcc5da4e8e8da4dd3af2e082.png', document.embedded_images)



if __name__ == "__main__":
    unittest.main()
