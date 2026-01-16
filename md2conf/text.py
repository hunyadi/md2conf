"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""
import re
import logging
    
logger = logging.getLogger(__name__)


def wrap_text(text: str, line_length: int = 160) -> str:
    """
    Wraps text by replacing individual whitespace characters with a linefeed such that lines in the output honor the specified line length.

    :param text: Input text, optionally with existing UNIX line endings.
    :param line_length: Desired line length.
    :returns: Wrapped output text. Long words that exceed the specified line length are not broken.
    """

    if line_length < 1:
        raise ValueError("expected: line_length > 0")

    input = text.encode("utf-8")
    output = bytearray(len(input))
    pos = 0
    length = len(input)

    while pos < length:
        end = min(pos + line_length, length)

        # find any linefeed already in input
        left = pos
        while left < end and input[left] != 0x0A:
            left += 1
        if left != end:
            output[pos : left + 1] = input[pos : left + 1]
            pos = left + 1  # include linefeed
            continue

        # find the nearest whitespace before end of line
        right = end
        while right > pos and input[right - 1] not in b"\t\v\f\r ":
            right -= 1

        if right == pos or end == length:
            # no whitespace found or at end of input; copy the rest
            output[pos:end] = input[pos:end]
            pos = end
        else:
            # replace the whitespace with a newline
            output[pos : right - 1] = input[pos : right - 1]
            output[right - 1] = 0x0A  # linefeed '\n'
            pos = right  # skip the whitespace (already replaced)

    return output.decode("utf-8")

def filter_out_excluded_sections(text: str) -> str:
    """
    Removes sections marked with md2conf-skip comments.
    
    Removes content between:
    <!-- md2conf-skip-start --> and <!-- md2conf-skip-end -->
    
    :param text: Raw Markdown text
    :returns: Markdown text with excluded sections removed
    """
    # Pattern to match excluded sections
    # (?s) is inline flag for re.DOTALL - makes . match newlines
    # .*? is non-greedy to handle multiple exclusion blocks
    # \s* allows optional whitespace around marker names
    pattern = r'<!--\s*md2conf-skip-start\s*-->.*?<!--\s*md2conf-skip-end\s*-->'

    # Warn about unmatched markers
    start_pattern = r'<!--\s*md2conf-skip-start\s*-->'
    end_pattern = r'<!--\s*md2conf-skip-end\s*-->'
    start_count = len(re.findall(start_pattern, text, flags=re.IGNORECASE))
    end_count = len(re.findall(end_pattern, text, flags=re.IGNORECASE))
    if start_count != end_count:
        logger.warning(
            f"Unmatched md2conf-skip markers: found {start_count} start marker(s) "
            f"and {end_count} end marker(s). Content may not be excluded as expected."
        )
    
    cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
    
    return cleaned_text
