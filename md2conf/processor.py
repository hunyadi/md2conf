import logging
import os
from pathlib import Path
from typing import Dict

from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageMetadata,
    extract_qualified_id,
)
from .properties import ConfluenceProperties

LOGGER = logging.getLogger(__name__)


class Processor:
    options: ConfluenceDocumentOptions
    properties: ConfluenceProperties

    def __init__(
        self, options: ConfluenceDocumentOptions, properties: ConfluenceProperties
    ) -> None:
        self.options = options
        self.properties = properties

    def process(self, path: Path) -> None:
        "Processes a single Markdown file or a directory of Markdown files."

        if path.is_dir():
            self.process_directory(path)
        elif path.is_file():
            self.process_page(path, {})
        else:
            raise ValueError(f"expected: valid file or directory path; got: {path}")

    def process_directory(self, local_dir: Path) -> None:
        "Recursively scans a directory hierarchy for Markdown files."

        page_metadata: Dict[Path, ConfluencePageMetadata] = {}
        LOGGER.info(f"Synchronizing directory: {local_dir}")

        # Step 1: build index of all page metadata
        # NOTE: Pathlib.walk() is implemented only in Python 3.12+
        # so sticking for old os.walk
        for root, directories, files in os.walk(local_dir):
            for file_name in files:
                # Reconstitute Path object back
                docfile = (Path(root) / file_name).absolute()

                # Skip non-markdown files
                if docfile.suffix.lower() != ".md":
                    continue

                metadata = self._get_page(docfile)
                LOGGER.debug(f"indexed {docfile} with metadata: {metadata}")
                page_metadata[docfile] = metadata

        LOGGER.info(f"indexed {len(page_metadata)} pages")

        # Step 2: Convert each page
        for page_path in page_metadata.keys():
            self.process_page(page_path, page_metadata)

    def process_page(
        self, path: Path, page_metadata: Dict[Path, ConfluencePageMetadata]
    ) -> None:
        "Processes a single Markdown file."

        document = ConfluenceDocument(path, self.options, page_metadata)
        content = document.xhtml()
        with open(path.with_suffix(".csf"), "w", encoding="utf-8") as f:
            f.write(content)

    def _get_page(self, absolute_path: Path) -> ConfluencePageMetadata:
        "Extracts metadata from a Markdown file."

        with open(absolute_path, "r", encoding="utf-8") as f:
            document = f.read()

        qualified_id, document = extract_qualified_id(document)
        if qualified_id is None:
            raise ValueError("required: page ID for local output")

        return ConfluencePageMetadata(
            domain=self.properties.domain,
            base_path=self.properties.base_path,
            page_id=qualified_id.page_id,
            space_key=qualified_id.space_key or self.properties.space_key,
            title="",
        )
