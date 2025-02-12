"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import os.path
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class Entry:
    """
    Represents a file or directory entry.

    :param name: Name of the file-system entry.
    :param is_dir: True if the entry is a directory.
    """

    name: str
    is_dir: bool


@dataclass
class MatcherOptions:
    """
    Options for checking against a list of exclude/include patterns.

    :param source: File name to read exclusion rules from.
    :param extension: Extension to narrow down search to.
    """

    source: str
    extension: Optional[str] = None

    def __post_init__(self) -> None:
        if self.extension is not None and not self.extension.startswith("."):
            self.extension = f".{self.extension}"


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

    def extension_matches(self, name: str) -> bool:
        "True if the file name has the expected extension."

        return self.options.extension is None or name.endswith(self.options.extension)

    def is_excluded(self, name: str, is_dir: bool) -> bool:
        """
        True if the file or directory name matches any of the exclusion patterns.

        :param name: Name to match against the rule-set.
        :param is_dir: Whether the name identifies a directory.
        :returns: True if the name matches at least one of the exclusion patterns.
        """

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

    def is_included(self, name: str, is_dir: bool) -> bool:
        """
        True if the file or directory name matches none of the exclusion patterns.

        :param name: Name to match against the rule-set.
        :param is_dir: Whether the name identifies a directory.
        :returns: True if the name doesn't match any of the exclusion patterns.
        """

        return not self.is_excluded(name, is_dir)

    def filter(self, items: Iterable[Entry]) -> list[Entry]:
        """
        Returns only those elements from the input that don't match any of the exclusion rules.

        :param items: A list of names to filter.
        :returns: A filtered list of names that didn't match any of the exclusion rules.
        """

        return [item for item in items if self.is_included(item.name, item.is_dir)]

    def scandir(self, path: Path) -> list[Entry]:
        """
        Returns only those entries in a directory whose name doesn't match any of the exclusion rules.

        :param path: Directory to scan.
        :returns: A filtered list of entries whose name didn't match any of the exclusion rules.
        """

        return self.filter(
            Entry(entry.name, entry.is_dir()) for entry in os.scandir(path)
        )
