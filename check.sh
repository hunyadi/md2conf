#!/usr/bin/env sh
#
# Publish Markdown files to Confluence wiki.
#
# Copyright 2022-2026, Levente Hunyadi
# https://github.com/hunyadi/md2conf

set -e
PYTHON_EXECUTABLE=${PYTHON:-python3}

# Run static type checker and verify formatting guidelines
$PYTHON_EXECUTABLE -m ruff check
$PYTHON_EXECUTABLE -m ruff format --check
$PYTHON_EXECUTABLE -m mypy md2conf
$PYTHON_EXECUTABLE -m mypy tests
$PYTHON_EXECUTABLE -m mypy integration_tests

# Test help message
$PYTHON_EXECUTABLE -m md2conf --help > /dev/null

# Generate documentation
$PYTHON_EXECUTABLE documentation.py
