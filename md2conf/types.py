"""
Common type definitions and protocols.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class SynchronizableDocument(Protocol):
    """
    A protocol for document properties that can be used in synchronization filters.
    """

    @property
    def absolute_path(self) -> Path:
        """
        The absolute path to the Markdown document.
        """
        ...

    @property
    def metadata(self) -> dict[str, Any] | None:
        """
        Front-matter metadata from the Markdown document.
        """
        ...
