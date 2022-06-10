import argparse
import logging
import os.path

from .api import ConfluenceAPI
from .application import synchronize_page

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
    choices=["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
    default="INFO",
    help="Use this option to set the log verbosity.",
)
args = parser.parse_args()

logging.basicConfig(
    level=getattr(logging, args.loglevel.upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - %(funcName)s [%(lineno)d] - %(message)s",
)

with ConfluenceAPI(args.domain, args.username, args.apikey, args.space) as api:
    synchronize_page(api, args.mdfile)
