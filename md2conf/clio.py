"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from argparse import ArgumentParser
from dataclasses import MISSING, Field, dataclass, fields, is_dataclass
from typing import Any, Literal, TypeVar, get_args, get_origin

from .compatibility import LiteralString


class BaseOption:
    pass


@dataclass
class BooleanOption(BaseOption):
    true_text: LiteralString
    false_text: LiteralString


def boolean_option(true_text: LiteralString, false_text: LiteralString) -> dict[str, Any]:
    return {BaseOption.__name__: BooleanOption(true_text, false_text)}


@dataclass
class ChoiceOption(BaseOption):
    text: LiteralString


def choice_option(text: LiteralString) -> dict[str, Any]:
    return {BaseOption.__name__: ChoiceOption(text)}


T = TypeVar("T")


def _get_metadata(field: Field[Any], tp: type[T]) -> T | None:
    attrs = field.metadata.get(BaseOption.__name__)
    if attrs is None:
        return None
    elif isinstance(attrs, tp):
        return attrs
    else:
        raise TypeError(f"expected: {tp.__name__}; got: {type(attrs).__name__}")


def _add_field_as_argument(parser: ArgumentParser, field: Field[Any]) -> None:
    arg_name = field.name.replace("_", "-")
    if field.type is bool:
        bool_opt = _get_metadata(field, BooleanOption)
        if bool_opt is None:
            return
        true_text = bool_opt.true_text
        if field.default is True:
            true_text += " (default)"
        parser.add_argument(
            f"--{arg_name}",
            dest=field.name,
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
            f"--{inverse_arg_name}",
            dest=field.name,
            action="store_false",
            help=false_text,
        )
        return

    origin = get_origin(field.type)
    if origin is Literal:
        choice_opt = _get_metadata(field, ChoiceOption)
        if choice_opt is None:
            return
        choice_text = choice_opt.text
        if field.default is not MISSING:
            choice_text += f" (default: {field.default!s})"
        parser.add_argument(
            f"--{arg_name}",
            dest=field.name,
            choices=get_args(field.type),
            default=field.default,
            help=choice_text,
        )


def add_arguments(parser: ArgumentParser, options: type[Any]) -> None:
    if is_dataclass(options):
        for field in fields(options):
            _add_field_as_argument(parser, field)
