"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import unittest
from argparse import ArgumentParser
from dataclasses import dataclass, field
from io import StringIO
from typing import Literal

from md2conf.clio import add_arguments, boolean_option, composite_option, get_options, value_option


@dataclass
class CompositeOption:
    int_val: int = field(default=12, metadata=value_option("Help text for integer option."))
    optional_int_val: int | None = field(default=None, metadata=value_option("Help text for integer option."))
    str_val: str = field(default="string", metadata=value_option("Help text for string option."))
    literal_val: Literal["one", "two", "three"] = field(
        default="two",
        metadata=value_option("Help text for choice option."),
    )
    untracked_val: str = "untracked"


@dataclass
class Options:
    bool_flag: bool = field(
        default=False,
        metadata=boolean_option(
            "Help text for the case when flag is enabled.",
            "Help text for the case when flag is disabled.",
        ),
    )
    untracked_value: str = "untracked"
    untracked_class: CompositeOption = field(default_factory=CompositeOption)


@dataclass
class NestedOptions(Options):
    nested: CompositeOption = field(default_factory=CompositeOption, metadata=composite_option())


@dataclass
class FlatOptions(Options):
    flat: CompositeOption = field(default_factory=CompositeOption, metadata=composite_option(flatten=True))


class TestCommandLine(unittest.TestCase):
    def test_hierarchical(self) -> None:
        parser = ArgumentParser()
        add_arguments(parser, NestedOptions)

        s = StringIO()
        parser.print_help(file=s)
        text = s.getvalue()
        self.assertIn("usage:", text)
        self.assertIn("options:", text)
        self.assertIn("--bool-flag", text)
        self.assertIn("--no-bool-flag", text)
        self.assertIn("--nested-int-val INT", text)

        args = parser.parse_args(["--nested-int-val=23", "--nested-optional-int-val=45", "--nested-str-val=text", "--nested-literal-val=three", "--bool-flag"])
        options = get_options(args, NestedOptions)

        self.assertTrue(options.bool_flag)
        self.assertEqual(options.nested.int_val, 23)
        self.assertEqual(options.nested.optional_int_val, 45)
        self.assertEqual(options.nested.str_val, "text")
        self.assertEqual(options.nested.literal_val, "three")
        self.assertEqual(options.nested.untracked_val, "untracked")

    def test_flat(self) -> None:
        parser = ArgumentParser()
        add_arguments(parser, FlatOptions)

        s = StringIO()
        parser.print_help(file=s)
        text = s.getvalue()
        self.assertIn("usage:", text)
        self.assertIn("options:", text)
        self.assertIn("--bool-flag", text)
        self.assertIn("--no-bool-flag", text)
        self.assertIn("--int-val INT", text)

        args = parser.parse_args(["--int-val=23", "--optional-int-val=45", "--str-val=text", "--literal-val=three", "--bool-flag"])
        options = get_options(args, FlatOptions)

        self.assertTrue(options.bool_flag)
        self.assertEqual(options.flat.int_val, 23)
        self.assertEqual(options.flat.optional_int_val, 45)
        self.assertEqual(options.flat.str_val, "text")
        self.assertEqual(options.flat.literal_val, "three")
        self.assertEqual(options.flat.untracked_val, "untracked")


if __name__ == "__main__":
    unittest.main()
