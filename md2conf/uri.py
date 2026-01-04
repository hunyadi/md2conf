"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import hashlib
import urllib.parse
import uuid
from urllib.parse import urlparse


def to_data_uri(mime: str, data: str) -> str:
    "Generates a data URI with the specified MIME type."

    # URL-encode data
    encoded = urllib.parse.quote(data, safe=";/?:@&=+$,-_.!~*'()#")  # minimal encoding
    return f"data:{mime},{encoded}"


def to_uuid(data: str) -> uuid.UUID:
    "Generates a UUID that represents the data."

    # create SHA-1 hash of the SVG content
    sha1_hash = hashlib.sha1(data.encode("utf-8")).digest()

    # generate UUID using the first 16 bytes of the hash
    return uuid.UUID(bytes=sha1_hash[:16])


def to_uuid_urn(data: str) -> str:
    "Generates a UUID URN that represents the data."

    return f"urn:uuid:{str(to_uuid(data))}"


def is_absolute_url(url: str) -> bool:
    urlparts = urlparse(url)
    return bool(urlparts.scheme) or bool(urlparts.netloc)


def is_relative_url(url: str) -> bool:
    urlparts = urlparse(url)
    return not bool(urlparts.scheme) and not bool(urlparts.netloc)
