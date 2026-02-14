"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

from .api import ConfluenceContentProperty, ConfluenceLabel, ConfluencePage, ConfluenceSession, ConfluenceStatus, ConfluenceVersion
from .attachment import attachment_name
from .compatibility import override, path_relative_to
from .converter import ConfluenceDocument, ElementType, get_volatile_attributes, get_volatile_elements
from .csf import AC_ATTR, elements_from_string
from .environment import PageError
from .metadata import ConfluencePageMetadata
from .options import ConfluencePageID, ProcessorOptions
from .processor import DocumentNode, DocumentProcessor, Processor, ProcessorFactory
from .serializer import json_to_object, object_to_json
from .xml import is_xml_equal, unwrap_substitute

LOGGER = logging.getLogger(__name__)


CONTENT_PROPERTY_TAG = "md2conf"


class _MissingType:
    pass


_MissingDefault = _MissingType()


class ParentCatalog:
    "Maintains a catalog of child-parent relationships."

    _api: ConfluenceSession
    _child_to_parent: dict[str, str | None]
    _known: set[str]

    def __init__(self, api: ConfluenceSession) -> None:
        self._api = api
        self._child_to_parent = {}
        self._known = set()

    def add_known(self, page_id: str) -> None:
        """
        Adds a new well-known page such as the root page or a page paired with a Markdown file using an explicit page ID.
        """

        self._known.add(page_id)

    def add_parent(self, *, page_id: str, parent_id: str | None) -> None:
        """
        Adds a new child-parent relationship.

        This method is useful to persist information acquired by a previous API call.
        """

        self._child_to_parent[page_id] = parent_id

    def is_traceable(self, page_id: str) -> bool:
        """
        Verifies if a page traces back to a well-known root page.

        :param page_id: The page to check.
        """

        if page_id in self._known:
            return True

        known_parent_id = self._child_to_parent.get(page_id, _MissingDefault)
        if not isinstance(known_parent_id, _MissingType):
            parent_id = known_parent_id
        else:
            page = self._api.get_page_properties(page_id)
            parent_id = page.parentId
            self._child_to_parent[page_id] = parent_id

        if parent_id is None:
            return False

        return self.is_traceable(parent_id)


@dataclass
class ConfluenceMarkdownTag:
    """
    Captures information used to synchronize the Markdown source file with the Confluence target page.

    :param page_version: Confluence page version number when the page was last synchronized.
    :param source_digest: MD5 hash computed from the Markdown source file.
    """

    page_version: int
    source_digest: str


