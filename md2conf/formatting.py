"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import enum
from dataclasses import dataclass
from typing import ClassVar


@enum.unique
class FormattingContext(enum.Enum):
    "Identifies the formatting context for the element."

    BLOCK = "block"
    INLINE = "inline"


@enum.unique
class ImageAlignment(enum.Enum):
    "Determines whether to align block-level images to center, left or right."

    CENTER = "center"
    LEFT = "left"
    RIGHT = "right"


def display_width(*, width: int | None, max_width: int | None) -> int | None:
    """
    Calculate the display width for an image, applying the maximum image width constraint if set.

    :returns: The constrained display width, or None if no constraint is needed.
    """

    if width is None or max_width is None:
        return None
    if width <= max_width:
        return None  # no constraint needed, image is already within limits
    return max_width


@dataclass(frozen=True)
class ImageAttributes:
    """
    Attributes applied to an `<img>` element.

    :param context: Identifies the formatting context for the element (block or inline).
    :param width: Natural image width in pixels.
    :param height: Natural image height in pixels.
    :param alt: Alternate text.
    :param title: Title text (a.k.a. image tooltip).
    :param show_caption: Whether to show caption text below figure (block-level images only).
    :param alignment: Figure alignment (block-level images only).
    """

    context: FormattingContext
    width: int | None
    height: int | None
    alt: str | None
    title: str | None
    show_caption: bool = True
    alignment: ImageAlignment = ImageAlignment.CENTER

    def get_caption(self) -> str | None:
        "Deduces a caption for block-level images."

        if self.show_caption and self.context is FormattingContext.BLOCK:
            return self.title or self.alt
        else:
            return None

    def with_dimensions(self, width: int, height: int) -> "ImageAttributes":
        "Creates a copy of the image attributes but with an updated width and height."

        return ImageAttributes(
            context=self.context,
            width=width,
            height=height,
            alt=self.alt,
            title=self.title,
            show_caption=self.show_caption,
            alignment=self.alignment,
        )

    EMPTY_BLOCK: ClassVar["ImageAttributes"]
    EMPTY_INLINE: ClassVar["ImageAttributes"]


ImageAttributes.EMPTY_BLOCK = ImageAttributes(
    FormattingContext.BLOCK, width=None, height=None, alt=None, title=None, show_caption=True, alignment=ImageAlignment.CENTER
)
ImageAttributes.EMPTY_INLINE = ImageAttributes(
    FormattingContext.INLINE, width=None, height=None, alt=None, title=None, show_caption=True, alignment=ImageAlignment.CENTER
)
