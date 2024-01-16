set -e

# Run static type checker and verify formatting guidelines
python3 -m mypy md2conf
python3 -m flake8 md2conf
python3 -m mypy tests
python3 -m flake8 tests
