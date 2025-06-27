"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import sys

if sys.version_info >= (3, 12):
    from typing import override as override  # noqa: F401
else:
    from typing_extensions import override as override  # noqa: F401

if sys.version_info >= (3, 12):
    from pathlib import Path

    def path_relative_to(destination: Path, origin: Path) -> Path:
        return destination.relative_to(origin, walk_up=True)

else:
    import os.path
    from pathlib import Path

    def path_relative_to(destination: Path, origin: Path) -> Path:
        return Path(os.path.relpath(destination, start=origin))
