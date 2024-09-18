import logging
import os
import shutil
import unittest
from pathlib import Path

from md2conf.mermaid import has_mmdc, render


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

MERMAID_SOURCE = """
graph TD
  C{ How to contribute? }
  C --> D[ Reporting bugs ]
  C --> E[ Sharing ideas ]
"""


@unittest.skipUnless(has_mmdc(), "mmdc is not available")
class TestMermaidRendering(unittest.TestCase):
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

    def test_render_simple_svg(self) -> None:
        svg = render(MERMAID_SOURCE, output_format="svg").decode()

        self.assertIn("transform=", svg)
        self.assertIn("translate(", svg)
        self.assertIn("<rect height=", svg)

    def test_render_simple_png(self) -> None:
        png = render(MERMAID_SOURCE)
        self.assertIn(b"PNG", png)


if __name__ == "__main__":
    unittest.main()
