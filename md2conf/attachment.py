"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ImageData:
    path: Path
    description: str | None = None


@dataclass
class EmbeddedFileData:
    data: bytes
    description: str | None = None


class AttachmentCatalog:
    "Maintains a list of files and binary data to be uploaded to Confluence as attachments."

    images: list[ImageData]
    embedded_files: dict[str, EmbeddedFileData]

    def __init__(self) -> None:
        self.images = []
        self.embedded_files = {}

    def add_image(self, data: ImageData) -> None:
        self.images.append(data)

    def add_embed(self, filename: str, data: EmbeddedFileData) -> None:
        self.embedded_files[filename] = data


def attachment_name(ref: Path | str) -> str:
    """
    Safe name for use with attachment uploads.

    Mutates a relative path such that it meets Confluence's attachment naming requirements.

    Allowed characters:

    * Alphanumeric characters: 0-9, a-z, A-Z
    * Special characters: hyphen (-), underscore (_), period (.)
    """

    if isinstance(ref, Path):
        path = ref
    else:
        path = Path(ref)

    if path.drive or path.root:
        raise ValueError(f"required: relative path; got: {ref}")

    regexp = re.compile(r"[^\-0-9A-Za-z_.]", re.UNICODE)

    def replace_part(part: str) -> str:
        if part == "..":
            return "PAR"
        else:
            return regexp.sub("_", part)

    parts = [replace_part(p) for p in path.parts]
    return Path(*parts).as_posix().replace("/", "_")
