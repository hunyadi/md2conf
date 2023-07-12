import logging
import os.path
import re

from .api import ConfluenceSession

from .converter import ConfluenceDocument, ConfluencePageMetadata, ConfluenceDocumentOptions,extract_value

from typing import Dict


LOGGER = logging.getLogger(__name__)


def update_document(
    api: ConfluenceSession, document: ConfluenceDocument, base_path: str
) -> None:
    for image in document.images:
        api.upload_attachment(
            document.page_id, os.path.join(base_path, image), image, ""
        )

    api.update_page(document.page_id, document.xhtml())



def synchronize_pages(api: ConfluenceSession, path: str, options: ConfluenceDocumentOptions) -> None:
    if os.path.isdir(path):
        synchronize_directory(api, path, options)
    elif os.path.isfile(path):
        synchronize_page(api, path, options)
    else:
        raise ValueError(f"expected: valid file or directory path; got: {path}")


def synchronize_page(
    api: ConfluenceSession, path: str, options: ConfluenceDocumentOptions, page_metadata: Dict[str, ConfluencePageMetadata] = dict()
) -> None:
    page_path = os.path.abspath(path)
    base_path = os.path.dirname(page_path)

    LOGGER.info(f"synchronize_page: {page_path}")
    document = ConfluenceDocument(path, options, page_metadata)

    if document.space_key:
        with api.switch_space(document.space_key):
            update_document(api, document, base_path)
    else:
        update_document(api, document, base_path)


def synchronize_directory(api: ConfluenceSession, dir: str, options: ConfluenceDocumentOptions) -> None:
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
                        confluence_page = api.get_page(page_id)
                        page_metadata[abs_path] = ConfluencePageMetadata(
                            page_id = page_id,
                            space_key = space_key,
                            title = confluence_page.title
                        )
                        LOGGER.debug(
                            f"indexed {abs_path} with metadata '{page_metadata[abs_path]}'"
                        )

    LOGGER.info(f"indexed {len(page_metadata)} pages")

    # Step 2: Convert each page
    for page_path in page_metadata.keys():
        try:
            synchronize_page(api, page_path, options, page_metadata)
        except Exception as e:
            # log error and continue converting other pages
            LOGGER.error(f"Failed to synchronize page. {page_path}: {e}")
