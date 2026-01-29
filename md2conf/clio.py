"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from argparse import ArgumentParser, Namespace
from dataclasses import MISSING, Field, dataclass, fields, is_dataclass
from types import NoneType, UnionType
from typing import Any, Literal, TypeVar, cast, get_args, get_origin

from .compatibility import LiteralString


class BaseOption:
    @staticmethod
    def field_name() -> str:
        return "argument"


@dataclass
class BooleanOption(BaseOption):
    true_text: LiteralString
    false_text: LiteralString


def boolean_option(true_text: LiteralString, false_text: LiteralString) -> dict[str, Any]:
    "Identifies a command-line argument as a boolean (on/off) flag."

    return {BaseOption.field_name(): BooleanOption(true_text, false_text)}


@dataclass
class ValueOption(BaseOption):
    text: LiteralString


def value_option(text: LiteralString) -> dict[str, Any]:
    "Identifies a command-line argument as an option that assigns a value."

    return {BaseOption.field_name(): ValueOption(text)}


class CompositeOption(BaseOption):
    pass


def composite_option() -> dict[str, Any]:
    "Identifies a command-line argument as a data-class that needs to be unnested."

    return {BaseOption.field_name(): CompositeOption()}


T = TypeVar("T")


def _has_metadata(field: Field[Any]) -> bool:
    return field.metadata.get(BaseOption.field_name()) is not None


def _get_metadata(field: Field[Any], tp: type[T]) -> T | None:
    attrs = field.metadata.get(BaseOption.field_name())
    if attrs is None:
        return None
    elif isinstance(attrs, tp):
        return attrs
    else:
        raise TypeError(f"expected: {tp.__name__}; got: {type(attrs).__name__}")


def _add_field_as_argument(parser: ArgumentParser, field: Field[Any], prefixes: tuple[str, ...]) -> None:
    arg_name = field.name.replace("_", "-")
    if field.type is bool:
        bool_opt = _get_metadata(field, BooleanOption)
        if bool_opt is None:
            return
        true_text = bool_opt.true_text
        if field.default is True:
            true_text += " (default)"
        parser.add_argument(
            f"--{'-'.join((*prefixes, arg_name))}",
            dest="_".join((*prefixes, field.name)),
            action="store_true",
            default=field.default,
            help=true_text,
        )
        if arg_name.startswith("skip-"):
            inverse_arg_name = "keep-" + arg_name.removeprefix("skip-")
        elif arg_name.startswith("keep-"):
            inverse_arg_name = "skip-" + arg_name.removeprefix("keep-")
        else:
            inverse_arg_name = f"no-{arg_name}"
        false_text = bool_opt.false_text
        if field.default is False:
            false_text += " (default)"
        parser.add_argument(
            f"--{'-'.join((*prefixes, inverse_arg_name))}",
            dest="_".join((*prefixes, field.name)),
            action="store_false",
            help=false_text,
        )
        return

    origin = get_origin(field.type)
    if origin is Literal:
        value_opt = _get_metadata(field, ValueOption)
        if value_opt is None:
            return
        value_text = value_opt.text
        if field.default is not MISSING and field.default is not None:
            value_text += f" (default: {field.default!s})"
        parser.add_argument(
            f"--{'-'.join((*prefixes, arg_name))}",
            dest="_".join((*prefixes, field.name)),
            choices=get_args(field.type),
            default=field.default,
            help=value_text,
        )

    elif origin is UnionType:
        union_types = list(get_args(field.type))
        if len(union_types) != 2 or NoneType not in union_types:
            raise TypeError(f"expected: `T` or `T | None` as argument type; got: {field.type}")
        union_types.remove(NoneType)
        required_type = union_types.pop()

        value_opt = _get_metadata(field, ValueOption)
        if value_opt is None:
            return
        value_text = value_opt.text
        if field.default is not MISSING and field.default is not None:
            value_text += f" (default: {field.default!s})"
        parser.add_argument(
            f"--{'-'.join((*prefixes, arg_name))}",
            dest="_".join((*prefixes, field.name)),
            default=field.default,
            type=required_type,
            help=value_text,
        )

    elif isinstance(field.type, type):
        if not hasattr(field.type, "__dataclass_fields__"):
            raise TypeError(f"expected: data-class as composite argument; got: {field.type}")
        composite_opt = _get_metadata(field, CompositeOption)
        if composite_opt is None:
            return

        _add_arguments(parser, field.type, (*prefixes, field.name))

    elif _has_metadata(field):
        raise TypeError(f"expected: known argument type; got: {field.type}")


def _add_arguments(parser: ArgumentParser, options_type: type[Any], prefixes: tuple[str, ...]) -> None:
    if is_dataclass(options_type):
        for field in fields(options_type):
            _add_field_as_argument(parser, field, prefixes)


def add_arguments(parser: ArgumentParser, options_type: type[Any]) -> None:
    """
    Adds arguments to a command-line argument parser.

    :param parser: A command-line argument parser.
    :param options_type: A data-class type that encapsulates configuration options.
    """

    _add_arguments(parser, options_type, ())


def _get_options(args: Namespace, options_type: type[T], prefixes: tuple[str, ...]) -> T:
    params: dict[str, Any] = {}
    if is_dataclass(options_type):
        for field in fields(options_type):
            if isinstance(field.type, type) and is_dataclass(field.type):
                params[field.name] = _get_options(args, field.type, (*prefixes, field.name))
            else:
                params[field.name] = getattr(args, "_".join((*prefixes, field.name)))
    return options_type(**params)


def get_options(args: Namespace, options_type: type[T]) -> T:
    """
    Extracts configuration options from command-line arguments acquired by an argument parser.

    :param args: Arguments acquired by a command-line argument parser.
    :param options_type: A data-class type that encapsulates configuration options.
    :returns: Configuration options as a data-class instance.
    """

    if not is_dataclass(options_type):
        raise TypeError(f"expected: data-class as argument target; got: {type(options_type).__name__}")
    return _get_options(args, cast(type[T], options_type), ())
