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

from .api import ConfluencePage, ConfluenceSession
from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageMetadata,
    ConfluenceQualifiedID,
    ConfluenceSiteMetadata,
    attachment_name,
    extract_frontmatter_title,
    extract_qualified_id,
    read_qualified_id,
)
from .matcher import Matcher, MatcherOptions
from .properties import ArgumentError, PageError

LOGGER = logging.getLogger(__name__)


class Application:
    "The entry point for Markdown to Confluence conversion."

    api: ConfluenceSession
    options: ConfluenceDocumentOptions

    def __init__(
        self, api: ConfluenceSession, options: ConfluenceDocumentOptions
    ) -> None:
        self.api = api
        self.options = options

    def synchronize(self, path: Path) -> None:
        "Synchronizes a single Markdown page or a directory of Markdown pages."

        path = path.resolve(True)
        if path.is_dir():
            self.synchronize_directory(path)
        elif path.is_file():
            self.synchronize_page(path)
        else:
            raise ArgumentError(f"expected: valid file or directory path; got: {path}")

    def synchronize_page(
        self, page_path: Path, root_dir: Optional[Path] = None
    ) -> None:
        "Synchronizes a single Markdown page with Confluence."

        page_path = page_path.resolve(True)
        if root_dir is None:
            root_dir = page_path.parent
        else:
            root_dir = root_dir.resolve(True)

        self._synchronize_page(page_path, root_dir, {})

    def synchronize_directory(
        self, local_dir: Path, root_dir: Optional[Path] = None
    ) -> None:
        "Synchronizes a directory of Markdown pages with Confluence."

        local_dir = local_dir.resolve(True)
        if root_dir is None:
            root_dir = local_dir
        else:
            root_dir = root_dir.resolve(True)

        LOGGER.info("Synchronizing directory: %s", local_dir)

        # Step 1: build index of all page metadata
        page_metadata: dict[Path, ConfluencePageMetadata] = {}
        root_id = (
            ConfluenceQualifiedID(self.options.root_page_id, self.api.space_key)
            if self.options.root_page_id
            else None
        )
        self._index_directory(local_dir, root_dir, root_id, page_metadata)
        LOGGER.info("Indexed %d page(s)", len(page_metadata))

        # Step 2: convert each page
        for page_path in page_metadata.keys():
            self._synchronize_page(page_path, root_dir, page_metadata)

    def _synchronize_page(
        self,
        page_path: Path,
        root_dir: Path,
        page_metadata: dict[Path, ConfluencePageMetadata],
    ) -> None:
        base_path = page_path.parent

        LOGGER.info("Synchronizing page: %s", page_path)
        site_metadata = ConfluenceSiteMetadata(
            domain=self.api.domain,
            base_path=self.api.base_path,
            space_key=self.api.space_key,
        )

        document = ConfluenceDocument.create(
            page_path, self.options, root_dir, site_metadata, page_metadata
        )
        self._update_document(document, base_path)

    def _index_directory(
        self,
        local_dir: Path,
        root_dir: Path,
        root_id: Optional[ConfluenceQualifiedID],
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

        # make page act as parent node in Confluence
        parent_doc: Optional[Path] = None
        if (Path(local_dir) / "index.md") in files:
            parent_doc = Path(local_dir) / "index.md"
        elif (Path(local_dir) / "README.md") in files:
            parent_doc = Path(local_dir) / "README.md"
        elif (Path(local_dir) / f"{local_dir.name}.md") in files:
            parent_doc = Path(local_dir) / f"{local_dir.name}.md"

        if parent_doc is None and self.options.keep_hierarchy:
            parent_doc = Path(local_dir) / "index.md"

            # create a blank page in Confluence for the directory entry
            with open(parent_doc, "w"):
                pass

        if parent_doc is not None:
            files.remove(parent_doc)

            metadata = self._get_or_create_page(parent_doc, root_dir, root_id)
            LOGGER.debug("Indexed parent %s with metadata: %s", parent_doc, metadata)
            page_metadata[parent_doc] = metadata

            parent_id = read_qualified_id(parent_doc) or root_id
        else:
            parent_id = root_id

        for doc in files:
            metadata = self._get_or_create_page(doc, root_dir, parent_id)
            LOGGER.debug("Indexed %s with metadata: %s", doc, metadata)
            page_metadata[doc] = metadata

        for directory in directories:
            self._index_directory(directory, root_dir, parent_id, page_metadata)

    def _get_or_create_page(
        self,
        absolute_path: Path,
        root_dir: Path,
        parent_id: Optional[ConfluenceQualifiedID],
        *,
        title: Optional[str] = None,
    ) -> ConfluencePageMetadata:
        """
        Creates a new Confluence page if no page is linked in the Markdown document.
        """

        # parse file
        with open(absolute_path, "r", encoding="utf-8") as f:
            document = f.read()

        qualified_id, document = extract_qualified_id(document)

        if qualified_id is not None:
            confluence_page = self.api.get_page(qualified_id.page_id)
        else:
            if parent_id is None:
                raise PageError(
                    f"expected: parent page ID for Markdown file with no linked Confluence page: {absolute_path}"
                )

            # assign title from front-matter if present
            if title is None:
                title, _ = extract_frontmatter_title(document)

            # use file name (without extension) and path hash if no title is supplied
            if title is None:
                relative_path = absolute_path.relative_to(root_dir)
                hash = hashlib.md5(relative_path.as_posix().encode("utf-8"))
                digest = "".join(f"{c:x}" for c in hash.digest())
                title = f"{absolute_path.stem} [{digest}]"

            confluence_page = self._create_page(
                absolute_path, document, title, parent_id
            )

        space_key = (
            self.api.space_id_to_key(confluence_page.space_id)
            if confluence_page.space_id
            else self.api.space_key
        )

        return ConfluencePageMetadata(
            page_id=confluence_page.id,
            space_key=space_key,
            title=confluence_page.title or "",
        )

    def _create_page(
        self,
        absolute_path: Path,
        document: str,
        title: str,
        parent_id: ConfluenceQualifiedID,
    ) -> ConfluencePage:
        "Creates a new Confluence page when Markdown file doesn't have an embedded page ID yet."

        confluence_page = self.api.get_or_create_page(
            title, parent_id.page_id, space_key=parent_id.space_key
        )
        self._update_markdown(
            absolute_path,
            document,
            confluence_page.id,
            self.api.space_id_to_key(confluence_page.space_id),
        )
        return confluence_page

    def _update_document(self, document: ConfluenceDocument, base_path: Path) -> None:
        "Saves a new version of a Confluence document."

        for image in document.images:
            self.api.upload_attachment(
                document.id.page_id,
                attachment_name(image),
                attachment_path=base_path / image,
            )

        for name, data in document.embedded_images.items():
            self.api.upload_attachment(
                document.id.page_id,
                name,
                raw_data=data,
            )

        content = document.xhtml()
        LOGGER.debug("Generated Confluence Storage Format document:\n%s", content)
        self.api.update_page(document.id.page_id, content, title=document.title)

    def _update_markdown(
        self,
        path: Path,
        document: str,
        page_id: str,
        space_key: Optional[str],
    ) -> None:
        "Writes the Confluence page ID and space key at the beginning of the Markdown file."

        content: list[str] = []

        # check if the file has frontmatter
        index = 0
        if document.startswith("---\n"):
            index = document.find("\n---\n", 4) + 4

            # insert the Confluence keys after the frontmatter
            content.append(document[:index])

        content.append(f"<!-- confluence-page-id: {page_id} -->")
        if space_key:
            content.append(f"<!-- confluence-space-key: {space_key} -->")

        content.append(document[index:])

        with open(path, "w", encoding="utf-8") as file:
            file.write("\n".join(content))
