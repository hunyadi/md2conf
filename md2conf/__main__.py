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
from types import TracebackType
from typing import Any, Iterable, Sequence

from requests.exceptions import HTTPError, JSONDecodeError

from . import __version__
from .clio import add_arguments, get_options
from .compatibility import override
from .environment import ArgumentError, ConfluenceSiteProperties, ConnectionProperties
from .metadata import ConfluenceSiteMetadata
from .options import ConfluencePageID, ConverterOptions, DocumentOptions

LOGGER = logging.getLogger(__name__)


class Arguments(argparse.Namespace):
    mdpath: list[Path]
    domain: str | None
    path: str | None
    api_url: str | None
    username: str | None
    api_key: str | None
    space: str | None
    api_version: str
    loglevel: str
    root_page: str | None
    keep_hierarchy: bool
    title_prefix: str | None
    generated_by: str | None
    skip_update: bool
    line_numbers: bool
    local: bool
    headers: dict[str, str]


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
    parser.add_argument("mdpath", type=Path, nargs="+", help="Path to Markdown file or directory to convert and publish.")
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
        "--api-version",
        dest="api_version",
        choices=["v1", "v2"],
        default="v2",
        help="Confluence REST API version to use (v1 for Data Center/Server, v2 for Cloud). Default: v2",
    )
    parser.add_argument(
        "-l",
        "--loglevel",
        choices=[logging.getLevelName(level).lower() for level in (logging.DEBUG, logging.INFO, logging.WARN, logging.ERROR, logging.CRITICAL)],
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
        "--skip-hierarchy",
        dest="keep_hierarchy",
        action="store_false",
        help="Flatten directories with no `index.md` or `README.md` when exporting to Confluence.",
    )
    parser.add_argument(
        "--generated-by",
        default="This page has been generated with a tool.",
        metavar="MARKDOWN",
        help="Add prompt to pages.",
    )
    parser.add_argument(
        "--no-generated-by",
        dest="generated_by",
        action="store_const",
        const=None,
        help="Do not add 'generated by a tool' prompt to pages.",
    )
    parser.add_argument(
        "--skip-update",
        action="store_true",
        default=False,
        help="Skip saving Confluence page ID in Markdown files.",
    )
    add_arguments(parser, ConverterOptions)
    if sys.version_info >= (3, 13):
        parser.add_argument(
            "--ignore-invalid-url",
            dest="force_valid_url",
            action="store_false",
            help="Emit a warning but otherwise ignore relative URLs that point to ill-specified locations.",
            deprecated=True,
        )
    parser.add_argument(
        "--title-prefix",
        default=None,
        metavar="TEXT",
        help="String to prepend to Confluence page title for each published page.",
    )
    parser.add_argument(
        "--line-numbers",
        dest="line_numbers",
        action="store_true",
        default=False,
        help="Inject line numbers in Markdown source to help localize conversion errors.",
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


def _exception_hook(exc_type: type[BaseException], exc_value: BaseException, traceback: TracebackType | None) -> None:
    LOGGER.exception("Exception raised: %s", exc_type.__name__, exc_info=exc_value)
    ex: BaseException | None = exc_value
    while ex is not None:
        print(f"\033[95m{ex.__class__.__name__}\033[0m: {ex}")

        if isinstance(ex, HTTPError):
            # print details for a response with JSON body
            if ex.response is not None:
                try:
                    LOGGER.error(ex.response.json())
                except JSONDecodeError:
                    pass

        ex = ex.__cause__


sys.excepthook = _exception_hook  # spellchecker:disable-line


def main() -> None:
    parser = get_parser()
    args = Arguments()
    parser.parse_args(namespace=args)

    logging.basicConfig(
        level=getattr(logging, args.loglevel.upper(), logging.INFO),
        format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
    )

    options = DocumentOptions(
        root_page_id=ConfluencePageID(args.root_page) if args.root_page else None,
        keep_hierarchy=args.keep_hierarchy,
        title_prefix=args.title_prefix,
        generated_by=args.generated_by,
        skip_update=args.skip_update,
        converter=get_options(args, ConverterOptions),
        line_numbers=args.line_numbers,
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
        converter = LocalConverter(options, site_metadata)
        for item in args.mdpath:
            converter.process(item)
    else:
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
                api_version=args.api_version,
            )
        except ArgumentError as e:
            parser.error(str(e))
        with ConfluenceAPI(properties) as api:
            publisher = Publisher(api, options)
            for item in args.mdpath:
                publisher.process(item)


if __name__ == "__main__":
    main()
