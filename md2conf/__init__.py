"""
Publish Markdown files to Confluence wiki.

Parses Markdown files, converts Markdown content into the Confluence Storage Format (XHTML), and invokes
Confluence API endpoints to upload images and content.
"""

from ._version import __version__

__all__ = ["__version__"]

__author__ = "Levente Hunyadi"
__copyright__ = "Copyright 2022-2025, Levente Hunyadi"
__license__ = "MIT"
__maintainer__ = "Levente Hunyadi"
__status__ = "Production"
