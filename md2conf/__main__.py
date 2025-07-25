"""
Publish Markdown files to Confluence wiki.

Parses Markdown files, converts Markdown content into the Confluence Storage Format (XHTML), and invokes
Confluence API endpoints to upload images and content.

Copyright 2022-2025, Levente Hunyadi

:see: https://github.com/hunyadi/md2conf
"""

import argparse
import logging
import os.path
import sys
import typing
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Sequence, Union

from . import __version__
from .domain import ConfluenceDocumentOptions, ConfluencePageID
from .extra import override
from .metadata import ConfluenceSiteMetadata
from .properties import ArgumentError, ConfluenceConnectionProperties, ConfluenceSiteProperties


class Arguments(argparse.Namespace):
    mdpath: Path
    domain: Optional[str]
    path: Optional[str]
    api_url: Optional[str]
    username: Optional[str]
    api_key: Optional[str]
    space: Optional[str]
    loglevel: str
    ignore_invalid_url: bool
    heading_anchors: bool
    root_page: Optional[str]
    keep_hierarchy: bool
    generated_by: Optional[str]
    render_drawio: bool
    render_mermaid: bool
    diagram_output_format: Literal["png", "svg"]
    local: bool
    headers: dict[str, str]
    webui_links: bool


class KwargsAppendAction(argparse.Action):
    """Append key-value pairs to a dictionary."""

    @override
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Union[None, str, Sequence[Any]],
        option_string: Optional[str] = None,
    ) -> None:
        try:
            d = dict(map(lambda x: x.split("="), typing.cast(Sequence[str], values)))
        except ValueError:
            raise argparse.ArgumentError(
                self,
                f'Could not parse argument "{values}". It should follow the format: k1=v1 k2=v2 ...',
            ) from None
        setattr(namespace, self.dest, d)


def unsupported(prefer: str) -> type[argparse.Action]:
    class UnsupportedAction(argparse.Action):
        """Display an error for unsupported command-line options."""

        @override
        def __call__(
            self,
            parser: argparse.ArgumentParser,
            namespace: argparse.Namespace,
            values: Union[None, str, Sequence[Any]],
            option_string: Optional[str] = None,
        ) -> None:
            raise argparse.ArgumentError(
                self,
                f"this command-line option is no longer supported, use `--{prefer}`",
            )

        @override
        def __repr__(self) -> str:
            return f"{unsupported.__name__}({repr(prefer)})"

    return UnsupportedAction


class PositionalOnlyHelpFormatter(argparse.HelpFormatter):
    def _format_usage(
        self,
        usage: Optional[str],
        actions: Iterable[argparse.Action],
        groups: Iterable[argparse._MutuallyExclusiveGroup],
        prefix: Optional[str],
    ) -> str:
        # filter only positional arguments
        positional_actions = [a for a in actions if not a.option_strings]

        # format usage string with only positional arguments
        usage_str = super()._format_usage(usage, positional_actions, groups, prefix).rstrip()

        # insert [OPTIONS] as a placeholder for all options (detailed below)
        usage_str += " [OPTIONS]\n"

        return usage_str


def main() -> None:
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
        "--apikey",
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
        help="Render draw.io diagrams as image files and add as attachments. (Installed utility required.)",
    )
    parser.add_argument(
        "--no-render-drawio",
        dest="render_drawio",
        action="store_false",
        help="Inline draw.io diagram in Confluence page. (Marketplace app required.)",
    )
    parser.add_argument(
        "--render-mermaid",
        dest="render_mermaid",
        action="store_true",
        default=True,
        help="Render Mermaid diagrams as image files and add as attachments. (Installed utility required.)",
    )
    parser.add_argument(
        "--no-render-mermaid",
        dest="render_mermaid",
        action="store_false",
        help="Inline Mermaid diagram in Confluence page. (Marketplace app required.)",
    )
    parser.add_argument(
        "--diagram-output-format",
        dest="diagram_output_format",
        choices=["png", "svg"],
        default="png",
        help="Format for rendering Mermaid and draw.io diagrams (default: 'png').",
    )
    parser.add_argument(
        "--render-mermaid-format",
        action=unsupported("diagram-output-format"),
        metavar="FORMAT",
        help="Format for rendering Mermaid diagrams (default: 'png').",
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
    parser.add_argument(
        "--webui-links",
        action="store_true",
        default=False,
        help="Enable Confluence Web UI links. (Typically required for on-prem versions of Confluence.)",
    )

    args = Arguments()
    parser.parse_args(namespace=args)

    args.mdpath = Path(args.mdpath)

    logging.basicConfig(
        level=getattr(logging, args.loglevel.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
    )

    options = ConfluenceDocumentOptions(
        heading_anchors=args.heading_anchors,
        ignore_invalid_url=args.ignore_invalid_url,
        generated_by=args.generated_by,
        root_page_id=ConfluencePageID(args.root_page) if args.root_page else None,
        keep_hierarchy=args.keep_hierarchy,
        render_drawio=args.render_drawio,
        render_mermaid=args.render_mermaid,
        diagram_output_format=args.diagram_output_format,
        webui_links=args.webui_links,
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
        from .application import Application

        try:
            properties = ConfluenceConnectionProperties(
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
                Application(
                    api,
                    options,
                ).process(args.mdpath)
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
