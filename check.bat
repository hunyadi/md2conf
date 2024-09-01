@echo off

rem Run static type checker and verify formatting guidelines
python -m mypy md2conf
if errorlevel 1 goto error
python -m flake8 md2conf
if errorlevel 1 goto error
python -m mypy tests
if errorlevel 1 goto error
python -m flake8 tests
if errorlevel 1 goto error
goto :EOF

:error
exit /b 1
