@echo off
rem Publish Markdown files to Confluence wiki.
rem
rem Copyright 2022-2026, Levente Hunyadi
rem https://github.com/hunyadi/md2conf

setlocal
set PYTHON=python

rem Run static type checker and verify formatting guidelines
%PYTHON% -m ruff check
if errorlevel 1 goto error
%PYTHON% -m ruff format --check
if errorlevel 1 goto error
%PYTHON% -m mypy md2conf
if errorlevel 1 goto error
%PYTHON% -m mypy tests
if errorlevel 1 goto error
%PYTHON% -m mypy integration_tests
if errorlevel 1 goto error

rem Test help message
%PYTHON% -m md2conf --help > NUL
if errorlevel 1 goto error

rem Generate documentation
%PYTHON% -c "import sys; sys.exit(0 if sys.version_info >= (3, 13) else 1)"
if errorlevel 1 (
    echo Skipping documentation generation on Python ^< 3.13
) else (
    %PYTHON% documentation.py
    if errorlevel 1 goto error
)

goto EOF

:error
exit /b %errorlevel%

:EOF
