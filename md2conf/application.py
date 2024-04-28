import logging
import os.path
from typing import Dict, Optional

from .api import ConfluenceSession
from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageMetadata,
    extract_qualified_id,
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

        self._synchronize_page(page_path, {})

    def synchronize_directory(self, dir: str) -> None:
        "Synchronizes a directory of Markdown pages with Confluence."

        page_metadata: Dict[str, ConfluencePageMetadata] = {}
        LOGGER.info(f"Synchronizing directory: {dir}")

        # Step 1: build index of all page metadata
        for root, directories, files in os.walk(dir):
            for file_name in files:
                # check the file extension
                _, file_extension = os.path.splitext(file_name)
                if file_extension.lower() != ".md":
                    continue

                absolute_path = os.path.join(os.path.abspath(root), file_name)
                relative_path = os.path.relpath(absolute_path, dir)
                metadata = self._get_or_create_page(absolute_path, relative_path)

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

    def _get_or_create_page(
        self,
        absolute_path: str,
        relative_path: str,
        title: Optional[str] = None
    ) -> ConfluencePageMetadata:
        """
        Creates a new Confluence page if no page is linked in the Markdown document.
        """

        # parse file
        with open(absolute_path, "r") as f:
            document = f.read()
        for line in document.splitlines():
            if line.startswith("# "):
                title = line.lstrip("# ")
                break
        else:
            title = None
        LOGGER.info(f"Title: '{title}'")

        qualified_id, document = extract_qualified_id(document)
        if qualified_id is not None:
            confluence_page = self.api.get_page(
                qualified_id.page_id, space_key=qualified_id.space_key
            )
        else:
            if self.options.root_page_id is None:
                raise ValueError(
                    "expected: Confluence page ID to act as parent for Markdown files with no linked Confluence page"
                )

            # Split the relative_path into individual directories
            directories = relative_path.split(os.path.sep)
            # Start from the root page
            current_page_id = self.options.root_page_id
            
            # Iterate through the directories and create pages as needed
            for directory in directories:
                # Exit if extension is .md (not a directory)
                if directory.endswith(".md"):
                    break

                # Check if the directory page already exists
                directory_page_id = self.api.get_page_id_by_title(directory)
                
                if directory_page_id is None:
                    # Create the directory page
                    LOGGER.info(f"Creating directory page: {directory}")
                    directory_page = self.api.get_or_create_page(directory, current_page_id)
                    directory_page_id = directory_page.id
                
                # Update the current_page_id for the next iteration
                current_page_id = directory_page_id

            # use file name without extension if no title is supplied
            if title is None:
                title, _ = os.path.splitext(os.path.basename(absolute_path))

            confluence_page = self.api.get_or_create_page(
                title, current_page_id
            )
            self._update_markdown(
                absolute_path,
                document,
                confluence_page.id,
                confluence_page.space_key,
            )

        return ConfluencePageMetadata(
            domain=self.api.domain,
            base_path=self.api.base_path,
            page_id=confluence_page.id,
            space_key=confluence_page.space_key or self.api.space_key,
            title=confluence_page.title or "",
        )

    def _update_document(self, document: ConfluenceDocument, base_path: str) -> None:
        for image in document.images:
            self.api.upload_attachment(
                document.id.page_id, os.path.join(base_path, image), image, ""
            )

        content = document.xhtml()
        LOGGER.debug(f"generated Confluence Storage Format document:\n{content}")
        self.api.update_page(document.id.page_id, content)

    def _update_markdown(
        self,
        path: str,
        document: str,
        page_id: str,
        space_key: Optional[str],
    ) -> None:
        with open(path, "r") as file:
            content = file.read()

        # Check if the file has frontmatter
        if content.startswith("---"):
            # Insert the confluence keys after the frontmatter
            frontmatter_end = content.find("\n---", 4) + 4
            new_content = content[:frontmatter_end] + \
                        f"\n<!-- confluence-page-id: {page_id} -->" + \
                        (f"\n<!-- confluence-space-key: {space_key} -->" if space_key else "") + \
                        content[frontmatter_end:]
        else:
            # Insert the confluence keys at the top of the file
            new_content = f"<!-- confluence-page-id: {page_id} -->\n" + \
                        (f"<!-- confluence-space-key: {space_key} -->\n" if space_key else "") + \
                        content

        with open(path, "w") as file:
            file.write(new_content)
