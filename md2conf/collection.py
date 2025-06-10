"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from pathlib import Path
from typing import Iterable, Optional

from .metadata import ConfluencePageMetadata


class ConfluencePageCollection:
    _metadata: dict[Path, ConfluencePageMetadata]

    def __init__(self) -> None:
        self._metadata = {}

    def __len__(self) -> int:
        return len(self._metadata)

    def add(self, path: Path, data: ConfluencePageMetadata) -> None:
        self._metadata[path] = data

    def get(self, path: Path) -> Optional[ConfluencePageMetadata]:
        return self._metadata.get(path)

    def items(self) -> Iterable[tuple[Path, ConfluencePageMetadata]]:
        return self._metadata.items()
