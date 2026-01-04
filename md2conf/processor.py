"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os
from abc import abstractmethod
from pathlib import Path
from typing import Iterable

from .collection import ConfluencePageCollection
from .converter import ConfluenceDocument
from .environment import ArgumentError
from .matcher import DirectoryEntry, FileEntry, Matcher, MatcherOptions
from .metadata import ConfluenceSiteMetadata
from .options import ConfluencePageID, DocumentOptions
from .scanner import Scanner

LOGGER = logging.getLogger(__name__)


class DocumentNode:
    "Represents a Markdown document in a hierarchy."

    absolute_path: Path
    page_id: str | None
    space_key: str | None
    title: str | None
    synchronized: bool

    _children: list["DocumentNode"]

    def __init__(
        self,
        absolute_path: Path,
        page_id: str | None,
        space_key: str | None,
        title: str | None,
        synchronized: bool,
    ):
        self.absolute_path = absolute_path
        self.page_id = page_id
        self.space_key = space_key
        self.title = title
        self.synchronized = synchronized
        self._children = []

    def count(self) -> int:
        "Number of descendants in the sub-tree spanned by this node (excluding the top-level node)."

        c = len(self._children)
        for child in self._children:
            c += child.count()
        return c

    def add_child(self, child: "DocumentNode") -> None:
        "Adds a new node to the list of direct children."

        self._children.append(child)

    def children(self) -> Iterable["DocumentNode"]:
        "Direct children of this node."

        for child in self._children:
            yield child

    def descendants(self) -> Iterable["DocumentNode"]:
        """
        Descendants of this node, part of its sub-tree.

        Traversal follows depth-first search.
        """

        for child in self._children:
            yield child
            yield from child.descendants()

    def all(self) -> Iterable["DocumentNode"]:
        """
        Descendants of this node, part of the sub-tree including the top-level node.

        Traversal follows depth-first search.
        """

        yield self
        for child in self._children:
            yield from child.all()


class Processor:
    """
    Processes a single Markdown page or a directory of Markdown pages.
    """

    options: DocumentOptions
    site: ConfluenceSiteMetadata
    root_dir: Path

    page_metadata: ConfluencePageCollection

    def __init__(
        self,
        options: DocumentOptions,
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

        # build index of all Markdown files in directory hierarchy
        root = self._index_directory(local_dir, None)
        LOGGER.info("Indexed %d document(s)", root.count())

        self._process_items(root)

    def process_page(self, path: Path) -> None:
        """
        Processes a single Markdown file.
        """

        LOGGER.info("Processing page: %s", path)
        root = self._index_file(path)

        self._process_items(root)

    def _process_items(self, root: DocumentNode) -> None:
        """
        Processes a sub-tree rooted at an ancestor node.
        """

        # synchronize directory tree structure with page hierarchy in space (find matching pages in Confluence)
        self._synchronize_tree(root, self.options.root_page_id)

        # synchronize files in directory hierarchy with pages in space
        for path, metadata in self.page_metadata.items():
            if metadata.synchronized:
                self._synchronize_page(path, ConfluencePageID(metadata.page_id))

    def _synchronize_page(self, path: Path, page_id: ConfluencePageID) -> None:
        """
        Synchronizes a single Markdown document with its corresponding Confluence page.
        """

        page_id, document = ConfluenceDocument.create(path, self.options, self.root_dir, self.site, self.page_metadata)
        self._update_page(page_id, document, path)

    @abstractmethod
    def _synchronize_tree(self, tree: DocumentNode, root_id: ConfluencePageID | None) -> None:
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

    def _index_directory(self, local_dir: Path, parent: DocumentNode | None) -> DocumentNode:
        """
        Indexes Markdown files in a directory hierarchy recursively.
        """

        LOGGER.info("Indexing directory: %s", local_dir)

        matcher = Matcher(MatcherOptions(source=".mdignore", extension="md"), local_dir)

        files: list[FileEntry] = []
        directories: list[DirectoryEntry] = []
        for entry in os.scandir(local_dir):
            if matcher.is_excluded(entry):
                continue

            if entry.is_file():
                files.append(FileEntry(entry.name))
            elif entry.is_dir():
                directories.append(DirectoryEntry(entry.name))

        files.sort()
        directories.sort()

        # make page act as parent node
        parent_doc: Path | None = None
        if FileEntry("index.md") in files:
            parent_doc = local_dir / "index.md"
        elif FileEntry("README.md") in files:
            parent_doc = local_dir / "README.md"
        elif FileEntry(f"{local_dir.name}.md") in files:
            parent_doc = local_dir / f"{local_dir.name}.md"

        if parent_doc is None and self.options.keep_hierarchy:
            parent_doc = local_dir / "index.md"

            # create a blank page for directory entry
            with open(parent_doc, "w") as f:
                print("[[_LISTING_]]", file=f)

        if parent_doc is not None:
            parent_entry = FileEntry(parent_doc.name)
            if parent_entry in files:
                files.remove(parent_entry)

            # promote Markdown document in directory as parent page in Confluence
            node = self._index_file(parent_doc)
            if parent is not None:
                parent.add_child(node)
            parent = node
        elif parent is None:
            raise ArgumentError(f"root page requires corresponding top-level Markdown document in {local_dir}")

        for file in files:
            node = self._index_file(local_dir / Path(file.name))
            parent.add_child(node)

        for directory in directories:
            self._index_directory(local_dir / Path(directory.name), parent)

        return parent

    def _index_file(self, path: Path) -> DocumentNode:
        """
        Indexes a single Markdown file.
        """

        LOGGER.info("Indexing file: %s", path)

        # extract information from a Markdown document found in a local directory.
        document = Scanner().read(path)

        props = document.properties
        return DocumentNode(
            absolute_path=path,
            page_id=props.page_id,
            space_key=props.space_key,
            title=props.title,
            synchronized=props.synchronized if props.synchronized is not None else True,
        )

    def _generate_hash(self, absolute_path: Path) -> str:
        """
        Computes a digest to be used as a unique string.
        """

        relative_path = absolute_path.relative_to(self.root_dir)
        hash = hashlib.md5(relative_path.as_posix().encode("utf-8"))
        return "".join(f"{c:x}" for c in hash.digest())


class ProcessorFactory:
    options: DocumentOptions
    site: ConfluenceSiteMetadata

    def __init__(self, options: DocumentOptions, site: ConfluenceSiteMetadata) -> None:
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

    def process_directory(self, local_dir: Path, root_dir: Path | None = None) -> None:
        """
        Recursively scans a directory hierarchy for Markdown files, and processes each, resolving cross-references.
        """

        local_dir = local_dir.resolve(True)
        if root_dir is None:
            root_dir = local_dir
        else:
            root_dir = root_dir.resolve(True)

        self.factory.create(root_dir).process_directory(local_dir)

    def process_page(self, path: Path, root_dir: Path | None = None) -> None:
        """
        Processes a single Markdown file.
        """

        path = path.resolve(True)
        if root_dir is None:
            root_dir = path.parent
        else:
            root_dir = root_dir.resolve(True)

        self.factory.create(root_dir).process_page(path)
