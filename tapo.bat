@echo off
setlocal
set "SCRIPT_DIR=%~dp0"

if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" "%SCRIPT_DIR%tapo-cli.py" %*
