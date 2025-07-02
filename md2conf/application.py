"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
from pathlib import Path
from typing import Optional

from .api import ConfluenceContentProperty, ConfluenceLabel, ConfluenceSession, ConfluenceStatus
from .converter import ConfluenceDocument, ConfluenceDocumentOptions, ConfluencePageID, attachment_name
from .extra import override, path_relative_to
from .metadata import ConfluencePageMetadata
from .processor import Converter, DocumentNode, Processor, ProcessorFactory
from .properties import PageError

LOGGER = logging.getLogger(__name__)


class SynchronizingProcessor(Processor):
    """
    Synchronizes a single Markdown page or a directory of Markdown pages with Confluence.
    """

    api: ConfluenceSession

    def __init__(self, api: ConfluenceSession, options: ConfluenceDocumentOptions, root_dir: Path) -> None:
        """
        Initializes a new processor instance.

        :param api: Holds information about an open session to a Confluence server.
        :param options: Options that control the generated page content.
        :param root_dir: File system directory that acts as topmost root node.
        """

        super().__init__(options, api.site, root_dir)
        self.api = api

    @override
    def _synchronize_tree(self, root: DocumentNode, root_id: Optional[ConfluencePageID]) -> None:
        """
        Creates the cross-reference index and synchronizes the directory tree structure with the Confluence page hierarchy.

        Creates new Confluence pages as necessary, e.g. if no page is linked in the Markdown document, or no page is found with lookup by page title.

        Updates the original Markdown document to add tags to associate the document with its corresponding Confluence page.
        """

        if root.page_id is None and root_id is None:
            raise PageError(f"expected: root page ID in options, or explicit page ID in {root.absolute_path}")
        elif root.page_id is not None and root_id is not None:
            if root.page_id != root_id.page_id:
                raise PageError(f"mismatched inferred page ID of {root_id.page_id} and explicit page ID in {root.absolute_path}")

            real_id = root_id
        elif root_id is not None:
            real_id = root_id
        elif root.page_id is not None:
            real_id = ConfluencePageID(root.page_id)
        else:
            raise NotImplementedError("condition not exhaustive")

        self._synchronize_subtree(root, real_id)

    def _synchronize_subtree(self, node: DocumentNode, parent_id: ConfluencePageID) -> None:
        if node.page_id is not None:
            # verify if page exists
            page = self.api.get_page_properties(node.page_id)
            update = False
        elif node.title is not None:
            # look up page by title
            page = self.api.get_or_create_page(node.title, parent_id.page_id)

            if page.status is ConfluenceStatus.ARCHIVED:
                raise PageError(f"unable to update archived page with ID {page.id}")

            update = True
        else:
            # always create a new page
            digest = self._generate_hash(node.absolute_path)
            title = f"{node.absolute_path.stem} [{digest}]"
            page = self.api.create_page(parent_id.page_id, title, "")
            update = True

        space_key = self.api.space_id_to_key(page.spaceId)
        if update:
            self._update_markdown(
                node.absolute_path,
                page_id=page.id,
                space_key=space_key,
            )

        data = ConfluencePageMetadata(
            page_id=page.id,
            space_key=space_key,
            title=page.title,
        )
        self.page_metadata.add(node.absolute_path, data)

        for child_node in node.children():
            self._synchronize_subtree(child_node, ConfluencePageID(page.id))

    @override
    def _update_page(self, page_id: ConfluencePageID, document: ConfluenceDocument, path: Path) -> None:
        """
        Saves a new version of a Confluence document.

        Invokes Confluence REST API to persist the new version.
        """

        base_path = path.parent
        for image_path in document.images:
            self.api.upload_attachment(
                page_id.page_id,
                attachment_name(path_relative_to(image_path, base_path)),
                attachment_path=image_path,
            )

        for name, data in document.embedded_images.items():
            self.api.upload_attachment(
                page_id.page_id,
                name,
                raw_data=data,
            )

        content = document.xhtml()
        LOGGER.debug("Generated Confluence Storage Format document:\n%s", content)

        title = None
        if document.title is not None:
            meta = self.page_metadata.get(path)
            if meta is not None and meta.space_key is not None and meta.title != document.title:
                conflicting_page_id = self.api.page_exists(document.title, space_id=self.api.space_key_to_id(meta.space_key))
                if conflicting_page_id is None:
                    title = document.title
                else:
                    LOGGER.info(
                        "Document title of %s conflicts with Confluence page title of %s",
                        path,
                        conflicting_page_id,
                    )

        self.api.update_page(page_id.page_id, content, title=title)

        if document.labels is not None:
            self.api.update_labels(
                page_id.page_id,
                [ConfluenceLabel(name=label, prefix="global") for label in document.labels],
            )

        if document.properties is not None:
            self.api.update_content_properties_for_page(page_id.page_id, [ConfluenceContentProperty(key, value) for key, value in document.properties.items()])

    def _update_markdown(self, path: Path, *, page_id: str, space_key: str) -> None:
        """
        Writes the Confluence page ID and space key at the beginning of the Markdown file.
        """

        with open(path, "r", encoding="utf-8") as file:
            document = file.read()

        content: list[str] = []

        # check if the file has frontmatter
        index = 0
        if document.startswith("---\n"):
            index = document.find("\n---\n", 4) + 4

            # insert the Confluence keys after the frontmatter
            content.append(document[:index])

        content.append(f"<!-- confluence-page-id: {page_id} -->")
        content.append(f"<!-- confluence-space-key: {space_key} -->")
        content.append(document[index:])

        with open(path, "w", encoding="utf-8") as file:
            file.write("\n".join(content))


class SynchronizingProcessorFactory(ProcessorFactory):
    api: ConfluenceSession

    def __init__(self, api: ConfluenceSession, options: ConfluenceDocumentOptions) -> None:
        super().__init__(options, api.site)
        self.api = api

    def create(self, root_dir: Path) -> Processor:
        return SynchronizingProcessor(self.api, self.options, root_dir)


class Application(Converter):
    """
    The entry point for Markdown to Confluence conversion.

    This is the class instantiated by the command-line application.
    """

    def __init__(self, api: ConfluenceSession, options: ConfluenceDocumentOptions) -> None:
        super().__init__(SynchronizingProcessorFactory(api, options))
