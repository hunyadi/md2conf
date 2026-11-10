"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
import sys
import unicodedata
from functools import lru_cache
from typing import Literal

# fmt: off
CategoryCode = Literal[
    "Cc", "Cf", "Cn", "Co", "Cs", "LC", "Ll", "Lm", "Lo", "Lt",
    "Lu", "Mc", "Me", "Mn", "Nd", "Nl", "No", "Pc", "Pd", "Pe",
    "Pf", "Pi", "Po", "Ps", "Sc", "Sk", "Sm", "So", "Zl", "Zp",
    "Zs",
]
# fmt: on


def to_unicode_escape(code: int) -> str:
    if code <= 0xFF:
        return rf"\x{code:02X}"
    elif code <= 0xFFFF:
        return rf"\u{code:04X}"
    else:
        return rf"\U{code:08X}"


def to_unicode_range(start: int, end: int) -> str:
    if start == end:
        return to_unicode_escape(start)
    else:
        return f"{to_unicode_escape(start)}-{to_unicode_escape(end)}"


def to_unicode_ranges(ranges: list[tuple[int, int]]) -> str:
    return "".join(to_unicode_range(start, end) for start, end in ranges)


def get_category_ranges(category_codes: set[CategoryCode]) -> list[tuple[int, int]]:
    """
    Finds all code points matching a 2-letter Unicode category and groups them into (start, end) tuples.

    :param category_codes: Set of 2-letter Unicode category codes to search for.
    """

    ranges: list[tuple[int, int]] = []
    range_start = None
    prev_code: int = 0

    # covers the entire code point space available in your Python build
    for code in range(sys.maxunicode + 1):  # spellchecker: disable-line
        if unicodedata.category(chr(code)) in category_codes:
            if range_start is None:
                range_start = code
            prev_code = code
        else:
            if range_start is not None:
                ranges.append((range_start, prev_code))
                range_start = None
                prev_code = 0

    # catch the last range if it extends to the end of the space
    if range_start is not None:
        ranges.append((range_start, prev_code))

    return ranges


