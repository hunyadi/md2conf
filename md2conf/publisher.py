"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
from pathlib import Path

from .api import ConfluenceContentProperty, ConfluenceLabel, ConfluenceSession, ConfluenceStatus
from .attachment import attachment_name
from .compatibility import override, path_relative_to
from .converter import ConfluenceDocument, get_volatile_attributes, get_volatile_elements
from .csf import AC_ATTR, elements_from_string
from .environment import PageError
from .metadata import ConfluencePageMetadata
from .options import ConfluencePageID, DocumentOptions
from .processor import Converter, DocumentNode, Processor, ProcessorFactory
from .xml import is_xml_equal, unwrap_substitute

LOGGER = logging.getLogger(__name__)


class SynchronizingProcessor(Processor):
    """
    Synchronizes a single Markdown page or a directory of Markdown pages with Confluence.
    """

    api: ConfluenceSession

    def __init__(self, api: ConfluenceSession, options: DocumentOptions, root_dir: Path) -> None:
        """
        Initializes a new processor instance.

        :param api: Holds information about an open session to a Confluence server.
        :param options: Options that control the generated page content.
        :param root_dir: File system directory that acts as topmost root node.
        """

        super().__init__(options, api.site, root_dir)
        self.api = api

    @override
    def _synchronize_tree(self, tree: DocumentNode, root_id: ConfluencePageID | None) -> None:
        """
        Creates the cross-reference index and synchronizes the directory tree structure with the Confluence page hierarchy.

        Creates new Confluence pages as necessary, e.g. if no page is linked in the Markdown document, or no page is found with lookup by page title.

        Updates the original Markdown document to add tags to associate the document with its corresponding Confluence page.
        """

        if tree.page_id is None and root_id is None:
            raise PageError(f"expected: root page ID in options, or explicit page ID in {tree.absolute_path}")
        elif tree.page_id is not None:
            real_id = ConfluencePageID(tree.page_id)  # explicit page ID takes precedence
        elif root_id is not None:
            real_id = root_id
        else:
            raise NotImplementedError("condition not exhaustive")

        self._synchronize_subtree(tree, real_id)

    def _synchronize_subtree(self, node: DocumentNode, parent_id: ConfluencePageID) -> None:
        if node.page_id is not None:
            # verify if page exists
            page = self.api.get_page_properties(node.page_id)
            update = False
        else:
            if node.title is not None:
                # use title extracted from source metadata
                title = node.title
            else:
                # assign an auto-generated title
                digest = self._generate_hash(node.absolute_path)
                title = f"{node.absolute_path.stem} [{digest}]"

            if self.options.title_prefix is not None:
                title = f"{self.options.title_prefix} {title}"

            # look up page by (possibly auto-generated) title
            page = self.api.get_or_create_page(title, parent_id.page_id)

            if page.status is ConfluenceStatus.ARCHIVED:
                # user has archived a page with this (auto-generated) title
                raise PageError(f"unable to update archived page with ID {page.id}")

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
            synchronized=node.synchronized,
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
        for image_data in document.images:
            self.api.upload_attachment(
                page_id.page_id,
                attachment_name(path_relative_to(image_data.path, base_path)),
                attachment_path=image_data.path,
                comment=image_data.description,
            )

        for name, file_data in document.embedded_files.items():
            self.api.upload_attachment(
                page_id.page_id,
                name,
                raw_data=file_data.data,
                comment=file_data.description,
            )

        content = document.xhtml()
        LOGGER.debug("Generated Confluence Storage Format document:\n%s", content)

        title = None
        if document.title is not None:
            meta = self.page_metadata.get(path)
            if meta is not None and meta.title != document.title:
                conflicting_page_id = self.api.page_exists(document.title, space_id=self.api.space_key_to_id(meta.space_key))
                if conflicting_page_id is None:
                    title = document.title
                else:
                    LOGGER.info(
                        "Document title of %s conflicts with Confluence page title of %s",
                        path,
                        conflicting_page_id,
                    )

        # fetch existing page
        page = self.api.get_page(page_id.page_id)
        if not title:  # empty or `None`
            title = page.title

        # discard comments
        tree = elements_from_string(page.content)
        unwrap_substitute(AC_ATTR("inline-comment-marker"), tree)

        # check if page has any changes
        if page.title != title or not is_xml_equal(
            document.root,
            tree,
            skip_attributes=get_volatile_attributes(),
            skip_elements=get_volatile_elements(),
        ):
            self.api.update_page(page_id.page_id, content, title=title, version=page.version.number + 1)
        else:
            LOGGER.info("Up-to-date page: %s", page_id.page_id)

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

    def __init__(self, api: ConfluenceSession, options: DocumentOptions) -> None:
        super().__init__(options, api.site)
        self.api = api

    def create(self, root_dir: Path) -> Processor:
        return SynchronizingProcessor(self.api, self.options, root_dir)


class Publisher(Converter):
    """
    The entry point for Markdown to Confluence conversion.

    This is the class instantiated by the command-line application.
    """

    def __init__(self, api: ConfluenceSession, options: DocumentOptions) -> None:
        super().__init__(SynchronizingProcessorFactory(api, options))
