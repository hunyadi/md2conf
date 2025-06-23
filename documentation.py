"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

from importlib.util import find_spec
from pathlib import Path

if find_spec("markdown_doc") is not None:
    from markdown_doc.generator import generate_markdown
    from markdown_doc.import_util import import_modules

    root_path = Path(__file__).parent
    scan_path = root_path / "md2conf"
    out_dir = root_path / "docs"
    modules = import_modules(root_path, scan_path)
    generate_markdown(modules, out_dir)
