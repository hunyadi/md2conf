set -e

PYTHON=python3

# Run static type checker and verify formatting guidelines
$PYTHON -m mypy md2conf
$PYTHON -m flake8 md2conf
$PYTHON -m mypy tests
$PYTHON -m flake8 tests
