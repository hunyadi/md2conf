import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, List

from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageMetadata,
    ConfluenceQualifiedID,
    extract_qualified_id,
)
from .matcher import Matcher, MatcherOptions
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

        LOGGER.info(f"Synchronizing directory: {local_dir}")

        # Step 1: build index of all page metadata
        page_metadata: Dict[Path, ConfluencePageMetadata] = {}
        self._index_directory(local_dir, page_metadata)
        LOGGER.info(f"indexed {len(page_metadata)} page(s)")

        # Step 2: convert each page
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

    def _index_directory(
        self,
        local_dir: Path,
        page_metadata: Dict[Path, ConfluencePageMetadata],
    ) -> None:
        "Indexes Markdown files in a directory recursively."

        LOGGER.info(f"Indexing directory: {local_dir}")

        matcher = Matcher(MatcherOptions(source=".mdignore", extension="md"), local_dir)

        files: List[Path] = []
        directories: List[Path] = []
        for entry in os.scandir(local_dir):
            if matcher.is_excluded(entry.name, entry.is_dir()):
                continue

            if entry.is_file():
                files.append((Path(local_dir) / entry.name).absolute())
            elif entry.is_dir():
                directories.append((Path(local_dir) / entry.name).absolute())

        for doc in files:
            metadata = self._get_page(doc)
            LOGGER.debug(f"indexed {doc} with metadata: {metadata}")
            page_metadata[doc] = metadata

        for directory in directories:
            self._index_directory(Path(local_dir) / directory, page_metadata)

    def _get_page(self, absolute_path: Path) -> ConfluencePageMetadata:
        "Extracts metadata from a Markdown file."

        with open(absolute_path, "r", encoding="utf-8") as f:
            document = f.read()

        qualified_id, document = extract_qualified_id(document)
        if qualified_id is None:
            if self.options.root_page_id is not None:
                hash = hashlib.md5(document.encode("utf-8"))
                digest = "".join(f"{c:x}" for c in hash.digest())
                LOGGER.info(f"Identifier '{digest}' assigned to page: {absolute_path}")
                qualified_id = ConfluenceQualifiedID(digest)
            else:
                raise ValueError("required: page ID for local output")

        return ConfluencePageMetadata(
            domain=self.properties.domain,
            base_path=self.properties.base_path,
            page_id=qualified_id.page_id,
            space_key=qualified_id.space_key or self.properties.space_key,
            title="",
        )
