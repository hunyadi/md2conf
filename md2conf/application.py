import logging
import os.path
from typing import Dict

from .api import ConfluenceSession
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

        self._synchronize_page(page_path, dict())

    def synchronize_directory(self, dir: str) -> None:
        "Synchronizes a directory of Markdown pages with Confluence."

        page_metadata: Dict[str, ConfluencePageMetadata] = dict()
        LOGGER.info(f"Synchronizing directory: {dir}")

        # Step 1: build index of all page metadata
        for root, directories, files in os.walk(dir):
            for file_name in files:
                # check the file extension
                _, file_extension = os.path.splitext(file_name)
                if file_extension.lower() != ".md":
                    continue

                # parse file
                absolute_path = os.path.join(os.path.abspath(root), file_name)
                with open(absolute_path, "r") as f:
                    document = f.read()

                id, document = extract_page_id(document)
                confluence_page = self.api.get_page(id.page_id)
                metadata = ConfluencePageMetadata(
                    domain=self.api.domain,
                    base_path=self.api.base_path,
                    page_id=id.page_id,
                    space_key=id.space_key or self.api.space_key,
                    title=confluence_page.title or "",
                )
                LOGGER.debug(f"indexed {absolute_path} with metadata: {metadata}")
                page_metadata[absolute_path] = metadata

        LOGGER.info(f"indexed {len(page_metadata)} pages")

        # Step 2: Convert each page
        for page_path in page_metadata.keys():
            self._synchronize_page(page_path, page_metadata)

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
