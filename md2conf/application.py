import logging
import os.path
from typing import Dict

from .api import ConfluenceSession, ConfluencePage
from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageMetadata,
    extract_page_id,
)

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

    def synchronize(self, path: str) -> None:
        "Synchronizes a single Markdown page or a directory of Markdown pages."

        if os.path.isdir(path):
            self.synchronize_directory(path)
        elif os.path.isfile(path):
            self.synchronize_page(path)
        else:
            raise ValueError(f"expected: valid file or directory path; got: {path}")

    def synchronize_page(self, page_path: str) -> None:
        "Synchronizes a single Markdown page with Confluence."

        file_name = os.path.basename(page_path)
        file_name_without_extension = os.path.splitext(file_name)[0]

        metadata = self._get_or_create_page_metadata(os.path.abspath(page_path), file_name_without_extension)
        self._synchronize_page(page_path, {page_path: metadata})

    def synchronize_directory(self, dir: str) -> None:
        "Synchronizes a directory of Markdown pages with Confluence."

        page_metadata: Dict[str, ConfluencePageMetadata] = dict()
        LOGGER.info(f"Synchronizing directory: {dir}")

        # Step 1: build index of all page metadata
        for root, directories, files in os.walk(dir):
            for file_name in files:
                # check the file extension
                file_name_without_extension, file_extension = os.path.splitext(file_name)
                if file_extension.lower() != ".md":
                    continue

                absolute_path = os.path.join(os.path.abspath(root), file_name)
                metadata = self._get_or_create_page_metadata(absolute_path, file_name_without_extension)

                LOGGER.debug(f"indexed {absolute_path} with metadata: {metadata}")
                page_metadata[absolute_path] = metadata

        LOGGER.info(f"indexed {len(page_metadata)} pages")

        # Step 2: Convert each page
        for page_path in page_metadata.keys():
            self._synchronize_page(page_path, page_metadata)

    def _get_or_create_page_metadata(self, absolute_path: str, title: str) -> ConfluencePageMetadata:
        # parse file
        with open(absolute_path, "r") as f:
            document = f.read()

        id, document = extract_page_id(document)

        should_update_file = False
        if id.page_id is None:
            confluence_page = self._get_or_create_page(title)
            should_update_file = True

            if confluence_page is None:
                raise RuntimeError(
                    "Markdown document has no Confluence page ID and no root page ID was provided."
                )
        else:
            confluence_page = self.api.get_page(id.page_id)

        if should_update_file:
            self._write_page_id(absolute_path, document, confluence_page.id)

        return ConfluencePageMetadata(
            domain=self.api.domain,
            base_path=self.api.base_path,
            page_id=confluence_page.id,
            space_key=id.space_key or self.api.space_key,
            title=confluence_page.title or "",
        )

    def _get_or_create_page(self, title) -> ConfluencePage:
        page_found, page_id = self.api.page_exists(title)

        confluence_page = None
        if page_found:
            LOGGER.debug(f"get page {page_id}")
            confluence_page = self.api.get_page(page_id)
        elif self.options.root_page_id is not None:
            LOGGER.debug(f"create page with title '{title}'")
            confluence_page = self.api.create_page(self.options.root_page_id, title, "")

        return confluence_page

    def _synchronize_page(
        self,
        page_path: str,
        page_metadata: Dict[str, ConfluencePageMetadata],
    ) -> None:
        base_path = os.path.dirname(page_path)

        LOGGER.info(f"Synchronizing page: {page_path}")
        document = ConfluenceDocument(page_path, self.options, page_metadata)

        if document.id.space_key:
            with self.api.switch_space(document.id.space_key):
                self._update_document(document, base_path)
        else:
            self._update_document(document, base_path)

    def _update_document(self, document: ConfluenceDocument, base_path: str) -> None:
        for image in document.images:
            self.api.upload_attachment(
                document.id.page_id, os.path.join(base_path, image), image, ""
            )

        content = document.xhtml()
        LOGGER.debug(f"generated Confluence Storage Format document:\n{content}")
        self.api.update_page(document.id.page_id, content)

    def _write_page_id(self, path, document, page_id) -> None:
        string = f'<!-- confluence-page-id: {page_id} -->\n'

        with open(path, 'w') as file:
            file.write(string + document)
