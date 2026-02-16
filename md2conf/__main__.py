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
from typing import Any, Iterable, Literal, Sequence

from requests.exceptions import HTTPError, JSONDecodeError

from . import __version__
from .clio import add_arguments, get_options
from .compatibility import override
from .environment import ArgumentError, ConfluenceSiteProperties, ConnectionProperties
from .metadata import ConfluenceSiteMetadata
from .options import ConfluencePageID, ProcessorOptions

LOGGER = logging.getLogger(__name__)


class Arguments(argparse.Namespace):
    mdpath: list[Path]
    domain: str | None
    path: str | None
    api_url: str | None
    username: str | None
    api_key: str | None
    space: str | None
    api_version: Literal["v2", "v1"] | None
    loglevel: str
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
    deprecated: dict[str, Any]
    if sys.version_info >= (3, 13):
        deprecated = {"deprecated": True}
    else:
        deprecated = {}

    parser = argparse.ArgumentParser(formatter_class=PositionalOnlyHelpFormatter)
    parser.prog = os.path.basename(os.path.dirname(__file__))
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("mdpath", type=Path, nargs="+", help="Path to Markdown file or directory to convert and publish.")
    parser.add_argument("-d", "--domain", help="Confluence organization domain. (env: CONFLUENCE_DOMAIN)")
    parser.add_argument("-p", "--path", help="Base path for Confluence. (env: CONFLUENCE_PATH; default: '/wiki/')")
    parser.add_argument(
        "--api-url",
        dest="api_url",
        help="Confluence API URL. Required for scoped tokens. Refer to documentation how to obtain one. (env: CONFLUENCE_API_URL)",
    )
    parser.add_argument("-u", "--username", help="Confluence user name. (env: CONFLUENCE_USER_NAME)")
    parser.add_argument(
        "-a",
        "--api-key",
        dest="api_key",
        help="Confluence API key. Refer to documentation how to obtain one. (env: CONFLUENCE_API_KEY)",
    )
    parser.add_argument(
        "-s",
        "--space",
        help="Confluence space key for pages to be published. If omitted, will default to user space. (env: CONFLUENCE_SPACE_KEY)",
    )
    parser.add_argument(
        "--api-version",
        dest="api_version",
        choices=["v2", "v1"],
        help="Confluence REST API version to use (v2 for Cloud, v1 for Data Center/Server). (env: CONFLUENCE_API_VERSION; default: v2)",
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
        type=ConfluencePageID,
        help="Confluence page to act as initial parent for creating new pages. (deprecated)",
        metavar="CONFLUENCE_PAGE_ID",
        **deprecated,
    )
    add_arguments(parser, ProcessorOptions)
    parser.add_argument(
        "--ignore-invalid-url",
        dest="force_valid_url",
        action="store_false",
        help="Emit a warning but otherwise ignore relative URLs that point to ill-specified locations. (deprecated)",
        **deprecated,
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

    options = get_options(args, ProcessorOptions)
    LOGGER.debug("Parsed options: %s", options)
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
