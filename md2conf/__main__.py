"""
Publish Markdown files to Confluence wiki.

Parses Markdown files, converts Markdown content into the Confluence Storage Format (XHTML), and invokes
Confluence API endpoints to upload images and content.

Copyright 2022-2026, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import argparse
import logging
import os.path
import sys
import typing
from io import StringIO
from pathlib import Path
from typing import Any, Iterable, Literal, Sequence

from . import __version__
from .compatibility import override
from .environment import ArgumentError, ConfluenceSiteProperties, ConnectionProperties
from .metadata import ConfluenceSiteMetadata
from .options import ConfluencePageID, ConverterOptions, DocumentOptions, ImageLayoutOptions, LayoutOptions


class Arguments(argparse.Namespace):
    mdpath: Path
    domain: str | None
    path: str | None
    api_url: str | None
    username: str | None
    api_key: str | None
    space: str | None
    loglevel: str
    heading_anchors: bool
    ignore_invalid_url: bool
    root_page: str | None
    keep_hierarchy: bool
    skip_title_heading: bool
    title_prefix: str | None
    generated_by: str | None
    prefer_raster: bool
    render_drawio: bool
    render_mermaid: bool
    render_plantuml: bool
    render_latex: bool
    diagram_output_format: Literal["png", "svg"]
    local: bool
    headers: dict[str, str]
    webui_links: bool
    alignment: Literal["center", "left", "right"]
    max_image_width: int | None
    use_panel: bool


class KwargsAppendAction(argparse.Action):
    """Append key-value pairs to a dictionary."""

    @override
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        try:
            d = dict(map(lambda x: x.split("="), typing.cast(Sequence[str], values)))
        except ValueError:
            raise argparse.ArgumentError(
                self,
                f'Could not parse argument "{values}". It should follow the format: k1=v1 k2=v2 ...',
            ) from None
        setattr(namespace, self.dest, d)


class PositionalOnlyHelpFormatter(argparse.HelpFormatter):
    def _format_usage(
        self,
        usage: str | None,
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],  # pyright: ignore[reportPrivateUsage]
        prefix: str | None,
    ) -> str:
        # filter only positional arguments
        positional_actions = [a for a in actions if not a.option_strings]

        # format usage string with only positional arguments
        usage_str = super()._format_usage(usage, positional_actions, groups, prefix).rstrip()

        # insert [OPTIONS] as a placeholder for all options (detailed below)
        usage_str += " [OPTIONS]\n"

        return usage_str


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(formatter_class=PositionalOnlyHelpFormatter)
    parser.prog = os.path.basename(os.path.dirname(__file__))
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("mdpath", help="Path to Markdown file or directory to convert and publish.")
    parser.add_argument("-d", "--domain", help="Confluence organization domain.")
    parser.add_argument("-p", "--path", help="Base path for Confluence (default: '/wiki/').")
    parser.add_argument(
        "--api-url",
        dest="api_url",
        help="Confluence API URL. Required for scoped tokens. Refer to documentation how to obtain one.",
    )
    parser.add_argument("-u", "--username", help="Confluence user name.")
    parser.add_argument(
        "-a",
        "--api-key",
        dest="api_key",
        help="Confluence API key. Refer to documentation how to obtain one.",
    )
    parser.add_argument(
        "-s",
        "--space",
        help="Confluence space key for pages to be published. If omitted, will default to user space.",
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        choices=[
            logging.getLevelName(level).lower()
            for level in (
                logging.DEBUG,
                logging.INFO,
                logging.WARN,
                logging.ERROR,
                logging.CRITICAL,
            )
        ],
        default=logging.getLevelName(logging.INFO),
        help="Use this option to set the log verbosity.",
    )
    parser.add_argument(
        "-r",
        dest="root_page",
        help="Root Confluence page to create new pages. If omitted, will raise exception when creating new pages.",
    )
    parser.add_argument(
        "--keep-hierarchy",
        action="store_true",
        default=False,
        help="Maintain source directory structure when exporting to Confluence.",
    )
    parser.add_argument(
        "--flatten-hierarchy",
        dest="keep_hierarchy",
        action="store_false",
        help="Flatten directories with no index.md or README.md when exporting to Confluence.",
    )
    parser.add_argument(
        "--generated-by",
        default="This page has been generated with a tool.",
        metavar="MARKDOWN",
        help="Add prompt to pages (default: 'This page has been generated with a tool.').",
    )
    parser.add_argument(
        "--no-generated-by",
        dest="generated_by",
        action="store_const",
        const=None,
        help="Do not add 'generated by a tool' prompt to pages.",
    )
    parser.add_argument(
        "--render-drawio",
        dest="render_drawio",
        action="store_true",
        default=True,
        help="Render draw.io diagrams as image files. (Installed utility required to covert.)",
    )
    parser.add_argument(
        "--no-render-drawio",
        dest="render_drawio",
        action="store_false",
        help="Upload draw.io diagram sources as Confluence page attachments. (Marketplace app required to display.)",
    )
    parser.add_argument(
        "--render-mermaid",
        dest="render_mermaid",
        action="store_true",
        default=True,
        help="Render Mermaid diagrams as image files. (Installed utility required to convert.)",
    )
    parser.add_argument(
        "--no-render-mermaid",
        dest="render_mermaid",
        action="store_false",
        help="Upload Mermaid diagram sources as Confluence page attachments. (Marketplace app required to display.)",
    )
    parser.add_argument(
        "--render-plantuml",
        dest="render_plantuml",
        action="store_true",
        default=True,
        help="Render PlantUML diagrams as image files. (Installed utility required to convert.)",
    )
    parser.add_argument(
        "--no-render-plantuml",
        dest="render_plantuml",
        action="store_false",
        help="Upload PlantUML diagram sources as Confluence page attachments. (Marketplace app required to display.)",
    )
    parser.add_argument(
        "--render-latex",
        dest="render_latex",
        action="store_true",
        default=True,
        help="Render LaTeX formulas as image files. (Matplotlib required to convert.)",
    )
    parser.add_argument(
        "--no-render-latex",
        dest="render_latex",
        action="store_false",
        help="Inline LaTeX formulas in Confluence page. (Marketplace app required to display.)",
    )
    parser.add_argument(
        "--diagram-output-format",
        dest="diagram_output_format",
        choices=["png", "svg"],
        default="png",
        help="Format for rendering Mermaid and draw.io diagrams (default: 'png').",
    )
    parser.add_argument(
        "--prefer-raster",
        dest="prefer_raster",
        action="store_true",
        default=True,
        help="Prefer PNG over SVG when both exist (default: enabled).",
    )
    parser.add_argument(
        "--no-prefer-raster",
        dest="prefer_raster",
        action="store_false",
        help="Use SVG files directly instead of preferring PNG equivalents.",
    )
    parser.add_argument(
        "--heading-anchors",
        action="store_true",
        default=False,
        help="Place an anchor at each section heading with GitHub-style same-page identifiers.",
    )
    parser.add_argument(
        "--no-heading-anchors",
        action="store_false",
        dest="heading_anchors",
        help="Don't place an anchor at each section heading.",
    )
    parser.add_argument(
        "--ignore-invalid-url",
        action="store_true",
        default=False,
        help="Emit a warning but otherwise ignore relative URLs that point to ill-specified locations.",
    )
    parser.add_argument(
        "--skip-title-heading",
        action="store_true",
        default=False,
        help="Skip the first heading from document body when it is used as the page title (does not apply if title comes from front-matter).",
    )
    parser.add_argument(
        "--no-skip-title-heading",
        dest="skip_title_heading",
        action="store_false",
        help="Keep the first heading in document body even when used as page title (default).",
    )
    parser.add_argument(
        "--title-prefix",
        default=None,
        metavar="TEXT",
        help="String to prepend to Confluence page title for each published page.",
    )
    parser.add_argument(
        "--webui-links",
        action="store_true",
        default=False,
        help="Enable Confluence Web UI links. (Typically required for on-prem versions of Confluence.)",
    )
    parser.add_argument(
        "--alignment",
        dest="alignment",
        choices=["center", "left", "right"],
        default="center",
        help="Alignment for block-level images and formulas (default: 'center').",
    )
    parser.add_argument(
        "--max-image-width",
        dest="max_image_width",
        type=int,
        default=None,
        help="Maximum display width for images [px]. Wider images are scaled down for page display. Original size kept for full-size viewing.",
    )
    parser.add_argument(
        "--use-panel",
        action="store_true",
        default=False,
        help="Transform admonitions and alerts into a Confluence custom panel.",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        default=False,
        help="Write XHTML-based Confluence Storage Format files locally without invoking Confluence API.",
    )
    parser.add_argument(
        "--headers",
        nargs="+",
        required=False,
        action=KwargsAppendAction,
        metavar="KEY=VALUE",
        help="Apply custom headers to all Confluence API requests.",
    )
    return parser


def get_help() -> str:
    parser = get_parser()
    with StringIO() as buf:
        parser.print_help(file=buf)
        return buf.getvalue()


def main() -> None:
    parser = get_parser()
    args = Arguments()
    parser.parse_args(namespace=args)

    args.mdpath = Path(args.mdpath)

    logging.basicConfig(
        level=getattr(logging, args.loglevel.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
    )

    options = DocumentOptions(
        root_page_id=ConfluencePageID(args.root_page) if args.root_page else None,
        keep_hierarchy=args.keep_hierarchy,
        title_prefix=args.title_prefix,
        generated_by=args.generated_by,
        converter=ConverterOptions(
            heading_anchors=args.heading_anchors,
            ignore_invalid_url=args.ignore_invalid_url,
            skip_title_heading=args.skip_title_heading,
            prefer_raster=args.prefer_raster,
            render_drawio=args.render_drawio,
            render_mermaid=args.render_mermaid,
            render_plantuml=args.render_plantuml,
            render_latex=args.render_latex,
            diagram_output_format=args.diagram_output_format,
            webui_links=args.webui_links,
            use_panel=args.use_panel,
            layout=LayoutOptions(
                image=ImageLayoutOptions(
                    alignment=args.alignment,
                    max_width=args.max_image_width,
                ),
            ),
        ),
    )
    if args.local:
        from .local import LocalConverter

        try:
            site_properties = ConfluenceSiteProperties(
                domain=args.domain,
                base_path=args.path,
                space_key=args.space,
            )
        except ArgumentError as e:
            parser.error(str(e))
        site_metadata = ConfluenceSiteMetadata(
            domain=site_properties.domain,
            base_path=site_properties.base_path,
            space_key=site_properties.space_key,
        )
        LocalConverter(options, site_metadata).process(args.mdpath)
    else:
        from requests import HTTPError, JSONDecodeError

        from .api import ConfluenceAPI
        from .publisher import Publisher

        try:
            properties = ConnectionProperties(
                api_url=args.api_url,
                domain=args.domain,
                base_path=args.path,
                user_name=args.username,
                api_key=args.api_key,
                space_key=args.space,
                headers=args.headers,
            )
        except ArgumentError as e:
            parser.error(str(e))
        try:
            with ConfluenceAPI(properties) as api:
                Publisher(api, options).process(args.mdpath)
        except HTTPError as err:
            logging.error(err)

            # print details for a response with JSON body
            if err.response is not None:
                try:
                    logging.error(err.response.json())
                except JSONDecodeError:
                    pass

            sys.exit(1)


if __name__ == "__main__":
    main()
