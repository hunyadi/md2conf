"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from pathlib import Path
from typing import Generic, Iterable, TypeVar

from .metadata import ConfluencePageMetadata

K = TypeVar("K")
V = TypeVar("V")


class KeyValueCollection(Generic[K, V]):
    _collection: dict[K, V]

    def __init__(self) -> None:
        self._collection = {}

    def __len__(self) -> int:
        return len(self._collection)

    def add(self, key: K, data: V) -> None:
        self._collection[key] = data

    def get(self, key: K) -> V | None:
        return self._collection.get(key)

    def items(self) -> Iterable[tuple[K, V]]:
        return self._collection.items()


class ConfluencePageCollection(KeyValueCollection[Path, ConfluencePageMetadata]): ...
