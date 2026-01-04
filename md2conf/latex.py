"""
Publish Markdown files to Confluence wiki.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import importlib.util
from io import BytesIO
from typing import BinaryIO, Literal


def render_latex(expression: str, *, format: Literal["png", "svg"] = "png", dpi: int = 100, font_size: int = 12) -> bytes:
    """
    Generates a PNG or SVG image of a LaTeX math expression using `matplotlib` for rendering.

    :param expression: A LaTeX math expression, e.g., r'\frac{a}{b}'.
    :param format: Output image format.
    :param dpi: Output image resolution (if applicable).
    :param font_size: Font size of the LaTeX text (if applicable).
    """

    with BytesIO() as f:
        _render_latex(expression, f, format=format, dpi=dpi, font_size=font_size)
        return f.getvalue()


if importlib.util.find_spec("matplotlib") is None:
    LATEX_ENABLED = False

    def _render_latex(expression: str, f: BinaryIO, *, format: Literal["png", "svg"], dpi: int, font_size: int) -> None:
        raise RuntimeError("matplotlib not installed; run: `pip install matplotlib`")

else:
    import matplotlib
    import matplotlib.pyplot as plt

    # spellchecker:disable-next-line
    matplotlib.rcParams["mathtext.fontset"] = "cm"  # change font to "Computer Modern"

    LATEX_ENABLED = True  # pyright: ignore[reportConstantRedefinition]

    def _render_latex(expression: str, f: BinaryIO, *, format: Literal["png", "svg"], dpi: int, font_size: int) -> None:
        # create a figure with no axis
        fig = plt.figure(dpi=dpi)  # pyright: ignore[reportUnknownMemberType]

        # transparent background
        fig.patch.set_alpha(0)

        # add LaTeX text
        # spellchecker:disable-next-line
        fig.text(x=0, y=0, s=f"${expression}$", fontsize=font_size)  # pyright: ignore[reportUnknownMemberType]

        # save the image
        fig.savefig(  # pyright: ignore[reportUnknownMemberType]
            f,
            transparent=True,
            format=format,
            bbox_inches="tight",
            pad_inches=0.0,
            metadata={"Title": expression} if format == "png" else None,
        )

        # close the figure to free memory
        plt.close(fig)
