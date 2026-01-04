"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import xml.etree.ElementTree
from typing import Any

import markdown


def _emoji_generator(
    index: str,
    shortname: str,
    alias: str | None,
    uc: str | None,
    alt: str,
    title: str | None,
    category: str | None,
    options: dict[str, Any],
    md: markdown.Markdown,
) -> xml.etree.ElementTree.Element:
    """
    Custom generator for `pymdownx.emoji`.
    """

    name = (alias or shortname).strip(":")
    emoji = xml.etree.ElementTree.Element("x-emoji", {"data-shortname": name})
    if uc is not None:
        emoji.attrib["data-unicode"] = uc

        # convert series of Unicode code point hexadecimal values into characters
        emoji.text = "".join(chr(int(item, base=16)) for item in uc.split("-"))
    else:
        emoji.text = alt

    return emoji


def _verbatim_formatter(
    source: str,
    language: str,
    css_class: str,
    options: dict[str, Any],
    md: markdown.Markdown,
    classes: list[str] | None = None,
    id_value: str = "",
    attrs: dict[str, str] | None = None,
    **kwargs: Any,
) -> str:
    """
    Custom formatter for `pymdownx.superfences`.

    Used by language `math` (a.k.a. `pymdownx.arithmatex`) and pseudo-language `csf` (Confluence Storage Format pass-through).
    """

    if classes is None:
        classes = [css_class]
    else:
        classes.insert(0, css_class)

    html_id = f' id="{id_value}"' if id_value else ""
    html_class = ' class="{}"'.format(" ".join(classes))
    html_attrs = " " + " ".join(f'{k}="{v}"' for k, v in attrs.items()) if attrs else ""

    return f"<div{html_id}{html_class}{html_attrs}>{source}</div>"


_CONVERTER = markdown.Markdown(
    extensions=[
        "admonition",
        "footnotes",
        "markdown.extensions.tables",
        "md_in_html",
        "pymdownx.arithmatex",
        "pymdownx.caret",
        "pymdownx.emoji",
        "pymdownx.highlight",  # required by `pymdownx.superfences`
        "pymdownx.magiclink",
        "pymdownx.mark",
        "pymdownx.superfences",
        "pymdownx.tilde",
        "sane_lists",
    ],
    extension_configs={
        "footnotes": {"BACKLINK_TITLE": ""},
        "pymdownx.arithmatex": {"generic": True, "preview": False, "tex_inline_wrap": ["", ""], "tex_block_wrap": ["", ""]},
        "pymdownx.emoji": {"emoji_generator": _emoji_generator},
        "pymdownx.highlight": {
            "use_pygments": False,
        },
        "pymdownx.superfences": {
            "custom_fences": [
                {"name": "math", "class": "arithmatex", "format": _verbatim_formatter},
                {"name": "csf", "class": "csf", "format": _verbatim_formatter},
            ]
        },
    },
)


def markdown_to_html(content: str) -> str:
    """
    Converts a Markdown document into XHTML with Python-Markdown.

    :param content: Markdown input as a string.
    :returns: XHTML output as a string.
    :see: https://python-markdown.github.io/
    """

    _CONVERTER.reset()
    html = _CONVERTER.convert(content)
    return html
