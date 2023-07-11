import argparse
import logging
import os.path
import sys

import requests

from .api import ConfluenceAPI
from .application import synchronize_pages


class Arguments(argparse.Namespace):
    mdfile: str
    domain: str
    username: str
    apikey: str
    space: str
    loglevel: str


parser = argparse.ArgumentParser()
parser.prog = os.path.basename(os.path.dirname(__file__))
parser.add_argument("mdfile", help="Markdown file to convert and publish.")
parser.add_argument("-d", "--domain", help="Confluence organization domain.")
parser.add_argument("-u", "--username", help="Confluence user name.")
parser.add_argument(
    "-a",
    "--apikey",
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
        logging.getLevelName(level)
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

args = Arguments()
parser.parse_args(namespace=args)

logging.basicConfig(
    level=getattr(logging, args.loglevel.upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

try:
    with ConfluenceAPI(args.domain, args.username, args.apikey, args.space) as api:
        synchronize_pages(api, args.mdfile)
except requests.exceptions.HTTPError as err:
    logging.error(err)

    # print details for a response with JSON body
    try:
        response: requests.Response = err.response
        logging.error(response.json())
    except requests.exceptions.JSONDecodeError:
        pass

    sys.exit(1)
