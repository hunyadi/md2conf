"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageMetadata,
    ConfluenceQualifiedID,
    ConfluenceSiteMetadata,
    extract_qualified_id,
)
from .matcher import Matcher, MatcherOptions
from .properties import ArgumentError

LOGGER = logging.getLogger(__name__)


class Processor:
    options: ConfluenceDocumentOptions
    site_metadata: ConfluenceSiteMetadata

    def __init__(
        self, options: ConfluenceDocumentOptions, site_metadata: ConfluenceSiteMetadata
    ) -> None:
        self.options = options
        self.site_metadata = site_metadata

    def process(self, path: Path) -> None:
        "Processes a single Markdown file or a directory of Markdown files."

        path = path.resolve(True)
        if path.is_dir():
            self.process_directory(path)
        elif path.is_file():
            self.process_page(path)
        else:
            raise ArgumentError(f"expected: valid file or directory path; got: {path}")

    def process_directory(
        self, local_dir: Path, root_dir: Optional[Path] = None
    ) -> None:
        "Recursively scans a directory hierarchy for Markdown files."

        local_dir = local_dir.resolve(True)
        if root_dir is None:
            root_dir = local_dir
        else:
            root_dir = root_dir.resolve(True)

        LOGGER.info("Synchronizing directory: %s", local_dir)

        # Step 1: build index of all page metadata
        page_metadata: dict[Path, ConfluencePageMetadata] = {}
        self._index_directory(local_dir, page_metadata)
        LOGGER.info("Indexed %d page(s)", len(page_metadata))

        # Step 2: convert each page
        for page_path in page_metadata.keys():
            self._process_page(page_path, root_dir, page_metadata)

    def process_page(self, path: Path, root_dir: Optional[Path] = None) -> None:
        "Processes a single Markdown file."

        path = path.resolve(True)
        if root_dir is None:
            root_dir = path.parent
        else:
            root_dir = root_dir.resolve(True)

        self._process_page(path, root_dir, {})

    def _process_page(
        self,
        path: Path,
        root_dir: Path,
        page_metadata: dict[Path, ConfluencePageMetadata],
    ) -> None:
        "Processes a single Markdown file."

        document = ConfluenceDocument.create(
            path, self.options, root_dir, self.site_metadata, page_metadata
        )
        content = document.xhtml()
        with open(path.with_suffix(".csf"), "w", encoding="utf-8") as f:
            f.write(content)

    def _index_directory(
        self,
        local_dir: Path,
        page_metadata: dict[Path, ConfluencePageMetadata],
    ) -> None:
        "Indexes Markdown files in a directory recursively."

        LOGGER.info("Indexing directory: %s", local_dir)

        matcher = Matcher(MatcherOptions(source=".mdignore", extension="md"), local_dir)

        files: list[Path] = []
        directories: list[Path] = []
        for entry in os.scandir(local_dir):
            if matcher.is_excluded(entry.name, entry.is_dir()):
                continue

            if entry.is_file():
                files.append(Path(local_dir) / entry.name)
            elif entry.is_dir():
                directories.append(Path(local_dir) / entry.name)

        for doc in files:
            metadata = self._get_page(doc)
            LOGGER.debug("Indexed %s with metadata: %s", doc, metadata)
            page_metadata[doc] = metadata

        for directory in directories:
            self._index_directory(directory, page_metadata)

    def _get_page(self, absolute_path: Path) -> ConfluencePageMetadata:
        "Extracts metadata from a Markdown file."

        with open(absolute_path, "r", encoding="utf-8") as f:
            document = f.read()

        qualified_id, document = extract_qualified_id(document)
        if qualified_id is None:
            if self.options.root_page_id is not None:
                hash = hashlib.md5(document.encode("utf-8"))
                digest = "".join(f"{c:x}" for c in hash.digest())
                LOGGER.info("Identifier %s assigned to page: %s", digest, absolute_path)
                qualified_id = ConfluenceQualifiedID(digest)
            else:
                raise ArgumentError("required: page ID for local output")

        return ConfluencePageMetadata(
            page_id=qualified_id.page_id,
            space_key=qualified_id.space_key,
            title="",
        )
