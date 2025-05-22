"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
from abc import abstractmethod
from pathlib import Path
from typing import Optional

from .converter import ConfluenceDocument, ConfluenceDocumentOptions, ConfluencePageID
from .matcher import Matcher, MatcherOptions
from .metadata import ConfluencePageMetadata, ConfluenceSiteMetadata
from .properties import ArgumentError

LOGGER = logging.getLogger(__name__)


class Processor:
    """
    Processes a single Markdown page or a directory of Markdown pages.
    """

    options: ConfluenceDocumentOptions
    site: ConfluenceSiteMetadata
    root_dir: Path

    page_metadata: dict[Path, ConfluencePageMetadata]

    def __init__(
        self,
        options: ConfluenceDocumentOptions,
        site: ConfluenceSiteMetadata,
        root_dir: Path,
    ) -> None:
        self.options = options
        self.site = site
        self.root_dir = root_dir

        self.page_metadata = {}

    def process_directory(self, local_dir: Path) -> None:
        """
        Recursively scans a directory hierarchy for Markdown files, and processes each, resolving cross-references.
        """

        local_dir = local_dir.resolve(True)
        LOGGER.info("Processing directory: %s", local_dir)

        # Step 1: build index of all page metadata
        self._index_directory(local_dir, self.options.root_page_id)
        LOGGER.info("Indexed %d page(s)", len(self.page_metadata))

        # Step 2: convert each page
        for page_path in self.page_metadata.keys():
            self._process_page(page_path)

    def process_page(self, path: Path) -> None:
        """
        Processes a single Markdown file.
        """

        LOGGER.info("Processing page: %s", path)
        self._index_page(path, self.options.root_page_id)
        self._process_page(path)

    def _process_page(self, path: Path) -> None:
        page_id, document = ConfluenceDocument.create(
            path, self.options, self.root_dir, self.site, self.page_metadata
        )
        self._save_document(page_id, document, path)

    @abstractmethod
    def _get_or_create_page(
        self, absolute_path: Path, parent_id: Optional[ConfluencePageID]
    ) -> ConfluencePageMetadata:
        """
        Creates a new Confluence page if no page is linked in the Markdown document.
        """
        ...

    @abstractmethod
    def _save_document(
        self, page_id: ConfluencePageID, document: ConfluenceDocument, path: Path
    ) -> None: ...

    def _index_directory(
        self, local_dir: Path, parent_id: Optional[ConfluencePageID]
    ) -> None:
        """
        Indexes Markdown files in a directory hierarchy recursively.
        """

        LOGGER.info("Indexing directory: %s", local_dir)

        matcher = Matcher(MatcherOptions(source=".mdignore", extension="md"), local_dir)

        files: list[Path] = []
        directories: list[Path] = []
        for entry in os.scandir(local_dir):
            if matcher.is_excluded(entry):
                continue

            if entry.is_file():
                files.append(Path(local_dir) / entry.name)
            elif entry.is_dir():
                directories.append(Path(local_dir) / entry.name)

        # make page act as parent node
        parent_doc: Optional[Path] = None
        if (Path(local_dir) / "index.md") in files:
            parent_doc = Path(local_dir) / "index.md"
        elif (Path(local_dir) / "README.md") in files:
            parent_doc = Path(local_dir) / "README.md"
        elif (Path(local_dir) / f"{local_dir.name}.md") in files:
            parent_doc = Path(local_dir) / f"{local_dir.name}.md"

        if parent_doc is None and self.options.keep_hierarchy:
            parent_doc = Path(local_dir) / "index.md"

            # create a blank page for directory entry
            with open(parent_doc, "w"):
                pass

        if parent_doc is not None:
            if parent_doc in files:
                files.remove(parent_doc)

            # use latest parent as parent for index page
            metadata = self._get_or_create_page(parent_doc, parent_id)
            LOGGER.debug("Indexed parent %s with metadata: %s", parent_doc, metadata)
            self.page_metadata[parent_doc] = metadata

            # assign new index page as new parent
            parent_id = ConfluencePageID(metadata.page_id)

        for doc in files:
            self._index_page(doc, parent_id)

        for directory in directories:
            self._index_directory(directory, parent_id)

    def _index_page(self, path: Path, parent_id: Optional[ConfluencePageID]) -> None:
        """
        Indexes a single Markdown file.
        """

        metadata = self._get_or_create_page(path, parent_id)
        LOGGER.debug("Indexed %s with metadata: %s", path, metadata)
        self.page_metadata[path] = metadata


class ProcessorFactory:
    options: ConfluenceDocumentOptions
    site: ConfluenceSiteMetadata

    def __init__(
        self, options: ConfluenceDocumentOptions, site: ConfluenceSiteMetadata
    ) -> None:
        self.options = options
        self.site = site

    @abstractmethod
    def create(self, root_dir: Path) -> Processor: ...


class Converter:
    factory: ProcessorFactory

    def __init__(self, factory: ProcessorFactory) -> None:
        self.factory = factory

    def process(self, path: Path) -> None:
        """
        Processes a single Markdown file or a directory of Markdown files.
        """

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
        """
        Recursively scans a directory hierarchy for Markdown files, and processes each, resolving cross-references.
        """

        local_dir = local_dir.resolve(True)
        if root_dir is None:
            root_dir = local_dir
        else:
            root_dir = root_dir.resolve(True)

        self.factory.create(root_dir).process_directory(local_dir)

    def process_page(self, path: Path, root_dir: Optional[Path] = None) -> None:
        """
        Processes a single Markdown file.
        """

        path = path.resolve(True)
        if root_dir is None:
            root_dir = path.parent
        else:
            root_dir = root_dir.resolve(True)

        self.factory.create(root_dir).process_page(path)
