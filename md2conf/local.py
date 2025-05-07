"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageID,
    ConfluenceQualifiedID,
    extract_qualified_id,
)
from .metadata import ConfluencePageMetadata, ConfluenceSiteMetadata
from .processor import Converter, Processor, ProcessorFactory
from .properties import ArgumentError

LOGGER = logging.getLogger(__name__)


class LocalProcessor(Processor):
    def _get_or_create_page(
        self,
        absolute_path: Path,
        parent_id: Optional[ConfluencePageID],
        *,
        title: Optional[str] = None,
    ) -> ConfluencePageMetadata:
        """
        Extracts metadata from a Markdown file.

        A derived class may create a new Confluence page if no page is linked in the Markdown document.
        """

        with open(absolute_path, "r", encoding="utf-8") as f:
            document = f.read()

        qualified_id, document = extract_qualified_id(document)
        if qualified_id is None:
            if self.options.root_page_id is not None:
                hash = hashlib.md5(document.encode("utf-8"))
                digest = "".join(f"{c:x}" for c in hash.digest())
                LOGGER.info("Identifier %s assigned to page: %s", digest, absolute_path)
                qualified_id = ConfluenceQualifiedID(digest)
            else:
                raise ArgumentError("required: page ID for local output")

        return ConfluencePageMetadata(
            page_id=qualified_id.page_id,
            space_key=qualified_id.space_key,
            title="",
        )

    def _save_document(self, document: ConfluenceDocument, path: Path) -> None:
        """
        Saves a new version of a Confluence document.

        A derived class may invoke Confluence REST API to persist the new version.
        """

        content = document.xhtml()
        with open(path.with_suffix(".csf"), "w", encoding="utf-8") as f:
            f.write(content)


class LocalProcessorFactory(ProcessorFactory):
    options: ConfluenceDocumentOptions
    site: ConfluenceSiteMetadata

    def create(self, root_dir: Path) -> Processor:
        return LocalProcessor(self.options, self.site, root_dir)


class LocalConverter(Converter):
    """
    The entry point for Markdown to Confluence conversion.
    """

    def __init__(
        self, options: ConfluenceDocumentOptions, site: ConfluenceSiteMetadata
    ) -> None:
        super().__init__(LocalProcessorFactory(options, site))
