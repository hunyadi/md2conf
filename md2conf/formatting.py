"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import enum
from dataclasses import dataclass
from typing import ClassVar

from .csf import AC_ATTR


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


@dataclass
class ImageAttributes:
    """
    Attributes applied to an `<img>` element.

    :param context: Identifies the formatting context for the element (block or inline).
    :param width: Natural image width in pixels.
    :param height: Natural image height in pixels.
    :param alt: Alternate text.
    :param title: Title text (a.k.a. image tooltip).
    :param caption: Caption text (shown below figure).
    :param alignment: Alignment for block-level images.
    """

    context: FormattingContext
    width: int | None
    height: int | None
    alt: str | None
    title: str | None
    caption: str | None
    alignment: ImageAlignment = ImageAlignment.CENTER

    def __post_init__(self) -> None:
        if self.caption is None and self.context is FormattingContext.BLOCK:
            self.caption = self.title or self.alt

    def as_dict(self, *, max_width: int | None) -> dict[str, str]:
        """
        Produces a key-value store of element attributes.

        :param max_width: The desired maximum width of the image in pixels.
        """

        attributes: dict[str, str] = {}
        match self.context:
            case FormattingContext.BLOCK:
                match self.alignment:
                    case ImageAlignment.LEFT:
                        align = "left"
                        layout = "align-start"
                    case ImageAlignment.RIGHT:
                        align = "right"
                        layout = "align-end"
                    case ImageAlignment.CENTER:
                        align = "center"
                        layout = "center"
                attributes[AC_ATTR("align")] = align
                attributes[AC_ATTR("layout")] = layout

                if self.width is not None:
                    attributes[AC_ATTR("original-width")] = str(self.width)
                if self.height is not None:
                    attributes[AC_ATTR("original-height")] = str(self.height)
                if self.width is not None:
                    attributes[AC_ATTR("custom-width")] = "true"
                    # Use display_width if set, otherwise use natural width
                    effective_width = display_width(width=self.width, max_width=max_width) or self.width
                    attributes[AC_ATTR("width")] = str(effective_width)

            case FormattingContext.INLINE:
                if self.width is not None:
                    attributes[AC_ATTR("width")] = str(self.width)
                if self.height is not None:
                    attributes[AC_ATTR("height")] = str(self.height)

        if self.alt is not None:
            attributes.update({AC_ATTR("alt"): self.alt})
        if self.title is not None:
            attributes.update({AC_ATTR("title"): self.title})
        return attributes

    EMPTY_BLOCK: ClassVar["ImageAttributes"]
    EMPTY_INLINE: ClassVar["ImageAttributes"]

    @classmethod
    def empty(cls, context: FormattingContext) -> "ImageAttributes":
        match context:
            case FormattingContext.BLOCK:
                return cls.EMPTY_BLOCK
            case FormattingContext.INLINE:
                return cls.EMPTY_INLINE


ImageAttributes.EMPTY_BLOCK = ImageAttributes(
    FormattingContext.BLOCK, width=None, height=None, alt=None, title=None, caption=None, alignment=ImageAlignment.CENTER
)
ImageAttributes.EMPTY_INLINE = ImageAttributes(
    FormattingContext.INLINE, width=None, height=None, alt=None, title=None, caption=None, alignment=ImageAlignment.CENTER
)
