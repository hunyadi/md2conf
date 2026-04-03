"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from dataclasses import dataclass, field

from .clio import boolean_option


@dataclass
class ConfluenceSessionOptions:
    """
    Options that affect the behavior of a Confluence session.

    :param notify: Whether to notify users about changes to a Confluence page (`True`) or trigger a minor edit (`False`).
    """

    notify: bool = field(
        default=False,
        metadata=boolean_option(
            "Notify users about changes when a Confluence page is updated.",
            "Trigger a minor edit on page updates, don't notify users about changes.",
        ),
    )
