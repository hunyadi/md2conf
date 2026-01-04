set -e
# Publish Markdown files to Confluence wiki.
#
# Copyright 2022-2026, Levente Hunyadi
# https://github.com/hunyadi/md2conf

#
# Builds a Python package and runs unit tests in Docker
#

PYTHON_EXECUTABLE=${PYTHON:-python3}

# clean up output from previous runs
if [ -d dist ]; then rm -rf dist; fi
if [ -d *.egg-info ]; then rm -rf *.egg-info; fi

# create PyPI package for distribution
$PYTHON_EXECUTABLE -m build --sdist --wheel

VERSION=`$PYTHON_EXECUTABLE -c "from md2conf import __version__; print(__version__)"`
docker build -f Dockerfile -t leventehunyadi/md2conf:latest -t leventehunyadi/md2conf:$VERSION .
docker run -i -t --rm --env-file .env --name md2conf -v $(pwd):/data leventehunyadi/md2conf:latest sample/index.md --ignore-invalid-url

# test PyPI package with various Python versions
# pass environment variables from the file `.env`
for PYTHON_VERSION in 3.10 3.11 3.12 3.13 3.14
do
    docker build -f test.dockerfile -t py-$PYTHON_VERSION-image --build-arg PYTHON_VERSION=$PYTHON_VERSION .
    docker run -i -t --rm --env-file .env py-$PYTHON_VERSION-image python3 -m unittest discover tests
    docker rmi py-$PYTHON_VERSION-image
done
