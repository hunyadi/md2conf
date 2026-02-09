"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
from argparse import ArgumentParser, Namespace
from dataclasses import MISSING, Field, dataclass, fields, is_dataclass
from types import NoneType, UnionType
from typing import Any, Literal, TypeVar, Union, cast, get_args, get_origin

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


@dataclass
class NullableOption(BaseOption):
    value_text: LiteralString
    omit_text: LiteralString


def nullable_option(value_text: LiteralString, omit_text: LiteralString) -> dict[str, Any]:
    "Identifies a command-line argument as an option that sets or un-sets a value."

    return {BaseOption.field_name(): NullableOption(value_text, omit_text)}


@dataclass
class CompositeOption(BaseOption):
    """
    Determines how a data-class populates command-line arguments.

    :param flatten: True if members of the data-class are populated as if they were defined in the encapsulating class.
    """

    flatten: bool


def composite_option(flatten: bool = False) -> dict[str, Any]:
    "Identifies a command-line argument as a data-class that needs to be unnested."

    return {BaseOption.field_name(): CompositeOption(flatten)}


T = TypeVar("T")


def _get_metadata(field: Field[Any], tp: type[T]) -> T:
    attrs = field.metadata.get(BaseOption.field_name())
    if attrs is None:
        raise TypeError(f"expected: object of type {tp.__name__}; got: None")
    if not isinstance(attrs, tp):
        raise TypeError(f"expected: object of type {tp.__name__}; got: {attrs}")
    return attrs


# inserts underscore before capital letters that follow lowercase letters or digits
_TITLE_TO_SNAKE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def title_to_upper(name: str) -> str:
    snake = _TITLE_TO_SNAKE.sub("_", name)
    return snake.upper()


