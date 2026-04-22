"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
from pathlib import Path

from md2conf.collection import ConfluenceUserCollection

from .compatibility import override
from .converter import ConfluenceDocument
from .metadata import ConfluencePageMetadata, ConfluenceSiteMetadata
from .options import ConfluencePageID, ProcessorOptions
from .processor import DocumentNode, DocumentProcessor, Processor, ProcessorFactory

LOGGER = logging.getLogger(__name__)


class LocalProcessor(Processor):
    """
    Transforms a single Markdown page or a directory of Markdown pages into Confluence Storage Format (CSF) documents.
    """

    def __init__(
        self,
        options: ProcessorOptions,
        site: ConfluenceSiteMetadata,
        *,
        out_dir: Path | None,
        root_dir: Path,
    ) -> None:
        """
        Initializes a new processor instance.

        :param options: Options that control the generated page content.
        :param site: Data associated with a Confluence wiki site.
        :param out_dir: File system directory to write generated CSF documents to.
        :param root_dir: File system directory that acts as topmost root node.
        """

        super().__init__(options, site, root_dir)
        self.out_dir = out_dir or root_dir

    @override
    def _synchronize_structure(self, tree: DocumentNode) -> None:
        """
        Creates the cross-reference index.

        Does not change Markdown files.
        """

        for node in tree.all():
            if node.page_id is not None:
                page_id = node.page_id
            else:
                digest = self._generate_hash(node.absolute_path)
                LOGGER.info("Identifier %s assigned to page: %s", digest, node.absolute_path)
                page_id = digest

            self.page_metadata.add(
                node.absolute_path,
                ConfluencePageMetadata(
                    page_id=page_id,
                    space_key=node.space_key or self.site.space_key or "HOME",
                    title=node.title or "",
                    synchronized=node.synchronized,
                ),
            )

    @override
    def _synchronize_users(self, users: set[tuple[str, str]]) -> ConfluenceUserCollection:
        """
        Fetches Confluence user account IDs.

        This implementation does not fetch any account IDs, as it maintains no connection to a Confluence server.
        """

        return ConfluenceUserCollection()

    @override
    def _update_page(self, page_id: ConfluencePageID, document: ConfluenceDocument, path: Path) -> None:
        """
        Saves the document as Confluence Storage Format XHTML to the local disk.
        """

        content = document.xhtml()
        csf_path = self.out_dir / path.relative_to(self.root_dir).with_suffix(".csf")
        csf_dir = csf_path.parent
        os.makedirs(csf_dir, exist_ok=True)
        csf_path.write_text(content, encoding="utf-8")
        for name, file_data in document.embedded_files.items():
            (csf_dir / name).write_bytes(file_data.data)


class LocalProcessorFactory(ProcessorFactory):
    out_dir: Path | None

    def __init__(
        self,
        options: ProcessorOptions,
        site: ConfluenceSiteMetadata,
        out_dir: Path | None = None,
    ) -> None:
        super().__init__(options, site)
        self.out_dir = out_dir

    def create(self, root_dir: Path) -> Processor:
        return LocalProcessor(self.options, self.site, out_dir=self.out_dir, root_dir=root_dir)


class LocalConverter(DocumentProcessor):
    """
    The entry point for Markdown to Confluence conversion.

    This class converts documents locally, producing Confluence Storage Format XHTML files as output.

    This is the class instantiated by the command-line application.
    """

    def __init__(
        self,
        options: ProcessorOptions,
        site: ConfluenceSiteMetadata,
        out_dir: Path | None = None,
    ) -> None:
        super().__init__(LocalProcessorFactory(options, site, out_dir))
