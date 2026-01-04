"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os
from pathlib import Path

from .compatibility import override
from .converter import ConfluenceDocument
from .metadata import ConfluencePageMetadata, ConfluenceSiteMetadata
from .options import ConfluencePageID, DocumentOptions
from .processor import Converter, DocumentNode, Processor, ProcessorFactory

LOGGER = logging.getLogger(__name__)


class LocalProcessor(Processor):
    """
    Transforms a single Markdown page or a directory of Markdown pages into Confluence Storage Format (CSF) documents.
    """

    def __init__(
        self,
        options: DocumentOptions,
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
    def _synchronize_tree(self, tree: DocumentNode, root_id: ConfluencePageID | None) -> None:
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
    def _update_page(self, page_id: ConfluencePageID, document: ConfluenceDocument, path: Path) -> None:
        """
        Saves the document as Confluence Storage Format XHTML to the local disk.
        """

        content = document.xhtml()
        csf_path = self.out_dir / path.relative_to(self.root_dir).with_suffix(".csf")
        csf_dir = csf_path.parent
        os.makedirs(csf_dir, exist_ok=True)
        with open(csf_path, "w", encoding="utf-8") as f:
            f.write(content)
        for name, file_data in document.embedded_files.items():
            with open(csf_dir / name, "wb") as f:
                f.write(file_data.data)


class LocalProcessorFactory(ProcessorFactory):
    out_dir: Path | None

    def __init__(
        self,
        options: DocumentOptions,
        site: ConfluenceSiteMetadata,
        out_dir: Path | None = None,
    ) -> None:
        super().__init__(options, site)
        self.out_dir = out_dir

    def create(self, root_dir: Path) -> Processor:
        return LocalProcessor(self.options, self.site, out_dir=self.out_dir, root_dir=root_dir)


class LocalConverter(Converter):
    """
    The entry point for Markdown to Confluence conversion.
    """

    def __init__(
        self,
        options: DocumentOptions,
        site: ConfluenceSiteMetadata,
        out_dir: Path | None = None,
    ) -> None:
        super().__init__(LocalProcessorFactory(options, site, out_dir))
