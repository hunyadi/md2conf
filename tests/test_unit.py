"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import unittest

from md2conf.converter import attachment_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


class TestUnit(unittest.TestCase):
    "Simple unit tests without set-up or tear-down requirements."

    def test_attachment(self) -> None:
        self.assertEqual(attachment_name("image"), "image")
        self.assertEqual(attachment_name("a.png"), "a.png")
        self.assertEqual(attachment_name("a/b.png"), "a_b.png")
        self.assertEqual(attachment_name("../a.png"), "PAR_a.png")
        with self.assertRaises(ValueError):
            _ = attachment_name("/path/to/image.png")


if __name__ == "__main__":
    unittest.main()
