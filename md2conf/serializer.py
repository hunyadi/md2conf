"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from typing import TypeVar

from cattrs.preconf.orjson import make_converter  # spellchecker:disable-line

JsonType = None | bool | int | float | str | dict[str, "JsonType"] | list["JsonType"]
JsonComposite = dict[str, "JsonType"] | list["JsonType"]

T = TypeVar("T")


_converter = make_converter(forbid_extra_keys=False)


@_converter.register_structure_hook
def json_type_structure_hook(value: JsonType, cls: type[JsonType]) -> JsonType:
    return value


@_converter.register_structure_hook
def json_composite_structure_hook(value: JsonComposite, cls: type[JsonComposite]) -> JsonComposite:
    return value


def json_to_object(typ: type[T], data: JsonType) -> T:
    """
    Converts a raw JSON object to a structured object, validating input data.

    :param typ: Target structured type.
    :param data: Source data as a JSON object.
    :returns: A valid object instance of the expected type.
    """

    return _converter.structure(data, typ)


def object_to_json_payload(data: object) -> bytes:
    """
    Converts a structured object to a JSON string encoded in UTF-8.

    :param data: Object to convert to a JSON string.
    :returns: JSON string encoded in UTF-8.
    """

    return _converter.dumps(data)
