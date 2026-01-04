"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import copy
import dataclasses
from typing import Any, ClassVar, Protocol, TypeVar


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]


D = TypeVar("D", bound=DataclassInstance)


def coalesce(target: D, source: D) -> D:
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
                updates[field.name] = copy.deepcopy(source_field)
        elif dataclasses.is_dataclass(field.type):
            if source_field is not None:
                updates[field.name] = coalesce(target_field, source_field)

    return dataclasses.replace(target, **updates)
