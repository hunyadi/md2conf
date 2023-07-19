import logging
import os.path
import re

from .api import ConfluenceSession

from .converter import ConfluenceDocument, ConfluencePageMetadata, ConfluenceDocumentOptions,extract_value

from typing import Dict


LOGGER = logging.getLogger(__name__)


class Application:
    "The entrypoint for Markdown to Confluence Conversion."

    api: ConfluenceSession
    path: str
    options: ConfluenceDocumentOptions

    def __init__(self, api: ConfluenceSession, path: str, options: ConfluenceDocumentOptions) -> None:
        self.api = api
        self.path = path
        self.options = options

    def run(self) -> None:
        if os.path.isdir(self.path):
            self.synchronize_directory(self.path)
        elif os.path.isfile(self.path):
            self.synchronize_page(self.path)
        else:
            raise ValueError(f"expected: valid file or directory path; got: {self.path}")

    def update_document(self, document: ConfluenceDocument, base_path: str) -> None:
        for image in document.images:
            self.api.upload_attachment(
                document.page_id, os.path.join(base_path, image), image, ""
            )

        self.api.update_page(document.page_id, document.xhtml())



    def synchronize_page(self, page_path: str, page_metadata: Dict[str, ConfluencePageMetadata] = dict()) -> None:
        # page_path = os.path.abspath(self.path)
        base_path = os.path.dirname(page_path)

        LOGGER.info(f"synchronize_page: {page_path}")
        document = ConfluenceDocument(page_path, self.options, page_metadata)

        if document.space_key:
            with self.api.switch_space(document.space_key):
                self.update_document(document, base_path)
        else:
            self.update_document(document, base_path)


    def synchronize_directory(self, dir: str) -> None:
        page_metadata = dict()
        LOGGER.info(f"synchronize_directory: {dir}")

        # Step 1: build index of all page metadata
        for root, directories, files in os.walk(dir):
            for filename in files:
                # Extract the file extension from the path
                file_extension = os.path.splitext(filename)[1]
                abs_path = os.path.join(os.path.abspath(root), filename)
                if file_extension.lower() == ".md":
                    # Open file
                    with open(abs_path, "r") as f:
                        document = f.read()
                        page_id, document = extract_value(
                            r"<!--\s+confluence-page-id:\s*(\d+)\s+-->", document
                        )
                        space_key, document = extract_value(
                            r"<!--\s+confluence-space-key:\s*(\w+)\s+-->", document
                        )

                        if page_id is not None:
                            confluence_page = self.api.get_page(page_id)
                            page_metadata[abs_path] = ConfluencePageMetadata(
                                domain = self.api.domain,
                                page_id = page_id,
                                space_key = space_key or self.api.space_key,
                                title = confluence_page.title or ""
                            )
                            LOGGER.debug(
                                f"indexed {abs_path} with metadata '{page_metadata[abs_path]}'"
                            )

        LOGGER.info(f"indexed {len(page_metadata)} pages")

        # Step 2: Convert each page
        for page_path in page_metadata.keys():
            try:
                self.synchronize_page(page_path, page_metadata)
            except Exception as e:
                # log error and continue converting other pages
                LOGGER.error(f"Failed to synchronize page. {page_path}: {e}")
