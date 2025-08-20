"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import argparse
import re
from importlib.util import find_spec
from pathlib import Path

from md2conf.__main__ import get_help

parser = argparse.ArgumentParser()
parser.add_argument(
    "--check",
    action="store_true",
    default=False,
    help="verify if documentation is up-to-date and raise an error when changes are identified",
)
args = parser.parse_args()

# update README.md
help_text = get_help()
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