class _OptionTreeVisitor:
    "Adds arguments to a command-line argument parser by recursively visiting fields of a composite type."

    parser: ArgumentParser
    prefixes: list[str]

    def __init__(self, parser: ArgumentParser) -> None:
        self.parser = parser
        self.prefixes = []

    def _get_arg_name(self, arg_name: str) -> str:
        return f"--{'-'.join([*self.prefixes, arg_name])}"

    def _get_field_name(self, field_name: str) -> str:
        return "_".join([*self.prefixes, field_name])

    def _add_boolean_field(self, field: Field[Any]) -> None:
        arg_name = field.name.replace("_", "-")
        bool_opt = _get_metadata(field, BooleanOption)
        true_text = bool_opt.true_text
        if field.default is True:
            true_text += " (default)"
        self.parser.add_argument(
            self._get_arg_name(arg_name),
            dest=self._get_field_name(field.name),
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
        self.parser.add_argument(
            self._get_arg_name(inverse_arg_name),
            dest=self._get_field_name(field.name),
            action="store_false",
            help=false_text,
        )

    def _add_value_field(self, field: Field[Any], field_type: Any) -> None:
        arg_name = field.name.replace("_", "-")
        value_opt = _get_metadata(field, ValueOption)
        help_text = value_opt.text
        if field.default is not MISSING and field.default is not None:
            help_text += f" (default: {field.default!s})"
        if isinstance(field_type, type):
            metavar = title_to_upper(field_type.__name__)
        else:
            metavar = None
        self.parser.add_argument(
            self._get_arg_name(arg_name),
            dest=self._get_field_name(field.name),
            default=field.default,
            type=field_type,
            help=help_text,
            metavar=metavar,
        )

    def _add_nullable_field(self, field: Field[Any], field_type: Any) -> None:
        arg_name = field.name.replace("_", "-")
        value_opt = _get_metadata(field, NullableOption)
        value_help_text = value_opt.value_text
        if field.default is not MISSING and field.default is not None:
            value_help_text += f" (default: {field.default!s})"
        if isinstance(field_type, type):
            metavar = title_to_upper(field_type.__name__)
        else:
            metavar = None
        self.parser.add_argument(
            self._get_arg_name(arg_name),
            dest=self._get_field_name(field.name),
            default=field.default,
            type=field_type,
            help=value_help_text,
            metavar=metavar,
        )
        omit_help_text = value_opt.omit_text
        if field.default is not MISSING and field.default is None:
            omit_help_text += " (default)"
        self.parser.add_argument(
            self._get_arg_name(f"no-{arg_name}"),
            dest=self._get_field_name(field.name),
            action="store_const",
            const=None,
            help=omit_help_text,
        )

    def _add_composite_field(self, field: Field[Any], field_type: Any) -> None:
        arg_name = field.name.replace("_", "-")
        composite_opt = _get_metadata(field, CompositeOption)
        if not composite_opt.flatten:
            self.prefixes.append(arg_name)
        self.add_arguments(field_type)
        if not composite_opt.flatten:
            self.prefixes.pop()

    def _add_field_as_argument(self, field: Field[Any]) -> None:
        attrs = field.metadata.get(BaseOption.field_name())
        if attrs is None:
            return

        arg_name = field.name.replace("_", "-")
        if field.type is bool:
            self._add_boolean_field(field)
            return

        origin = get_origin(field.type)
        if origin is Literal:
            value_opt = _get_metadata(field, ValueOption)
            value_text = value_opt.text
            if field.default is not MISSING and field.default is not None:
                value_text += f" (default: {field.default!s})"
            self.parser.add_argument(
                self._get_arg_name(arg_name),
                dest=self._get_field_name(field.name),
                choices=get_args(field.type),
                default=field.default,
                help=value_text,
            )

        elif origin is Union or origin is UnionType:
            union_types = list(get_args(field.type))
            if len(union_types) != 2 or NoneType not in union_types:
                raise TypeError(f"expected: `T` or `T | None` as argument type; got: {field.type}")
            union_types.remove(NoneType)
            required_type = union_types.pop()

            match attrs:
                case ValueOption():
                    self._add_value_field(field, required_type)
                case NullableOption():
                    self._add_nullable_field(field, required_type)
                case None:
                    raise TypeError(f"expected: object of type {ValueOption.__name__} or {NullableOption.__name__}; got: None")
                case _:
                    raise TypeError(f"expected: object of type {ValueOption.__name__} or {NullableOption.__name__}; got: {attrs}")

        elif isinstance(field.type, type):
            if hasattr(field.type, "__dataclass_fields__"):
                self._add_composite_field(field, field.type)
            else:
                self._add_value_field(field, field.type)

        else:
            raise TypeError(f"expected: known argument type; got: {field.type}")

    def add_arguments(self, options_type: type[Any]) -> None:
        if is_dataclass(options_type):
            for field in fields(options_type):
                self._add_field_as_argument(field)


def add_arguments(parser: ArgumentParser, options_type: type[Any]) -> None:
    """
    Adds arguments to a command-line argument parser.

    :param parser: A command-line argument parser.
    :param options_type: A data-class type that encapsulates configuration options.
    """

    _OptionTreeVisitor(parser).add_arguments(options_type)


def _get_options(args: Namespace, options_type: type[T], prefixes: tuple[str, ...]) -> T:
    params: dict[str, Any] = {}
    if is_dataclass(options_type):  # always true, condition included for type checkers
        for field in fields(options_type):
            field_type = field.type
            field_prefixes = (*prefixes, field.name)
            attrs = field.metadata.get(BaseOption.field_name())
            match attrs:
                case BooleanOption() | ValueOption() | NullableOption():
                    field_param = getattr(args, "_".join(field_prefixes), MISSING)
                    if field_param is not MISSING:
                        params[field.name] = field_param
                case CompositeOption():
                    if not isinstance(field_type, type) or not is_dataclass(field_type):
                        raise TypeError(f"expected: data-class for {CompositeOption.__name__}; got: {field_type}")
                    nested_prefixes = prefixes if attrs.flatten else field_prefixes
                    params[field.name] = _get_options(args, field_type, nested_prefixes)
                case None:
                    continue
                case _:
                    raise TypeError(f"expected: command-line argument option; got: {attrs}")
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
