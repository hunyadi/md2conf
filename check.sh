set -e

PYTHON_EXECUTABLE=${PYTHON:-python3}

# Run static type checker and verify formatting guidelines
$PYTHON_EXECUTABLE -m ruff check
$PYTHON_EXECUTABLE -m ruff format --check
$PYTHON_EXECUTABLE -m mypy md2conf
$PYTHON_EXECUTABLE -m mypy tests
$PYTHON_EXECUTABLE -m mypy integration_tests

# Generate documentation
$PYTHON_EXECUTABLE documentation.py
