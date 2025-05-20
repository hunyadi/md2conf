"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

from .api import ConfluencePage, ConfluenceSession
from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageID,
    attachment_name,
    extract_frontmatter_title,
    extract_qualified_id,
)
from .metadata import ConfluencePageMetadata
from .processor import Converter, Processor, ProcessorFactory
from .properties import PageError

LOGGER = logging.getLogger(__name__)


class SynchronizingProcessor(Processor):
    """
    Synchronizes a single Markdown page or a directory of Markdown pages with Confluence.
    """

    api: ConfluenceSession

    def __init__(
        self, api: ConfluenceSession, options: ConfluenceDocumentOptions, root_dir: Path
    ) -> None:
        """
        Initializes a new processor instance.

        :param api: Holds information about an open session to a Confluence server.
        :param options: Options that control the generated page content.
        :param root_dir: File system directory that acts as topmost root node.
        """

        super().__init__(options, api.site, root_dir)
        self.api = api

    def _get_or_create_page(
        self,
        absolute_path: Path,
        parent_id: Optional[ConfluencePageID],
        *,
        title: Optional[str] = None,
    ) -> ConfluencePageMetadata:
        """
        Creates a new Confluence page if no page is linked in the Markdown document.
        """

        # parse file
        with open(absolute_path, "r", encoding="utf-8") as f:
            text = f.read()

        qualified_id, text = extract_qualified_id(text)

        overwrite = False
        if qualified_id is None:
            # create new Confluence page
            if parent_id is None:
                raise PageError(
                    f"expected: parent page ID for Markdown file with no linked Confluence page: {absolute_path}"
                )

            # assign title from front-matter if present
            if title is None:
                title, _ = extract_frontmatter_title(text)

            # use file name (without extension) and path hash if no title is supplied
            if title is None:
                overwrite = True
                relative_path = absolute_path.relative_to(self.root_dir)
                hash = hashlib.md5(relative_path.as_posix().encode("utf-8"))
                digest = "".join(f"{c:x}" for c in hash.digest())
                title = f"{absolute_path.stem} [{digest}]"

            confluence_page = self._create_page(absolute_path, text, title, parent_id)
        else:
            # look up existing Confluence page
            confluence_page = self.api.get_page(qualified_id.page_id)

        space_key = (
            self.api.space_id_to_key(confluence_page.space_id)
            if confluence_page.space_id
            else self.site.space_key
        )

        return ConfluencePageMetadata(
            page_id=confluence_page.id,
            space_key=space_key,
            title=confluence_page.title,
            overwrite=overwrite,
        )

    def _create_page(
        self,
        absolute_path: Path,
        document: str,
        title: str,
        parent_id: ConfluencePageID,
    ) -> ConfluencePage:
        """
        Creates a new Confluence page when Markdown file doesn't have an embedded page ID yet.
        """

        confluence_page = self.api.get_or_create_page(title, parent_id.page_id)
        self._update_markdown(
            absolute_path,
            document,
            confluence_page.id,
            self.api.space_id_to_key(confluence_page.space_id),
        )
        return confluence_page

    def _save_document(self, document: ConfluenceDocument, path: Path) -> None:
        """
        Saves a new version of a Confluence document.

        Invokes Confluence REST API to persist the new version.
        """

        base_path = path.parent
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

        # leave title as it is for existing pages, update title for pages with randomly assigned title
        title = document.title if self.page_metadata[path].overwrite else None

        LOGGER.debug("Generated Confluence Storage Format document:\n%s", content)
        self.api.update_page(document.id.page_id, content, title=title)

    def _update_markdown(
        self,
        path: Path,
        document: str,
        page_id: str,
        space_key: Optional[str],
    ) -> None:
        """
        Writes the Confluence page ID and space key at the beginning of the Markdown file.
        """

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


class SynchronizingProcessorFactory(ProcessorFactory):
    api: ConfluenceSession

    def __init__(
        self, api: ConfluenceSession, options: ConfluenceDocumentOptions
    ) -> None:
        super().__init__(options, api.site)
        self.api = api

    def create(self, root_dir: Path) -> Processor:
        return SynchronizingProcessor(self.api, self.options, root_dir)


class Application(Converter):
    """
    The entry point for Markdown to Confluence conversion.
    """

    def __init__(
        self, api: ConfluenceSession, options: ConfluenceDocumentOptions
    ) -> None:
        super().__init__(SynchronizingProcessorFactory(api, options))
