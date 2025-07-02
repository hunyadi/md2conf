"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os
from abc import abstractmethod
from pathlib import Path
from typing import Iterable, Optional

from .collection import ConfluencePageCollection
from .converter import ConfluenceDocument, ConfluenceDocumentOptions, ConfluencePageID
from .matcher import Matcher, MatcherOptions
from .metadata import ConfluenceSiteMetadata
from .properties import ArgumentError
from .scanner import Scanner

LOGGER = logging.getLogger(__name__)


class DocumentNode:
    absolute_path: Path
    page_id: Optional[str]
    space_key: Optional[str]
    title: Optional[str]

    _children: list["DocumentNode"]

    def __init__(
        self,
        absolute_path: Path,
        page_id: Optional[str],
        space_key: Optional[str] = None,
        title: Optional[str] = None,
    ):
        self.absolute_path = absolute_path
        self.page_id = page_id
        self.space_key = space_key
        self.title = title
        self._children = []

    def count(self) -> int:
        c = len(self._children)
        for child in self._children:
            c += child.count()
        return c

    def add_child(self, child: "DocumentNode") -> None:
        self._children.append(child)

    def children(self) -> Iterable["DocumentNode"]:
        for child in self._children:
            yield child

    def descendants(self) -> Iterable["DocumentNode"]:
        for child in self._children:
            yield child
            yield from child.descendants()

    def all(self) -> Iterable["DocumentNode"]:
        yield self
        for child in self._children:
            yield from child.all()


class Processor:
    """
    Processes a single Markdown page or a directory of Markdown pages.
    """

    options: ConfluenceDocumentOptions
    site: ConfluenceSiteMetadata
    root_dir: Path

    page_metadata: ConfluencePageCollection

    def __init__(
        self,
        options: ConfluenceDocumentOptions,
        site: ConfluenceSiteMetadata,
        root_dir: Path,
    ) -> None:
        self.options = options
        self.site = site
        self.root_dir = root_dir
        self.page_metadata = ConfluencePageCollection()

    def process_directory(self, local_dir: Path) -> None:
        """
        Recursively scans a directory hierarchy for Markdown files, and processes each, resolving cross-references.
        """

        local_dir = local_dir.resolve(True)
        LOGGER.info("Processing directory: %s", local_dir)

        # Step 1: build index of all Markdown files in directory hierarchy
        root = self._index_directory(local_dir, None)
        LOGGER.info("Indexed %d document(s)", root.count())

        # Step 2: synchronize directory tree structure with page hierarchy in space
        self._synchronize_tree(root, self.options.root_page_id)

        # Step 3: synchronize files in directory hierarchy with pages in space
        for path, metadata in self.page_metadata.items():
            self._synchronize_page(path, ConfluencePageID(metadata.page_id))

    def process_page(self, path: Path) -> None:
        """
        Processes a single Markdown file.
        """

        LOGGER.info("Processing page: %s", path)

        # Step 1: parse Markdown file
        root = self._index_file(path)

        # Step 2: find matching page in Confluence
        self._synchronize_tree(root, self.options.root_page_id)

        # Step 3: synchronize document with page in space
        for path, metadata in self.page_metadata.items():
            self._synchronize_page(path, ConfluencePageID(metadata.page_id))

    def _synchronize_page(self, path: Path, page_id: ConfluencePageID) -> None:
        """
        Synchronizes a single Markdown document with its corresponding Confluence page.
        """

        page_id, document = ConfluenceDocument.create(path, self.options, self.root_dir, self.site, self.page_metadata)
        self._update_page(page_id, document, path)

    @abstractmethod
    def _synchronize_tree(self, node: DocumentNode, page_id: Optional[ConfluencePageID]) -> None:
        """
        Creates the cross-reference index and synchronizes the directory tree structure with the Confluence page hierarchy.

        Creates new Confluence pages as necessary, e.g. if no page is linked in the Markdown document, or no page is found with lookup by page title.

        May update the original Markdown document to add tags to associate the document with its corresponding Confluence page.
        """
        ...

    @abstractmethod
    def _update_page(self, page_id: ConfluencePageID, document: ConfluenceDocument, path: Path) -> None:
        """
        Saves the document as Confluence Storage Format XHTML.
        """
        ...

    def _index_directory(self, local_dir: Path, parent: Optional[DocumentNode]) -> DocumentNode:
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
                files.append(local_dir / entry.name)
            elif entry.is_dir():
                directories.append(local_dir / entry.name)

        # make page act as parent node
        parent_doc: Optional[Path] = None
        if (local_dir / "index.md") in files:
            parent_doc = local_dir / "index.md"
        elif (local_dir / "README.md") in files:
            parent_doc = local_dir / "README.md"
        elif (local_dir / f"{local_dir.name}.md") in files:
            parent_doc = local_dir / f"{local_dir.name}.md"

        if parent_doc is None and self.options.keep_hierarchy:
            parent_doc = local_dir / "index.md"

            # create a blank page for directory entry
            with open(parent_doc, "w"):
                pass

        if parent_doc is not None:
            if parent_doc in files:
                files.remove(parent_doc)

            # promote Markdown document in directory as parent page in Confluence
            node = self._index_file(parent_doc)
            if parent is not None:
                parent.add_child(node)
            parent = node
        elif parent is None:
            raise ArgumentError(f"root page requires corresponding top-level Markdown document in {local_dir}")

        for file in files:
            node = self._index_file(file)
            parent.add_child(node)

        for directory in directories:
            self._index_directory(directory, parent)

        return parent

    def _index_file(self, path: Path) -> DocumentNode:
        """
        Indexes a single Markdown file.
        """

        LOGGER.info("Indexing file: %s", path)

        # extract information from a Markdown document found in a local directory.
        document = Scanner().read(path)

        return DocumentNode(
            absolute_path=path,
            page_id=document.page_id,
            space_key=document.space_key,
            title=document.title,
        )

    def _generate_hash(self, absolute_path: Path) -> str:
        """
        Computes a digest to be used as a unique string.
        """

        relative_path = absolute_path.relative_to(self.root_dir)
        hash = hashlib.md5(relative_path.as_posix().encode("utf-8"))
        return "".join(f"{c:x}" for c in hash.digest())


class ProcessorFactory:
    options: ConfluenceDocumentOptions
    site: ConfluenceSiteMetadata

    def __init__(self, options: ConfluenceDocumentOptions, site: ConfluenceSiteMetadata) -> None:
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

    def process_directory(self, local_dir: Path, root_dir: Optional[Path] = None) -> None:
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
