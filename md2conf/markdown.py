"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import xml.etree.ElementTree
from typing import Any, Optional

import markdown


def _emoji_generator(
    index: str,
    shortname: str,
    alias: Optional[str],
    uc: Optional[str],
    alt: str,
    title: Optional[str],
    category: Optional[str],
    options: dict[str, Any],
    md: markdown.Markdown,
) -> xml.etree.ElementTree.Element:
    """
    Custom generator for `pymdownx.emoji`.
    """

    name = (alias or shortname).strip(":")
    span = xml.etree.ElementTree.Element("span", {"data-emoji-shortname": name})
    if uc is not None:
        span.attrib["data-emoji-unicode"] = uc

        # convert series of Unicode code point hexadecimal values into characters
        span.text = "".join(chr(int(item, base=16)) for item in uc.split("-"))
    else:
        span.text = alt
    return span


def _math_formatter(
    source: str,
    language: str,
    css_class: str,
    options: dict[str, Any],
    md: markdown.Markdown,
    classes: Optional[list[str]] = None,
    id_value: str = "",
    attrs: Optional[dict[str, str]] = None,
    **kwargs: Any,
) -> str:
    """
    Custom formatter for language `math` in `pymdownx.superfences`.
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
        "pymdownx.emoji",
        "pymdownx.highlight",  # required by `pymdownx.superfences`
        "pymdownx.magiclink",
        "pymdownx.superfences",
        "pymdownx.tilde",
        "sane_lists",
    ],
    extension_configs={
        "footnotes": {"BACKLINK_TITLE": ""},
        "pymdownx.arithmatex": {"generic": True, "preview": False, "tex_inline_wrap": ["", ""], "tex_block_wrap": ["", ""]},
        "pymdownx.emoji": {
            "emoji_generator": _emoji_generator,
        },
        "pymdownx.highlight": {
            "use_pygments": False,
        },
        "pymdownx.superfences": {"custom_fences": [{"name": "math", "class": "arithmatex", "format": _math_formatter}]},
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
