"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest
from pathlib import Path

from md2conf.options import ConfluencePageID, ConverterOptions, ProcessorOptions
from md2conf.publisher import Publisher
from tests.api import MockConfluenceSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestPublisher(unittest.TestCase):
    def test_process_sample_directory(self) -> None:
        parent_dir = Path(__file__).parent.parent
        sample_dir = parent_dir / "sample"
        docs_dir = sample_dir / "docs"
        figure_dir = sample_dir / "figure"

        markdown_count = len(list(sample_dir.rglob("*.md")))
        docs_count = len(list(docs_dir.rglob("*.*")))
        figure_count = len(list(figure_dir.rglob("*.*")))

        session = MockConfluenceSession()

        options = ProcessorOptions(
            root_page=ConfluencePageID(session.get_homepage_id("SPACE_ID")),
            skip_update=True,
            converter=ConverterOptions(
                render_drawio=False,
                render_mermaid=False,
                render_plantuml=False,
                render_latex=False,
            ),
        )

        publisher = Publisher(session, options)
        publisher.process(sample_dir)

        self.assertEqual(session.get_page_count(), markdown_count + 1)  # add one for the homepage
        self.assertEqual(session.get_attachment_count(), docs_count + figure_count)

        publisher.process(sample_dir)


if __name__ == "__main__":
    unittest.main()
