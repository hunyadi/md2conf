set -e

PYTHON=python3

# Run static type checker and verify formatting guidelines
ruff check
ruff format --check
$PYTHON -m mypy md2conf
$PYTHON -m mypy tests
$PYTHON -m mypy integration_tests

# Generate documentation
$PYTHON documentation.py
