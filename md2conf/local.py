"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Optional

from .converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    ConfluencePageID,
    extract_extended_id,
)
from .metadata import ConfluencePageMetadata, ConfluenceSiteMetadata
from .processor import Converter, Processor, ProcessorFactory
from .properties import PageError

LOGGER = logging.getLogger(__name__)


class LocalProcessor(Processor):
    """
    Transforms a single Markdown page or a directory of Markdown pages into Confluence Storage Format (CSF) documents.
    """

    def __init__(
        self,
        options: ConfluenceDocumentOptions,
        site: ConfluenceSiteMetadata,
        *,
        out_dir: Optional[Path],
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

    def _get_or_create_page(
        self,
        absolute_path: Path,
        parent_id: Optional[ConfluencePageID],
        *,
        title: Optional[str] = None,
    ) -> ConfluencePageMetadata:
        """
        Extracts metadata from a Markdown file.
        """

        # parse file
        with open(absolute_path, "r", encoding="utf-8") as f:
            text = f.read()

        extended_id, text = extract_extended_id(text)
        if extended_id is not None:
            page_id = extended_id.page_id
            space_key = extended_id.space_key or self.site.space_key or "HOME"
        else:
            if parent_id is None:
                raise PageError(
                    f"expected: parent page ID for Markdown file with no linked Confluence page: {absolute_path}"
                )

            hash = hashlib.md5(text.encode("utf-8"))
            digest = "".join(f"{c:x}" for c in hash.digest())
            LOGGER.info("Identifier %s assigned to page: %s", digest, absolute_path)
            page_id = digest
            space_key = self.site.space_key or "HOME"

        return ConfluencePageMetadata(
            page_id=page_id,
            space_key=space_key,
            title="",
            overwrite=True,
        )

    def _save_document(
        self, page_id: ConfluencePageID, document: ConfluenceDocument, path: Path
    ) -> None:
        """
        Saves a new version of a Confluence document.

        A derived class may invoke Confluence REST API to persist the new version.
        """

        content = document.xhtml()
        out_path = self.out_dir / path.relative_to(self.root_dir).with_suffix(".csf")
        os.makedirs(out_path.parent, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)


class LocalProcessorFactory(ProcessorFactory):
    out_dir: Optional[Path]

    def __init__(
        self,
        options: ConfluenceDocumentOptions,
        site: ConfluenceSiteMetadata,
        out_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(options, site)
        self.out_dir = out_dir

    def create(self, root_dir: Path) -> Processor:
        return LocalProcessor(
            self.options, self.site, out_dir=self.out_dir, root_dir=root_dir
        )


class LocalConverter(Converter):
    """
    The entry point for Markdown to Confluence conversion.
    """

    def __init__(
        self,
        options: ConfluenceDocumentOptions,
        site: ConfluenceSiteMetadata,
        out_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(LocalProcessorFactory(options, site, out_dir))
