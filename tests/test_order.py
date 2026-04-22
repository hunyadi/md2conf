"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import logging
import string
import unittest
from dataclasses import dataclass
from random import shuffle
from typing import Literal

from md2conf.order import sort_items_in_order
from tests.utility import TypedTestCase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)


@dataclass(frozen=True)
class _Item:
    key: int
    label: str


class _Container:
    __slots__ = ("_items", "_actions")

    _items: list[_Item]
    _actions: list[tuple[Literal["insert_before", "insert_after"], _Item, _Item]]

    def __init__(self, items: list[_Item]) -> None:
        self._items = list(items)
        self._actions = []

    @property
    def items(self) -> list[_Item]:
        return self._items

    def insert_before(self, item: _Item, ref: _Item) -> None:
        self._actions.append(("insert_before", item, ref))

    def insert_after(self, item: _Item, ref: _Item) -> None:
        self._actions.append(("insert_after", item, ref))

    def apply(self) -> int:
        for action, item, ref in self._actions:
            current_index = self._items.index(item)
            target_index = self._items.index(ref)
            match action:
                case "insert_before":
                    pass
                case "insert_after":
                    target_index += 1
            self._items.pop(current_index)
            if current_index < target_index:
                target_index -= 1
            self._items.insert(target_index, item)

        count = len(self._actions)
        self._actions.clear()
        return count


class TestOrder(TypedTestCase):
    def test_sorted_with_minimal_moves(self) -> None:
        items = [_Item(3, "c"), _Item(1, "a"), _Item(2, "b"), _Item(4, "d")]
        container = _Container(items)

        sort_items_in_order(
            container.items,
            key=lambda item: item.key,
            insert_before=container.insert_before,
            insert_after=container.insert_after,
        )

        calls = container.apply()
        self.assertEqual(sorted(items, key=lambda item: item.key), container.items)
        self.assertEqual(calls, 1)

    def test_equal_keys_keep_stable_order(self) -> None:
        items = [_Item(2, "b1"), _Item(1, "a"), _Item(2, "b2"), _Item(0, "z")]
        container = _Container(items)

        sort_items_in_order(
            container.items,
            key=lambda item: item.key,
            insert_before=container.insert_before,
            insert_after=container.insert_after,
        )

        calls = container.apply()
        self.assertEqual(sorted(items, key=lambda item: item.key), container.items)
        self.assertEqual(calls, 2)

    def test_order_random(self) -> None:
        items = [_Item(i, f"{string.printable[i // 100]}{string.printable[i % 100]}") for i in range(1000)]
        shuffle(items)
        container = _Container(items)

        sort_items_in_order(
            container.items,
            key=lambda item: item.key,
            insert_before=container.insert_before,
            insert_after=container.insert_after,
        )

        count = container.apply()
        self.assertEqual(sorted(items, key=lambda item: item.key), container.items)
        self.assertGreater(count, 0)


if __name__ == "__main__":
    unittest.main()
