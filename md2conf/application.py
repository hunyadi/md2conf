import os.path

from .api import ConfluenceSession
from .converter import ConfluenceDocument


def update_document(
    api: ConfluenceSession, document: ConfluenceDocument, base_path: str
) -> None:
    for image in document.images:
        api.upload_attachment(
            document.page_id, os.path.join(base_path, image), image, ""
        )

    api.update_page(document.page_id, document.xhtml())


def synchronize_page(api: ConfluenceSession, path: str) -> None:
    page_path = os.path.abspath(path)
    base_path = os.path.dirname(page_path)

    document = ConfluenceDocument(path)

    if document.space_key:
        with api.switch_space(document.space_key):
            update_document(api, document, base_path)
    else:
        update_document(api, document, base_path)
