"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import dataclasses
import sys
from typing import Any, ClassVar, Protocol, TypeVar

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


class DataclassInstance(Protocol):
    __dataclass_fields__: ClassVar[dict[str, dataclasses.Field[Any]]]


D = TypeVar("D", bound=DataclassInstance)


def merged(target: D, source: D) -> D:
    """
    Implements nullish coalescing assignment on each field of a data-class.

    Iterates over each field of the data-class, and evaluates the right operand and assigns it to the left only if
    the left operand is `None`. Always creates and returns a new data-class instance.
    """

    updates = {f.name: getattr(source, f.name, None) for f in dataclasses.fields(target) if getattr(target, f.name, None) is None}
    return dataclasses.replace(target, **updates)
