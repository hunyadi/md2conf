"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2024, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os.path
from pathlib import Path
from typing import Dict, List, Optional

from .api import ConfluencePage, ConfluenceSession
from .converter import (
    ConfluenceDocument,
    ConfluenceFolder,
    ConfluenceDocumentOptions,
    ConfluencePageMetadata,
    ConfluenceQualifiedID,
    attachment_name,
    extract_frontmatter_title,
    extract_qualified_id,
    read_qualified_id,
)
from .matcher import Matcher, MatcherOptions

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
            raise ValueError(f"expected: valid file or directory path; got: {path}")

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

        # Step 1: build index of all page and folder metadata
        page_metadata: Dict[Path, ConfluencePageMetadata] = {}
        folder_metadata: Dict[Path, ConfluencePageMetadata] = {}
        root_id = (
            ConfluenceQualifiedID(self.options.root_page_id, self.api.space_key)
            if self.options.root_page_id
            else None
        )
        self._index_directory(local_dir, root_id, page_metadata, folder_metadata)
        LOGGER.info("Indexed %d page(s)", len(page_metadata))

        # Step 2: convert each page
        for page_path in page_metadata.keys():
            self._synchronize_page(page_path, root_dir, page_metadata)

        # Step 3: synchronize the "folders" as well
        for folder_path in folder_metadata.keys():
            self._synchronize_folder(folder_path, root_dir, folder_metadata)

    def _synchronize_page(
        self,
        page_path: Path,
        root_dir: Path,
        page_metadata: Dict[Path, ConfluencePageMetadata],
    ) -> None:
        base_path = page_path.parent

        LOGGER.info("Synchronizing page: %s", page_path)
        document = ConfluenceDocument(page_path, self.options, root_dir, page_metadata)
        if not document.title:
            document.title = page_path.stem

        if document.id.space_key:
            with self.api.switch_space(document.id.space_key):
                self._update_document(document, base_path)
        else:
            self._update_document(document, base_path)

    def _synchronize_folder(
        self,
        folder_path: Path,
        root_dir: Path,
        folder_metadata: Dict[Path, ConfluencePageMetadata],
    ) -> None:
        LOGGER.info("Synchronizing folder: %s", folder_path)
        folder = ConfluenceFolder(folder_path, self.options, root_dir, folder_metadata)

        if folder.id.space_key:
            with self.api.switch_space(folder.id.space_key):
                self._update_folder(folder)
        else:
            self._update_folder(folder)

    def _index_directory(
        self,
        local_dir: Path,
        root_id: Optional[ConfluenceQualifiedID],
        page_metadata: Dict[Path, ConfluencePageMetadata],
        folder_metadata: Dict[Path, ConfluencePageMetadata],
    ) -> None:
        "Indexes Markdown files in a directory recursively."

        LOGGER.info("Indexing directory: %s", local_dir)

        matcher = Matcher(MatcherOptions(source=".mdignore", extension="md"), local_dir)

        files: List[Path] = []
        directories: List[Path] = []
        for entry in os.scandir(local_dir):
            if matcher.is_excluded(entry.name, entry.is_dir()):
                continue

            if entry.is_file():
                files.append(Path(local_dir) / entry.name)
            elif entry.is_dir():
                directories.append(Path(local_dir) / entry.name)

        parent_id = root_id

        for doc in files:
            metadata = self._get_or_create_page(doc, parent_id)
            LOGGER.debug("Indexed %s with metadata: %s", doc, metadata)
            page_metadata[doc] = metadata

        for directory in directories:
            # Make en empty page that acts like a folder
            metadata = self._get_or_create_folder(directory, parent_id)
            new_id = ConfluenceQualifiedID(metadata.page_id, metadata.space_key)
            folder_metadata[directory] = metadata

            self._index_directory(directory, new_id, page_metadata, folder_metadata)

    def _get_or_create_page(
        self,
        absolute_path: Path,
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
        frontmatter_title, _ = extract_frontmatter_title(document)

        if qualified_id is not None:
            confluence_page = self.api.get_page(
                qualified_id.page_id, space_key=qualified_id.space_key
            )
        else:
            if parent_id is None:
                raise ValueError(
                    f"expected: parent page ID for Markdown file with no linked Confluence page: {absolute_path}"
                )

            # assign title from frontmatter if present
            confluence_page = self._create_page(
                absolute_path, document, title or frontmatter_title, parent_id
            )

        return ConfluencePageMetadata(
            domain=self.api.domain,
            base_path=self.api.base_path,
            page_id=confluence_page.id,
            space_key=confluence_page.space_key or self.api.space_key,
            title=confluence_page.title or "",
        )

    def _get_or_create_folder(
        self,
        absolute_path: Path,
        parent_id: Optional[ConfluenceQualifiedID],
        *,
        title: Optional[str] = None,
    ) -> ConfluencePageMetadata:
        """Creates a new Confluence page if no page is linked in the .md2conf_folder
        file (or if the file does not exist).

        Note:
            We are not using actual Confluence folders for this because the API is
            currently too limited (unable to PUT, so cannot rename).
        """
        # parse file
        data_file = os.path.join(absolute_path, ".md2conf_folder")

        if os.path.exists(data_file):
            with open(data_file, "r", encoding="utf-8") as f:
                text = f.read()
            qualified_id, _ = extract_qualified_id(text)
        else:
            qualified_id = None

        if qualified_id is not None:
            LOGGER.debug("Found qualified ID in %s", data_file)
            confluence_page = self.api.get_page(
                qualified_id.page_id, space_key=qualified_id.space_key
            )
        else:
            if parent_id is None:
                raise ValueError(
                    f"expected: parent page ID for folder with no linked Confluence page: {absolute_path}"
                )

            LOGGER.debug("Creating folder 'page' %s", title)
            confluence_page = self._create_folder(absolute_path, title, parent_id)

        return ConfluencePageMetadata(
            domain=self.api.domain,
            base_path=self.api.base_path,
            page_id=confluence_page.id,
            space_key=confluence_page.space_key or self.api.space_key,
            title=confluence_page.title or "",
        )

    def _create_page(
        self,
        absolute_path: Path,
        document: str,
        title: Optional[str],
        parent_id: ConfluenceQualifiedID,
    ) -> ConfluencePage:
        "Creates a new Confluence page when Markdown file doesn't have an embedded page ID yet."

        # use file name without extension if no title is supplied
        if title is None:
            title = absolute_path.stem

        confluence_page = self.api.get_or_create_page(
            title, parent_id.page_id, space_key=parent_id.space_key
        )
        self._update_markdown(
            absolute_path,
            document,
            confluence_page.id,
            confluence_page.space_key,
        )
        return confluence_page

    def _create_folder(
        self,
        absolute_path: Path,
        title: Optional[str],
        parent_id: ConfluenceQualifiedID,
    ) -> ConfluencePage:
        """Creates a new Confluence page when .md2conf_folder file doesn't have an
        embedded page ID yet.

        Note:
            We are not using actual Confluence folders for this because the API is
            currently too limited (unable to PUT, so cannot rename).
        """
        # use file name without extension if no title is supplied
        if title is None:
            title = absolute_path.stem

        confluence_folder = self.api.get_or_create_page(
            title, parent_id.page_id, space_key=parent_id.space_key
        )

        self._update_folder_data(
            absolute_path,
            confluence_folder.id,
            confluence_folder.space_key,
        )

        return confluence_folder

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

    def _update_folder(self, folder: ConfluenceFolder) -> None:
        self.api.update_page(folder.id.page_id, folder.xhtml(), title=folder.title)

    def _update_markdown(
        self,
        path: Path,
        document: str,
        page_id: str,
        space_key: Optional[str],
    ) -> None:
        "Writes the Confluence page ID and space key at the beginning of the Markdown file."

        content: List[str] = []

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

    def _update_folder_data(
        self,
        path: Path,
        folder_id: str,
        space_key: Optional[str],
    ) -> None:
        """Adds/updates the .md2conf_folder file in the directory. This file importantly
        stores the ID of the 'folder' page in Confluence, so that if we rename a folder
        on the file system, it can be reflected in Confluence.
        """
        data_file = os.path.join(path, ".md2conf_folder")

        with open(data_file, "w", encoding="utf-8") as file:
            file.write(f"<!-- confluence-page-id: {folder_id} -->\n")

            if space_key:
                file.write(f"<!-- confluence-space-key: {space_key} -->")
