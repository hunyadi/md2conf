@echo off
rem Publish Markdown files to Confluence wiki.
rem
rem Copyright 2022-2026, Levente Hunyadi
rem https://github.com/hunyadi/md2conf

if exist dist rmdir /s /q dist
if errorlevel 1 goto error
for /d %%i in (*.egg-info) do rmdir /s /q "%%i"
if errorlevel 1 goto error

python -m build --sdist --wheel
if errorlevel 1 goto error
goto :EOF

:error
exit /b 1
