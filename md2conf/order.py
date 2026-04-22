"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from bisect import bisect_left
from collections.abc import Callable, Iterable, Sequence
from typing import Any, TypeVar

T = TypeVar("T")


def _longest_increasing_subsequence_indices(values: Sequence[int]) -> list[int]:
    "Returns the indices of a longest increasing subsequence in the specified sequence."

    if not values:
        return []

    tails: list[int] = []
    tails_indices: list[int] = []
    previous_indices = [-1] * len(values)

    for index, value in enumerate(values):
        pos = bisect_left(tails, value)

        if pos > 0:
            previous_indices[index] = tails_indices[pos - 1]

        if pos == len(tails):
            tails.append(value)
            tails_indices.append(index)
        else:
            tails[pos] = value
            tails_indices[pos] = index

    lis_indices: list[int] = []
    index = tails_indices[-1]
    while index >= 0:
        lis_indices.append(index)
        index = previous_indices[index]

    lis_indices.reverse()
    return lis_indices


def sort_items_in_order(items: Iterable[T], *, key: Callable[[T], Any], insert_before: Callable[[T, T], None], insert_after: Callable[[T, T], None]) -> None:
    """
    Reorders existing items using the minimum number of insert operations.

    The input sequence defines the current order in the container. The function computes the stable sorted order using
    the supplied key function, keeps the largest possible subsequence in place, and repositions the remaining items
    using exactly one insert operation per moved item.

    :param items: Existing items in their current container order.
    :param key: Sort key applied to each item.
    :param insert_before: Moves an existing item immediately before another item.
    :param insert_after: Moves an existing item immediately after another item.
    """

    original_items = list(items)
    item_count = len(original_items)
    if item_count < 2:
        return

    # stable target order, expressed as original indices
    keys = [key(item) for item in original_items]
    target_indices = sorted(range(item_count), key=keys.__getitem__)

    # rank[orig_index] = position in sorted order
    rank = [0] * item_count
    for sorted_position, original_index in enumerate(target_indices):
        rank[original_index] = sorted_position

    # items in the longest increasing subsequence can stay where they are
    keep_indices = set(_longest_increasing_subsequence_indices(rank))

    # for each position in target order, find the next kept item to the right
    next_keep_to_right: list[int | None] = [None] * item_count
    next_keep: int | None = None
    for sorted_position in range(item_count - 1, -1, -1):
        next_keep_to_right[sorted_position] = next_keep
        original_index = target_indices[sorted_position]
        if original_index in keep_indices:
            next_keep = original_index

    # rebuild the sorted order with exactly one insert call per moved item
    previous_item: T | None = None
    for sorted_position, original_index in enumerate(target_indices):
        item = original_items[original_index]

        if original_index in keep_indices:
            previous_item = item
            continue

        next_keep_index = next_keep_to_right[sorted_position]
        if next_keep_index is not None:
            insert_before(item, original_items[next_keep_index])
        elif previous_item is not None:
            insert_after(item, previous_item)
        else:
            raise RuntimeError("expected: at least one anchor item")

        previous_item = item
