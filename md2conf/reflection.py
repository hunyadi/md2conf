"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from types import NoneType, UnionType
from typing import Any, Literal, NewType, Union, get_args, get_origin, get_type_hints


def get_nested_types(items: Sequence[Any]) -> set[NewType | type[Any]]:
    "Returns a set of types that are directly or indirectly referenced by any of the specified items."

    tps: set[NewType | type[Any]] = set()
    for item in items:
        tps.update(_get_nested_types(item))
    return tps


def _get_nested_types(tp: Any) -> set[NewType | type[Any]]:
    tps: set[NewType | type[Any]] = set()
    if tp is not None and tp is not NoneType:
        origin = get_origin(tp)
        if origin is list:
            (item_type,) = get_args(tp)
            tps.update(_get_nested_types(item_type))
        elif origin is dict:
            key_type, value_type = get_args(tp)
            tps.update(_get_nested_types(key_type))
            tps.update(_get_nested_types(value_type))
        elif origin is set:
            (elem_type,) = get_args(tp)
            tps.update(_get_nested_types(elem_type))
        elif origin is UnionType or origin is Union:
            for union_arg in get_args(tp):
                tps.update(_get_nested_types(union_arg))
        elif isinstance(tp, (NewType, type)):
            tps.add(tp)
            if is_dataclass(tp):
                for field in fields(tp):
                    tps.update(_get_nested_types(field.type))
            elif isinstance(tp, type):  # required to please static type checkers
                for field_type in get_type_hints(tp).values():
                    tps.update(_get_nested_types(field_type))
    return tps


def format_initializer(tp: Any) -> str:
    "Prints an initialization value for a type."

    origin = get_origin(tp)
    if tp is None or tp is NoneType:
        return "None"
    elif origin is list:
        (item_type,) = get_args(tp)
        return f"[{format_initializer(item_type)}]"
    elif origin is dict:
        key_type, value_type = get_args(tp)
        return f"{{{format_initializer(key_type)}: {format_initializer(value_type)}}}"
    elif origin is set:
        (elem_type,) = get_args(tp)
        return f"[{format_initializer(elem_type)}]"
    elif origin is Literal:
        return " or ".join(repr(arg) for arg in get_args(tp))
    elif origin is UnionType or origin is Union:
        return " or ".join(format_initializer(arg) for arg in get_args(tp))
    elif isinstance(tp, (NewType, type)):
        return f"{tp.__name__}()"  # type: ignore[union-attr]
    else:
        return "..."
