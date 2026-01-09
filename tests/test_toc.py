"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest

from md2conf.toc import TableOfContentsBuilder, TableOfContentsEntry, headings, unique_title
from tests.utility import TypedTestCase

markdown_content = """
# Section 1

#### Section 1.1
#### Section 1.2

`````md
# not a heading
```
not a heading
=============
`````

    ```
    # not a heading
        ```
    ```

Section 2
=========

Section 2.1
-----------

not a heading
-*-*-*-*-*-*-

## Section 2.2 ##
"""


class TestTableOfContents(TypedTestCase):
    "Simple unit tests without set-up or tear-down requirements."

    def test_hierarchy(self) -> None:
        builder = TableOfContentsBuilder()
        sections = [
            (2, "Section 1"),
            (3, "Section 1.1"),
            (3, "Section 1.2"),
            (6, "Section 1.2.1"),  # test skipping levels
            (6, "Section 1.2.2"),
            (3, "Section 1.3"),
            (4, "Section 1.3.1"),
            (2, "Section 2"),
        ]
        for level, text in sections:
            builder.add(level, text)
        expected = [
            TableOfContentsEntry(
                2,
                "Section 1",
                [
                    TableOfContentsEntry(3, "Section 1.1"),
                    TableOfContentsEntry(
                        3,
                        "Section 1.2",
                        [
                            TableOfContentsEntry(6, "Section 1.2.1"),
                            TableOfContentsEntry(6, "Section 1.2.2"),
                        ],
                    ),
                    TableOfContentsEntry(
                        3,
                        "Section 1.3",
                        [
                            TableOfContentsEntry(4, "Section 1.3.1"),
                        ],
                    ),
                ],
            ),
            TableOfContentsEntry(2, "Section 2"),
        ]
        self.assertEqual(expected, builder.tree)
        self.assertIsNone(builder.get_title())

    def test_title(self) -> None:
        builder = TableOfContentsBuilder()
        sections = [
            (2, "Title"),
            (3, "Section 1"),
            (3, "Section 2"),
            (4, "Section 2.1"),
        ]
        for level, text in sections:
            builder.add(level, text)
        expected = [
            TableOfContentsEntry(
                2,
                "Title",
                [
                    TableOfContentsEntry(3, "Section 1"),
                    TableOfContentsEntry(
                        3,
                        "Section 2",
                        [
                            TableOfContentsEntry(4, "Section 2.1"),
                        ],
                    ),
                ],
            ),
        ]
        self.assertEqual(expected, builder.tree)
        self.assertEqual(builder.get_title(), "Title")

        self.assertIsNone(unique_title(markdown_content))

    def test_headings(self) -> None:
        builder = TableOfContentsBuilder()
        for heading in headings(markdown_content.splitlines(keepends=True)):
            level, text = heading
            builder.add(level, text)

        expected = [
            TableOfContentsEntry(
                1,
                "Section 1",
                [
                    TableOfContentsEntry(4, "Section 1.1"),
                    TableOfContentsEntry(4, "Section 1.2"),
                ],
            ),
            TableOfContentsEntry(
                1,
                "Section 2",
                [
                    TableOfContentsEntry(2, "Section 2.1"),
                    TableOfContentsEntry(2, "Section 2.2"),
                ],
            ),
        ]
        self.assertEqual(expected, builder.tree)


if __name__ == "__main__":
    unittest.main()
