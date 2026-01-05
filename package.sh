#!/usr/bin/env sh
#
# Publish Markdown files to Confluence wiki.
#
# Copyright 2022-2026, Levente Hunyadi
# https://github.com/hunyadi/md2conf

#
# Builds a Python package and runs unit tests in Docker
#

set -e
PYTHON_EXECUTABLE=${PYTHON:-python3}

# clean up output from previous runs
if [ -d dist ]; then rm -rf dist; fi
if [ -d *.egg-info ]; then rm -rf *.egg-info; fi

# create PyPI package for distribution
$PYTHON_EXECUTABLE -m build --sdist --wheel

# build Docker image
VERSION=`$PYTHON_EXECUTABLE -c "from md2conf import __version__; print(__version__)"`
docker build -f Dockerfile -t leventehunyadi/md2conf:latest -t leventehunyadi/md2conf:$VERSION .

# run Docker image with Markdown input files containing diagrams to produce PNG/SVG output
# pass environment variables from the file `.env`
FILES="tests/source/mermaid.md tests/source/plantuml.md"
docker run -i -t --rm --env-file .env --name md2conf -v $(pwd):/data leventehunyadi/md2conf:latest --local --diagram-output-format=png $FILES
docker run -i -t --rm --env-file .env --name md2conf -v $(pwd):/data leventehunyadi/md2conf:latest --local --diagram-output-format=svg $FILES
