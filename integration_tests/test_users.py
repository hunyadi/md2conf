"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import os.path
import unittest

from md2conf.api import ConfluenceAPI
from tests.utility import TypedTestCase


class TestConfluenceUsers(TypedTestCase):
    def test_users(self) -> None:
        with ConfluenceAPI() as api:
            users = api.get_users("levente")
            self.assertGreaterEqual(len(users), 1)
            matches = [user for user in users if user.email is not None and "hunyadi" in user.email]
            self.assertEqual(len(matches), 1)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
    )

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s")

    (name, _) = os.path.splitext(os.path.basename(__file__))
    handler = logging.FileHandler(os.path.join(os.path.dirname(__file__), f"{name}.log"), "w", "utf-8")
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    unittest.main()
