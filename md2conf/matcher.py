"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import os.path
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, final, overload


@dataclass(frozen=True, eq=True)
class _BaseEntry:
    """
    Represents a file or directory entry.

    Entries are primarily sorted alphabetically case-insensitive.
    When two items are equal case-insensitive, conflicting items are put in case-sensitive order.

    :param name: Name of the file-system entry.
    """

    name: str

    @property
    def lower_name(self) -> str:
        return self.name.lower()

    def __lt__(self, other: "_BaseEntry") -> bool:
        return (self.lower_name, self.name) < (other.lower_name, other.name)

    def __le__(self, other: "_BaseEntry") -> bool:
        return (self.lower_name, self.name) <= (other.lower_name, other.name)

    def __ge__(self, other: "_BaseEntry") -> bool:
        return (self.lower_name, self.name) >= (other.lower_name, other.name)

    def __gt__(self, other: "_BaseEntry") -> bool:
        return (self.lower_name, self.name) > (other.lower_name, other.name)


@final
class FileEntry(_BaseEntry):
    pass


@final
class DirectoryEntry(_BaseEntry):
    pass


@dataclass(frozen=True, eq=True)
class Entry:
    """
    Represents a file or directory entry.

    When sorted, directories come before files and items are primarily arranged in alphabetical order case-insensitive.
    When two items are equal case-insensitive, conflicting items are put in case-sensitive order.

    :param name: Name of the file-system entry to match against the rule-set.
    :param is_dir: True if the entry is a directory.
    """

    name: str
    is_dir: bool

    @property
    def lower_name(self) -> str:
        return self.name.lower()

    def __lt__(self, other: "Entry") -> bool:
        return (not self.is_dir, self.lower_name, self.name) < (not other.is_dir, other.lower_name, other.name)

    def __le__(self, other: "Entry") -> bool:
        return (not self.is_dir, self.lower_name, self.name) <= (not other.is_dir, other.lower_name, other.name)

    def __ge__(self, other: "Entry") -> bool:
        return (not self.is_dir, self.lower_name, self.name) >= (not other.is_dir, other.lower_name, other.name)

    def __gt__(self, other: "Entry") -> bool:
        return (not self.is_dir, self.lower_name, self.name) > (not other.is_dir, other.lower_name, other.name)


@dataclass
class MatcherOptions:
    """
    Options for checking against a list of exclude/include patterns.

    :param source: File name to read exclusion rules from.
    :param extension: Extension to narrow down search to.
    """

    source: str
    extension: str | None = None

    def __post_init__(self) -> None:
        if self.extension is not None and not self.extension.startswith("."):
            self.extension = f".{self.extension}"


def _entry_name_dir(entry: Entry | os.DirEntry[str]) -> tuple[str, bool]:
    if isinstance(entry, Entry):
        return entry.name, entry.is_dir
    else:
        return entry.name, entry.is_dir()


class Matcher:
    "Compares file and directory names against a list of exclude/include patterns."

    options: MatcherOptions
    rules: list[str]

    def __init__(self, options: MatcherOptions, directory: Path) -> None:
        self.options = options
        if os.path.exists(directory / options.source):
            with open(directory / options.source, "r") as f:
                rules = f.read().splitlines()
            self.rules = [rule for rule in rules if rule and not rule.startswith("#")]
        else:
            self.rules = []

        for rule in self.rules:
            if "/" in rule or os.path.sep in rule:
                raise ValueError(f"nested matching not supported: {rule}")

    def extension_matches(self, name: str) -> bool:
        "True if the file name has the expected extension."

        return self.options.extension is None or name.endswith(self.options.extension)

    @overload
    def is_excluded(self, entry: Entry) -> bool:
        """
        True if the file or directory name matches any of the exclusion patterns.

        :param entry: A data-class object.
        :returns: True if the name matches at least one of the exclusion patterns.
        """

        ...

    @overload
    def is_excluded(self, entry: os.DirEntry[str]) -> bool:
        """
        True if the file or directory name matches any of the exclusion patterns.

        :param entry: An object returned by `scandir`.
        :returns: True if the name matches at least one of the exclusion patterns.
        """

        ...

    def is_excluded(self, entry: Entry | os.DirEntry[str]) -> bool:
        name, is_dir = _entry_name_dir(entry)

        # skip hidden files and directories
        if name.startswith("."):
            return True

        # match extension for regular files
        if not is_dir and not self.extension_matches(name):
            return True

        for rule in self.rules:
            if fnmatch(name, rule):
                return True
        else:
            return False

    @overload
    def is_included(self, entry: Entry) -> bool:
        """
        True if the file or directory name matches none of the exclusion patterns.

        :param entry: A data-class object.
        :returns: True if the name doesn't match any of the exclusion patterns.
        """
        ...

    @overload
    def is_included(self, entry: os.DirEntry[str]) -> bool:
        """
        True if the file or directory name matches none of the exclusion patterns.

        :param entry: An object returned by `scandir`.
        :returns: True if the name doesn't match any of the exclusion patterns.
        """
        ...

    def is_included(self, entry: Entry | os.DirEntry[str]) -> bool:
        return not self.is_excluded(entry)

    def filter(self, entries: Iterable[Entry]) -> list[Entry]:
        """
        Returns only those elements from the input that don't match any of the exclusion rules.

        :param entries: A list of names to filter.
        :returns: A filtered list of names that didn't match any of the exclusion rules.
        """

        return sorted(entry for entry in entries if self.is_included(entry))

    def listing(self, path: Path) -> list[Entry]:
        """
        Returns only those entries in a directory whose name doesn't match any of the exclusion rules.

        :param path: Directory to scan.
        :returns: A filtered list of entries whose name didn't match any of the exclusion rules.
        """

        return self.filter(Entry(entry.name, entry.is_dir()) for entry in os.scandir(path))
