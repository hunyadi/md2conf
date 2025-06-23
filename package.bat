@echo off

if exist dist rmdir /s /q dist
if errorlevel 1 goto error
for /d %%i in (*.egg-info) do rmdir /s /q "%%i"
if errorlevel 1 goto error

python -m build --sdist --wheel
if errorlevel 1 goto error
goto :EOF

:error
exit /b 1
