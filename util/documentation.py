"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import argparse
import os
import re
from importlib.util import find_spec
from pathlib import Path

from md2conf.__main__ import get_help


def patch_help(help_text: str) -> str:
    "Updates the help text returned by `argparse` to be consistent across Python versions."

    # replace verbose options like `-u USERNAME, --username USERNAME` with their compact equivalent `-u, --username USERNAME`
    # use vertical tab character `\v` as a marker to indicate where re-alignment is necessary
    repl_text, count = re.subn(r"-(?P<short>[-a-z]+) (?P<arg>[_A-Z]+|\{[^{}]+\}), --(?P<long>[-a-z]+) (?P=arg)", r"-\g<short>, --\g<long> \g<arg>\v", help_text)

    if count > 0:
        # determine column index at which help description is aligned
        re_align = re.search(r"^(?P<indent>.*)show this help message and exit$", help_text, flags=re.MULTILINE)
        if re_align is None:
            return help_text
        indent = len(re_align.group("indent"))

        def _align(m: re.Match[str]) -> str:
            option: str = m.group("option")
            description: str = m.group("description")
            if len(option) + 2 > indent:
                # spans across lines
                return option + "\n" + " " * indent + description
            else:
                # same line
                return option + " " * (indent - len(option)) + description

        # re-align text as necessary
        return re.sub(r"^(?P<option>.+)\v\n? *(?P<description>.+)$", _align, repl_text, flags=re.MULTILINE)
    else:
        return help_text


class Arguments(argparse.Namespace):
    check: bool


parser = argparse.ArgumentParser()
parser.add_argument(
    "--check",
    action="store_true",
    default=False,
    help="verify if documentation is up-to-date and raise an error when changes are identified",
)
args = Arguments()
parser.parse_args(namespace=args)

# locate repository root
root_path = Path(__file__).parent.parent

# update README.md
os.environ["COLUMNS"] = "160"  # ensures consistent column width across platforms
help_text = patch_help(get_help())
readme_path = root_path / "README.md"
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
    with open(root_path / "README.md", "w") as output_file:
        output_file.write(output_content)

# generate code documentation
if find_spec("markdown_doc") is not None:
    from markdown_doc.generator import generate_markdown
    from markdown_doc.import_util import import_modules

    scan_path = root_path / "md2conf"
    out_dir = root_path / "docs"
    modules = import_modules(root_path, scan_path)
    generate_markdown(modules, out_dir)
