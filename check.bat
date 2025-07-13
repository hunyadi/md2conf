@echo off

rem Run static type checker and verify formatting guidelines
python -m ruff check
if errorlevel 1 goto error
python -m ruff format --check
if errorlevel 1 goto error
python -m mypy md2conf
if errorlevel 1 goto error
python -m mypy tests
if errorlevel 1 goto error
python -m mypy integration_tests
if errorlevel 1 goto error

rem Test help message
python -m md2conf --help > NUL
if errorlevel 1 goto error

rem Generate documentation
python documentation.py
if errorlevel 1 goto error

goto :EOF

:error
exit /b 1