class SynchronizingProcessor(Processor):
    """
    Synchronizes a single Markdown page or a directory of Markdown pages with Confluence.
    """

    api: ConfluenceSession

    def __init__(self, api: ConfluenceSession, options: ProcessorOptions, root_dir: Path) -> None:
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
            raise NotImplementedError("condition not exhaustive for synchronizing tree")

        catalog = ParentCatalog(self.api)
        catalog.add_known(real_id.page_id)
        self._synchronize_subtree(tree, real_id, catalog)

    def _synchronize_subtree(self, node: DocumentNode, parent_id: ConfluencePageID, catalog: ParentCatalog) -> None:
        if node.page_id is not None:
            # verify if page exists
            page = self.api.get_page_properties(node.page_id)
            catalog.add_known(page.id)
            catalog.add_parent(page_id=page.id, parent_id=page.parentId)
            update = False
        else:
            if node.title is not None:
                # use title extracted from source metadata
                title = node.title
            else:
                # assign an auto-generated title
                digest = self._generate_hash(node.absolute_path)
                title = f"{node.absolute_path.stem} [{digest}]"

            title = self._get_extended_title(title)

            # look up page by (possibly auto-generated) title
            page = self.api.get_or_create_page(title, parent_id.page_id)
            catalog.add_parent(page_id=page.id, parent_id=page.parentId)

            if page.status is ConfluenceStatus.ARCHIVED:
                # user has archived a page with this (possibly auto-generated) title
                raise PageError(f"unable to update archived page with ID {page.id} when synchronizing {node.absolute_path}")

            if not catalog.is_traceable(page.id):
                raise PageError(
                    f"expected: page with ID {page.id} to be a descendant of the root page or one of the pages paired with a Markdown file using an explicit "
                    f"page ID when synchronizing {node.absolute_path}"
                )

            update = True

        # For v1, page.spaceId already contains the space key (not ID)
        # For v2, page.spaceId contains the space ID and needs conversion
        if self.api.api_version == ConfluenceVersion.VERSION_1:
            space_key = page.spaceId  # Already a space key for v1
        else:
            space_key = self.api.space_id_to_key(page.spaceId)

        if update and not self.options.skip_update:
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
            self._synchronize_subtree(child_node, ConfluencePageID(page.id), catalog)

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

        # compute content hash to help detect if document has changed
        m = hashlib.md5()
        with open(path, "rb") as f:
            m.update(f.read())
        source_digest = m.hexdigest()

        # set Confluence title based on Markdown content
        title = self._get_unique_title(document, path)

        # fetch existing page
        page = self.api.get_page(page_id.page_id)
        prop = self.api.get_content_property_for_page(page_id.page_id, CONTENT_PROPERTY_TAG)
        tag: ConfluenceMarkdownTag | None = None
        if prop is not None:
            try:
                tag = json_to_object(ConfluenceMarkdownTag, prop.value)
                LOGGER.debug("Page with ID %s has last synchronized version of %d and hash of %s", page.id, tag.page_version, tag.source_digest)
            except Exception:
                pass

        # keep existing Confluence title if cannot infer meaningful title from Markdown source
        if not title:  # empty or `None`
            title = page.title

        # synchronize page if page has any changes
        if self._has_changes(page, tag, title, document.root, source_digest):
            if tag is not None and page.version.number != tag.page_version:
                LOGGER.warning("Page with ID %s has been edited since last synchronized: %s", page.id, page.title)

            relative_path = path_relative_to(path, self.root_dir)
            version = page.version.number + 1
            self.api.update_page(page.id, content, title=title, version=version, message=f"Synchronized by md2conf from Markdown file: {relative_path}")
        else:
            version = page.version.number

        if document.labels is not None:
            self.api.update_labels(
                page.id,
                [ConfluenceLabel(name=label, prefix="global") for label in document.labels],
            )

        props = [ConfluenceContentProperty(CONTENT_PROPERTY_TAG, object_to_json(ConfluenceMarkdownTag(version, source_digest)))]
        if document.properties is not None:
            props.extend(ConfluenceContentProperty(key, value) for key, value in document.properties.items())
            self.api.update_content_properties_for_page(page.id, props)
        else:
            if tag is None or tag.page_version != version:
                self.api.update_content_properties_for_page(page.id, props, keep_existing=True)

    def _has_changes(self, page: ConfluencePage, tag: ConfluenceMarkdownTag | None, title: str, root: ElementType, source_digest: str) -> bool:
        "True if the Confluence Storage Format content generated from the Markdown source file matches the Confluence target page content."

        if page.title != title:
            LOGGER.info("Detected page with new title: %s", page.id)
            return True

        if tag is not None and tag.source_digest != source_digest:
            LOGGER.info("Detected page with updated Markdown source: %s", page.id)
            return True

        # discard comments
        tree = elements_from_string(page.content)
        unwrap_substitute(AC_ATTR("inline-comment-marker"), tree)

        # visit XML nodes recursively
        if not is_xml_equal(
            root,
            tree,
            skip_attributes=get_volatile_attributes(),
            skip_elements=get_volatile_elements(),
        ):
            LOGGER.info("Detected page with updated Markdown content: %s", page.id)
            return True

        LOGGER.info("Up-to-date page: %s", page.id)
        return False

    def _get_extended_title(self, title: str) -> str:
        """
        Returns a title with the title prefix applied (if any).
        """

        if self.options.title_prefix is not None:
            return f"{self.options.title_prefix} {title}"
        else:
            return title

    def _get_unique_title(self, document: ConfluenceDocument, path: Path) -> str | None:
        """
        Determines the (new) document title to assign to the Confluence page.

        Ensures that the title is unique across the Confluence space.
        """

        # document has no title (neither in front-matter nor as unique top-level heading)
        if document.title is None:
            return None

        # add configured title prefix
        title = self._get_extended_title(document.title)

        # compare current document title with title discovered during directory traversal
        meta = self.page_metadata.get(path)
        if meta is not None and meta.title != title:
            # title has changed, check if new title is available
            # meta.space_key contains the actual space key for both v1 and v2
            # Pass it as space_id parameter (which accepts key for v1, ID for v2)
            if self.api.api_version == ConfluenceVersion.VERSION_1:
                page_id = self.api.page_exists(title, space_id=meta.space_key)
            else:
                page_id = self.api.page_exists(title, space_id=self.api.space_key_to_id(meta.space_key))
            if page_id is not None:
                LOGGER.info("Unrelated Confluence page with ID %s has the same inferred title as the Markdown file: %s", page_id, path)
                return None

        return title

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

    def __init__(self, api: ConfluenceSession, options: ProcessorOptions) -> None:
        super().__init__(options, api.site)
        self.api = api

    def create(self, root_dir: Path) -> Processor:
        return SynchronizingProcessor(self.api, self.options, root_dir)


class Publisher(DocumentProcessor):
    """
    The entry point for Markdown to Confluence conversion.

    This class communicates with Confluence REST API, generating and synchronizing Confluence Storage Format XHTML
    files and attachments.

    This is the class instantiated by the command-line application.
    """

    def __init__(self, api: ConfluenceSession, options: ProcessorOptions) -> None:
        super().__init__(SynchronizingProcessorFactory(api, options))
