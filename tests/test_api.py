import logging
import os
import os.path
import shutil
import unittest
from pathlib import Path

from md2conf.api import ConfluenceAPI, ConfluenceAttachment, ConfluencePage
from md2conf.application import Application
from md2conf.converter import (
    ConfluenceDocument,
    ConfluenceDocumentOptions,
    sanitize_confluence,
)
from md2conf.properties import ConfluenceProperties

TEST_PAGE_ID = "85668266616"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestAPI(unittest.TestCase):
    out_dir: Path

    def setUp(self) -> None:
        test_dir = Path(__file__).parent
        parent_dir = test_dir.parent

        self.out_dir = test_dir / "tests" / "output"
        self.sample_dir = parent_dir / "sample"
        os.makedirs(self.out_dir, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.out_dir)

    def test_markdown(self) -> None:
        document = ConfluenceDocument(
            str(self.sample_dir / "example.md"),
            ConfluenceDocumentOptions(ignore_invalid_url=True),
            {},
        )
        self.assertListEqual(document.links, [])
        self.assertListEqual(
            document.images,
            ["figure/interoperability.png", "figure/interoperability.png"],
        )

        with open(os.path.join(self.out_dir, "document.html"), "w") as f:
            f.write(document.xhtml())

    def test_find_page_by_title(self) -> None:
        with ConfluenceAPI() as api:
            id = api.get_page_id_by_title("Test Page")
            self.assertEqual(id, "%s" % TEST_PAGE_ID)

    def test_switch_space(self) -> None:
        with ConfluenceAPI(ConfluenceProperties(space_key="PLAT")) as api:
            with api.switch_space("DAP"):
                id = api.get_page_id_by_title("Publish to Confluence")
                self.assertEqual(id, TEST_PAGE_ID)

    def test_get_page(self) -> None:
        with ConfluenceAPI() as api:
            page = api.get_page(TEST_PAGE_ID)
            self.assertIsInstance(page, ConfluencePage)

        with open(os.path.join(self.out_dir, "page.html"), "w") as f:
            f.write(sanitize_confluence(page.content))

    def test_get_attachment(self) -> None:
        with ConfluenceAPI() as api:
            data = api.get_attachment_by_name(
                TEST_PAGE_ID, "figure/interoperability.png"
            )
            self.assertIsInstance(data, ConfluenceAttachment)

    def test_upload_attachment(self) -> None:
        with ConfluenceAPI() as api:
            api.upload_attachment(
                TEST_PAGE_ID,
                str(self.sample_dir / "figure" / "interoperability.png"),
                "figure/interoperability.png",
                "A sample figure",
            )

    def test_synchronize(self) -> None:
        with ConfluenceAPI() as api:
            Application(
                api, ConfluenceDocumentOptions(ignore_invalid_url=True)
            ).synchronize(str(self.sample_dir / "example.md"))

    def test_synchronize_page(self) -> None:
        with ConfluenceAPI() as api:
            Application(
                api, ConfluenceDocumentOptions(ignore_invalid_url=True)
            ).synchronize_page(str(self.sample_dir / "example.md"))

    def test_synchronize_directory(self) -> None:
        with ConfluenceAPI() as api:
            Application(
                api, ConfluenceDocumentOptions(ignore_invalid_url=True)
            ).synchronize_directory(str(self.sample_dir))

    def test_synchronize_create(self) -> None:
        dir = os.path.join(self.out_dir, "markdown")
        dir = self.out_dir / "markdown"
        os.makedirs(dir, exist_ok=True)

        child = os.path.join(dir, "child.md")
        with open(child, "w") as f:
            f.write(
                "This is a document without an explicitly linked Confluence document.\n"
            )

        with ConfluenceAPI() as api:
            Application(
                api,
                ConfluenceDocumentOptions(
                    ignore_invalid_url=True, root_page_id="86090481730"
                ),
            ).synchronize_directory(str(dir))

        with open(child, "r") as f:
            self.assertEqual(
                f.read(),
                "<!-- confluence-page-id: 86269493445 -->\n"
                "<!-- confluence-space-key: DAP -->\n"
                "This is a document without an explicitly linked Confluence document.\n",
            )


if __name__ == "__main__":
    unittest.main()
