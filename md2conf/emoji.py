"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import pathlib

import pymdownx.emoji1_db as emoji_db

EMOJI_PAGE_ID = "13500452"


def to_html(cp: int) -> str:
    """
    Returns the safe HTML representation for a Unicode code point.

    Converts non-ASCII and non-printable characters into HTML entities with decimal notation.

    :param cp: Unicode code point.
    :returns: An HTML representation of the Unicode character.
    """

    ch = chr(cp)
    if ch.isascii() and ch.isalnum():
        return ch
    else:
        return f"&#{cp};"


def generate_source(path: pathlib.Path) -> None:
    "Generates a source Markdown document for testing emojis."

    emojis = emoji_db.emoji

    with open(path, "w") as f:
        print(f"<!-- confluence-page-id: {EMOJI_PAGE_ID} -->", file=f)
        print("<!-- This file has been generated by a script. -->", file=f)
        print(file=f)
        print("## Emoji", file=f)
        print(file=f)
        print("| Icon | Emoji code |", file=f)
        print("| ---- | ---------- |", file=f)
        for key in emojis.keys():
            key = key.strip(":")
            print(f"| :{key}: | `:{key}:` |", file=f)


def generate_target(path: pathlib.Path) -> None:
    "Generates a target Confluence Storage Format (XML) document for testing emojis."

    emojis = emoji_db.emoji

    with open(path, "w") as f:
        print('<ac:structured-macro ac:name="info" ac:schema-version="1">', file=f)
        print("<ac:rich-text-body>", file=f)
        print("<p>This page has been generated with a tool.</p>", file=f)
        print("</ac:rich-text-body>", file=f)
        print("</ac:structured-macro>", file=f)
        print("<h2>Emoji</h2>", file=f)
        print("<table>", file=f)
        print("<thead><tr><th>Icon</th><th>Emoji code</th></tr></thead>", file=f)
        print("<tbody>", file=f)
        for key, data in emojis.items():
            unicode = data["unicode"]
            key = key.strip(":")
            html = "".join(to_html(int(item, base=16)) for item in unicode.split("-"))

            print(
                f"<tr>\n"
                f"  <td>\n"
                f'    <ac:emoticon ac:name="{key}" ac:emoji-shortname=":{key}:" ac:emoji-id="{unicode}" ac:emoji-fallback="{html}"/>\n'
                f"  </td>\n"
                f"  <td>\n"
                f"    <code>:{key}:</code>\n"
                f"  </td>\n"
                f"</tr>",
                file=f,
            )
        print("</tbody>", file=f)
        print("</table>", file=f)
