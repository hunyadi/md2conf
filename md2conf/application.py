import os.path

from .api import ConfluenceSession
from .converter import ConfluenceDocument, markdown_to_html


def synchronize_page(api: ConfluenceSession, path: str) -> None:
    page_path = os.path.abspath(path)
    base_path = os.path.dirname(page_path)

    document = ConfluenceDocument(path)

    for image in document.images:
        api.upload_attachment(document.id, os.path.join(base_path, image), image, "")

    api.update_page(document.id, document.xhtml())
