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
    composite: CompositeOption = field(default_factory=CompositeOption, metadata=composite_option())
    bool_flag: bool = field(
        default=False,
        metadata=boolean_option(
            "Help text for the case when flag is enabled.",
            "Help text for the case when flag is disabled.",
        ),
    )
    untracked: str = "untracked"


class TestCommandLine(unittest.TestCase):
    def test_cli(self) -> None:
        parser = ArgumentParser()
        add_arguments(parser, Options)
        args = parser.parse_args(["--composite-int-val=23", "--composite-optional-int-val=45", "--composite-literal-val=three", "--bool-flag"])

        s = StringIO()
        parser.print_help(file=s)
        text = s.getvalue()
        self.assertIn("usage:", text)
        self.assertIn("options:", text)
        self.assertIn("--bool-flag", text)
        self.assertIn("--no-bool-flag", text)
        self.assertIn("--composite-int-val INT", text)

        options = get_options(args, Options)
        self.assertTrue(options.bool_flag)
        self.assertEqual(options.composite.int_val, 23)
        self.assertEqual(options.composite.optional_int_val, 45)
        self.assertEqual(options.composite.literal_val, "three")


if __name__ == "__main__":
    unittest.main()