def subtract_ranges(a: list[tuple[int, int]], b: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Computes the set difference of the integer values represented by two sets of inclusive ranges.

    Values covered by a range in `a` are retained unless they are also covered by a range in `b`. A range in `a` may
    be split when it partially overlaps a range in `b`. Ranges in `a` are processed independently, so overlapping
    output ranges are not merged.

    :param a: List of inclusive (start, end) ranges whose values are candidates for the result.
    :param b: List of inclusive (start, end) ranges whose values are removed from the result.
    :return: List of inclusive (start, end) ranges representing the difference.
    """

    if not a:
        return []

    if not b:
        return a

    # sort ranges for easier processing
    sorted_a = sorted(a)
    sorted_b = sorted(b)

    result: list[tuple[int, int]] = []

    for range_start, range_end in sorted_a:
        # track the current segment we're processing
        current_segments = [(range_start, range_end)]

        # subtract each excluded range from current segments
        for excl_start, excl_end in sorted_b:
            new_segments: list[tuple[int, int]] = []

            for seg_start, seg_end in current_segments:
                # if excluded range doesn't overlap with this segment, keep it
                if excl_end < seg_start or excl_start > seg_end:
                    new_segments.append((seg_start, seg_end))
                else:
                    # there is overlap, split the segment; keep the part before the excluded range
                    if seg_start < excl_start:
                        new_segments.append((seg_start, excl_start - 1))

                    # keep the part after the excluded range
                    if seg_end > excl_end:
                        new_segments.append((excl_end + 1, seg_end))

            current_segments = new_segments

        result.extend(current_segments)

    return result


@lru_cache(maxsize=1)
def get_symbol_matching_regex() -> re.Pattern[str]:
    """
    Creates a regex pattern for discarding punctuation, separators, non-alphabetic symbols, control and format characters.

    Identifies characters that should be removed when generating a slug.

    :return: A compiled regular expression pattern.
    """

    # items in the category *Other Symbol* that have the *alphabetic* binary property in Unicode
    ALPHABETIC_OTHER_SYMBOL = [
        ("\u24b6", "\u24e9"),
        ("\U0001f130", "\U0001f149"),
        ("\U0001f150", "\U0001f169"),
        ("\U0001f170", "\U0001f189"),
    ]

    DISCARD_CATEGORIES: set[CategoryCode] = {
        "No",  # Other Number
        "Pi",  # Initial Punctuation
        "Pf",  # Final Punctuation
        "Ps",  # Open Punctuation
        "Pe",  # Close Punctuation
        "Po",  # Other Punctuation
        # "Pd",  # Dash Punctuation; all except a normal dash (`-`)
        "Sm",  # Math Symbol
        "Sc",  # Currency Symbol
        "Sk",  # Modifier Symbol
        # "So",  # Other Symbol; all except alphabetic other symbols
        "Cc",  # Control
        "Co",  # Private Use
        "Cf",  # Format
        "Cn",  # Unassigned
        # "Zs",  # Space Separator; all except a normal space (` `)
        "Zl",  # Line Separator
        "Zp",  # Paragraph_Separator
    }

    ranges: list[tuple[int, int]] = []
    ranges.extend(get_category_ranges(DISCARD_CATEGORIES))
    ranges.extend(subtract_ranges(get_category_ranges({"Pd"}), [(ord("-"), ord("-"))]))
    ranges.extend(subtract_ranges(get_category_ranges({"So"}), [(ord(start), ord(end)) for start, end in ALPHABETIC_OTHER_SYMBOL]))
    ranges.extend(subtract_ranges(get_category_ranges({"Zs"}), [(ord(" "), ord(" "))]))
    ranges.sort()
    return re.compile(f"[{to_unicode_ranges(ranges)}]")


_DISALLOWED_CHAR_REGEXP = re.compile(r"[^\sa-z0-9_-]")
_PUNCTUATION_REMOVE_REGEXP = re.compile(r"[^\s\w-]")
_SPACE_COLLAPSE_REGEXP = re.compile(r"\s+")


def title_to_identifier(title: str) -> str:
    """
    Converts a section heading title to a Markdown same-page anchor.

    :param title: Heading title text without formatting.
    :returns: A slug suitable for use as a Markdown same-page anchor.
    """

    # remove leading and trailing whitespace, convert letters to lowercase
    s = title.strip().lower()
    # remove international characters
    s = _DISALLOWED_CHAR_REGEXP.sub("", s)
    # collapse whitespace to hyphens
    s = _SPACE_COLLAPSE_REGEXP.sub("-", s)
    return s


def title_to_ascii_slug(title: str) -> str:
    """
    Converts a section heading title to a Markdown same-page anchor with accent removal.

    :param title: Heading title text without formatting.
    :returns: A slug suitable for use as a Markdown same-page anchor.
    """

    s = title.strip()
    # normalize to NFD (decomposes accents)
    s = unicodedata.normalize("NFD", s)
    # remove non-spacing combining diacritic marks (zero advance width) (Unicode category `Mn`)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    # transform to lowercase
    s = s.lower()
    # remove punctuation except spaces and hyphens
    s = _DISALLOWED_CHAR_REGEXP.sub("", s)
    # collapse whitespace to hyphens
    s = _SPACE_COLLAPSE_REGEXP.sub("-", s)

    return s


def title_to_common_slug(title: str) -> str:
    """
    Converts a section heading title to a Markdown same-page anchor retaining Unicode word characters.

    :param title: Heading title text without formatting.
    :returns: A slug mostly compatible with GitHub and GitLab flavor Markdown.
    """

    # normalize equivalent Unicode sequences and transform letters to lowercase
    s = unicodedata.normalize("NFC", title.strip()).lower()
    # remove punctuation except spaces, hyphens and Unicode word characters
    s = _PUNCTUATION_REMOVE_REGEXP.sub("", s)
    # collapse whitespace to hyphens
    s = _SPACE_COLLAPSE_REGEXP.sub("-", s)
    return s


def title_to_slug(title: str) -> str:
    """
    Converts a section heading title to a Markdown same-page anchor compatible with GitHub and GitLab.

    :param title: Heading title text without formatting.
    :returns: A slug mostly compatible with GitHub and GitLab flavor Markdown.
    """

    s = unicodedata.normalize("NFC", title.strip()).lower()
    s = get_symbol_matching_regex().sub("", s)
    s = s.replace(" ", "-")
    return s
