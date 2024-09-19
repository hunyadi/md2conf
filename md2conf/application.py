import logging
import os.path
from pathlib import Path
from typing import Dict, List, Optional

from .api import ConfluenceSession
from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageMetadata,
    attachment_name,
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

    def synchronize(self, path: Path) -> None:
        "Synchronizes a single Markdown page or a directory of Markdown pages."

        if path.is_dir():
            self.synchronize_directory(path)
        elif path.is_file():
            self.synchronize_page(path)
        else:
            raise ValueError(f"expected: valid file or directory path; got: {path}")

    def synchronize_page(self, page_path: Path) -> None:
        "Synchronizes a single Markdown page with Confluence."

        self._synchronize_page(page_path, {})

    def _get_qualified_id(self, absolute_path: Path) -> Optional[str]:
        with open(absolute_path, "r", encoding="utf-8") as f:
            document = f.read()

        qualified_id, _ = extract_qualified_id(document)
        if qualified_id is not None:
            return qualified_id.page_id
        else:
            return None

    def _index_directory(
        self,
        local_dir: Path,
        root_id: Optional[str],
        page_metadata: Dict[Path, ConfluencePageMetadata],
    ) -> None:
        "Indexes Markdown files in a directory recursively."

        LOGGER.info(f"Synchronizing directory: {local_dir}")

        files: List[Path] = []
        directories: List[Path] = []
        for entry in os.scandir(local_dir):
            if entry.is_file():
                if entry.name.endswith(".md"):
                    # skip non-markdown files
                    files.append((Path(local_dir) / entry.name).absolute())
            elif entry.is_dir():
                if not entry.name.startswith("."):
                    directories.append((Path(local_dir) / entry.name).absolute())

        # make page act as parent node in Confluence
        parent_id: Optional[str] = None
        if "index.md" in files:
            parent_id = self._get_qualified_id(Path(local_dir) / "index.md")
        elif "README.md" in files:
            parent_id = self._get_qualified_id(Path(local_dir) / "README.md")

        if parent_id is None:
            parent_id = root_id

        for doc in files:
            metadata = self._get_or_create_page(doc, parent_id)
            LOGGER.debug(f"indexed {doc} with metadata: {metadata}")
            page_metadata[doc] = metadata

        for directory in directories:
            self._index_directory(Path(local_dir) / directory, parent_id, page_metadata)

    def synchronize_directory(self, local_dir: Path) -> None:
        "Synchronizes a directory of Markdown pages with Confluence."

        # Step 1: build index of all page metadata
        page_metadata: Dict[Path, ConfluencePageMetadata] = {}
        self._index_directory(local_dir, self.options.root_page_id, page_metadata)
        LOGGER.info(f"indexed {len(page_metadata)} page(s)")

        # Step 2: convert each page
        for page_path in page_metadata.keys():
            self._synchronize_page(page_path, page_metadata)

    def _synchronize_page(
        self,
        page_path: Path,
        page_metadata: Dict[Path, ConfluencePageMetadata],
    ) -> None:
        base_path = page_path.parent

        LOGGER.info(f"Synchronizing page: {page_path}")
        document = ConfluenceDocument(page_path, self.options, page_metadata)

        if document.id.space_key:
            with self.api.switch_space(document.id.space_key):
                self._update_document(document, base_path)
        else:
            self._update_document(document, base_path)

    def _get_or_create_page(
        self,
        absolute_path: Path,
        parent_id: Optional[str],
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
            confluence_page = self.api.get_page(
                qualified_id.page_id, space_key=qualified_id.space_key
            )
        else:
            if parent_id is None:
                raise ValueError(
                    "expected: Confluence page ID to act as parent for Markdown files with no linked Confluence page"
                )

            # use file name without extension if no title is supplied
            if title is None:
                title = absolute_path.stem

            confluence_page = self.api.get_or_create_page(title, parent_id)
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

    def _update_document(self, document: ConfluenceDocument, base_path: Path) -> None:

        for image in document.images:
            self.api.upload_attachment(
                document.id.page_id,
                base_path / image,
                attachment_name(image),
            )

        for image, data in document.embedded_images.items():
            self.api.upload_attachment(
                document.id.page_id,
                Path("EMB") / image,
                attachment_name(image),
                raw_data=data,
            )

        content = document.xhtml()
        LOGGER.debug(f"generated Confluence Storage Format document:\n{content}")
        self.api.update_page(document.id.page_id, content)

    def _update_markdown(
        self,
        path: Path,
        document: str,
        page_id: str,
        space_key: Optional[str],
    ) -> None:
        with open(path, "w", encoding="utf-8") as file:
            file.write(f"<!-- confluence-page-id: {page_id} -->\n")
            if space_key:
                file.write(f"<!-- confluence-space-key: {space_key} -->\n")
            file.write(document)
