"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import argparse
import re
from importlib.util import find_spec
from pathlib import Path

from md2conf.__main__ import PositionalOnlyHelpFormatter, get_help


class DocumentationHelpFormatter(PositionalOnlyHelpFormatter):
    """
    A custom help formatter for generating documentation.

    It ensures that the output is suitable for inclusion in README.md by:
    - Increasing the width to prevent line wrapping.
    - Removing redundant metavariables for options with short flags.
    """

    def __init__(self, *args, **kwargs):
        kwargs["width"] = 1000
        super().__init__(*args, **kwargs)

    def _format_action_invocation(self, action: argparse.Action) -> str:
        """
        Formats the option flags and metavariables.

        If both short and long flags are present, the metavariable is only
        shown once after the last flag.
        """
        if action.option_strings and action.nargs != 0:
            # remove redundant metavariables for options with short flags
            # e.g., -u USERNAME, --username USERNAME -> -u, --username USERNAME
            parts = action.option_strings[:-1]
            default = self._get_default_metavar_for_optional(action)
            args_string = self._format_args(action, default)
            parts.append(f"{action.option_strings[-1]} {args_string}")
            return ", ".join(parts)
        return super()._format_action_invocation(action)


parser = argparse.ArgumentParser()
parser.add_argument(
    "--check",
    action="store_true",
    default=False,
    help="verify if documentation is up-to-date and raise an error when changes are identified",
)
args = parser.parse_args()

# update README.md
help_text = get_help(formatter_class=DocumentationHelpFormatter)
readme_path = Path(__file__).parent / "README.md"
with open(readme_path, "r") as input_file:
    input_content = input_file.read()
output_content, count = re.subn(
    r"^```console\n\$ python3 -m md2conf --help\n.*?^```$",
    f"```console\n$ python3 -m md2conf --help\n{help_text}```",
    input_content,
    count=1,
    flags=re.DOTALL | re.MULTILINE,
)
if count != 1:
    raise ValueError("missing placeholder for console output")
if args.check:
    if input_content != output_content:
        raise ValueError(f"outdated file: {readme_path}")
else:
    with open(Path(__file__).parent / "README.md", "w") as output_file:
        output_file.write(output_content)

# generate code documentation
if find_spec("markdown_doc") is not None:
    from markdown_doc.generator import generate_markdown
    from markdown_doc.import_util import import_modules

    root_path = Path(__file__).parent
    scan_path = root_path / "md2conf"
    out_dir = root_path / "docs"
    modules = import_modules(root_path, scan_path)
    generate_markdown(modules, out_dir)
