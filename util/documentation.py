"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import argparse
import os
import re
from collections.abc import Sequence
from dataclasses import fields, is_dataclass
from importlib.util import find_spec
from io import StringIO
from pathlib import Path
from typing import Any, NewType, get_type_hints

from md2conf.__main__ import get_help
from md2conf.api import ConfluenceAPI
from md2conf.environment import ConnectionProperties
from md2conf.options import ProcessorOptions
from md2conf.publisher import Publisher
from md2conf.reflection import format_initializer, get_nested_types


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


def update_console(text: str) -> str:
    "Updates the console output section in `README.md`."

    output, count = re.subn(
        r"^```console\n\$ python3 -m md2conf --help\n.*?^```$",
        f"```console\n$ python3 -m md2conf --help\n{help_text}```",
        text,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )
    if count != 1:
        raise ValueError("missing placeholder for console output")
    return output


def update_python(text: str) -> str:
    "Updates the Python sample code section in `README.md`."

    tps: set[NewType | type[Any]] = {ConfluenceAPI, Publisher}
    tps.update(get_nested_types([ConnectionProperties, ProcessorOptions]))

    python_code = f"""
{get_imports(list(tps))}
properties = {format_dataclass(ConnectionProperties)}
options = {format_dataclass(ProcessorOptions)}
with {ConfluenceAPI.__name__}(properties) as api:
    {Publisher.__name__}(api, options).process(mdpath)
"""

    output, count = re.subn(
        r"^```python\n.*?^```$",
        f"```python{python_code}```",
        text,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )
    if count != 1:
        raise ValueError("missing placeholder for Python code")
    return output


def format_dataclass(tp: Any, indent: str = "") -> str:
    "Prints sample code to initialize a data-class with all of its fields."

    if not isinstance(tp, type):
        raise TypeError("unrecognized type")

    s = StringIO()
    print(f"{tp.__name__}(", file=s)
    field_indent = indent + "    "
    if is_dataclass(tp):
        for field in fields(tp):
            s.write(f"{field_indent}{field.name}=")
            if is_dataclass(field.type):
                s.write(format_dataclass(field.type, indent=field_indent))
            else:
                s.write(format_initializer(field.type))
            print(",", file=s)
    elif isinstance(tp, type):
        for field_name, field_type in get_type_hints(tp).items():
            s.write(f"{field_indent}{field_name}={format_initializer(field_type)}")
            print(",", file=s)

    s.write(f"{indent})")
    return s.getvalue()


def get_imports(tps: Sequence[NewType | type[Any]]) -> str:
    "Returns a list of `import` statements to bring the specified classes into scope."

    s = StringIO()
    for module in sorted(list(set(tp.__module__ for tp in tps if tp.__module__ != "builtins"))):
        items = sorted(tp.__name__ for tp in tps if tp.__module__ == module)  # type: ignore[union-attr]
        if not items:
            continue
        print(f"from {module} import {', '.join(name for name in items)}", file=s)
    return s.getvalue()


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

# read README.md
os.environ["COLUMNS"] = "160"  # ensures consistent column width across platforms
help_text = patch_help(get_help())
readme_path = root_path / "README.md"
with open(readme_path, "r") as input_file:
    input_content = input_file.read()

# update README.md
text = input_content
text = update_console(text)
text = update_python(text)
output_content = text

# write README.md
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
