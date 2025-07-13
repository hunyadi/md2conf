@echo off

rem Load environment variable assignments from `.env`, and set them in the caller's context
for /f "usebackq tokens=*" %%A in (".env") do (
    set "%%A"
)
