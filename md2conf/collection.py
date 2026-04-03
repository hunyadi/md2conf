"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from collections.abc import Mapping
from pathlib import Path
from typing import Generic, Iterable, TypeVar

from .metadata import ConfluencePageMetadata

K = TypeVar("K")
V = TypeVar("V")


class KeyValueCollection(Generic[K, V]):
    _collection: dict[K, V]

    def __init__(self, items: Mapping[K, V] | None = None) -> None:
        if items is not None:
            self._collection = dict(items)
        else:
            self._collection = {}

    def __len__(self) -> int:
        return len(self._collection)

    def add(self, key: K, data: V) -> None:
        self._collection[key] = data

    def get(self, key: K) -> V | None:
        return self._collection.get(key)

    def items(self) -> Iterable[tuple[K, V]]:
        return self._collection.items()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._collection!r})"


class ConfluencePageCollection(KeyValueCollection[Path, ConfluencePageMetadata]): ...
