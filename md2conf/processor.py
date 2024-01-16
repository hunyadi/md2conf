import logging
import os.path
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

    def process(self, path: str) -> None:
        "Processes a single Markdown file or a directory of Markdown files."

        if os.path.isdir(path):
            self.process_directory(path)
        elif os.path.isfile(path):
            self.process_page(path, {})
        else:
            raise ValueError(f"expected: valid file or directory path; got: {path}")

    def process_directory(self, dir: str) -> None:
        "Recursively scans a directory hierarchy for Markdown files."

        page_metadata: Dict[str, ConfluencePageMetadata] = {}
        LOGGER.info(f"Synchronizing directory: {dir}")

        # Step 1: build index of all page metadata
        for root, directories, files in os.walk(dir):
            for file_name in files:
                # check the file extension
                _, file_extension = os.path.splitext(file_name)
                if file_extension.lower() != ".md":
                    continue

                absolute_path = os.path.join(os.path.abspath(root), file_name)
                metadata = self._get_page(absolute_path)

                LOGGER.debug(f"indexed {absolute_path} with metadata: {metadata}")
                page_metadata[absolute_path] = metadata

        LOGGER.info(f"indexed {len(page_metadata)} pages")

        # Step 2: Convert each page
        for page_path in page_metadata.keys():
            self.process_page(page_path, page_metadata)

    def process_page(
        self, path: str, page_metadata: Dict[str, ConfluencePageMetadata]
    ) -> None:
        "Processes a single Markdown file."

        document = ConfluenceDocument(path, self.options, page_metadata)
        content = document.xhtml()
        output_path, _ = os.path.splitext(path)
        with open(f"{output_path}.csf", "w") as f:
            f.write(content)

    def _get_page(self, absolute_path: str) -> ConfluencePageMetadata:
        "Extracts metadata from a Markdown file."

        with open(absolute_path, "r") as f:
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
