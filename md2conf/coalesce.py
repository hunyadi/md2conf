"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import dataclasses
from copy import deepcopy
from typing import Any, ClassVar, Protocol, TypeVar

from .serializer import JsonType


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]


D = TypeVar("D", bound=DataclassInstance)


def coalesce_dataclass(target: D, source: D) -> D:
    """
    Implements nullish coalescing assignment on each field of a data-class.

    Iterates over each field of the data-class, and evaluates the right operand and assigns it to the left only if
    the left operand is `None`. Applies recursively when the field is a data-class.

    :returns: A newly created data-class instance.
    """

    updates: dict[str, Any] = {}
    for field in dataclasses.fields(target):
        target_field = getattr(target, field.name, None)
        source_field = getattr(source, field.name, None)

        if target_field is None:
            if source_field is not None:
                updates[field.name] = deepcopy(source_field)
        elif dataclasses.is_dataclass(field.type):
            if source_field is not None:
                updates[field.name] = coalesce_dataclass(target_field, source_field)

    return dataclasses.replace(target, **updates)


def coalesce_json(target: dict[str, JsonType] | None, source: dict[str, JsonType] | None) -> dict[str, JsonType] | None:
    """
    Recursively performs a nullish coalescing merge of source into target.

    * Missing keys in target are copied from source.
    * Keys with value None in target are replaced with source values.
    * Nested dictionaries are merged recursively.
    * Non-dictionary values are left unchanged unless they are `None`.

    :returns: A new merged dictionary (does not mutate inputs).
    """

    if source is None:
        return target
    if target is None:
        return source

    result = deepcopy(target)
    for key, source_value in source.items():
        if key not in result:
            result[key] = deepcopy(source_value)
        else:
            target_value = result[key]

            # if target value is `None` then replace
            if target_value is None:
                result[key] = deepcopy(source_value)

            # if both values are `dict` then recurse
            elif isinstance(target_value, dict) and isinstance(source_value, dict):
                result[key] = coalesce_json(target_value, source_value)

    return result
