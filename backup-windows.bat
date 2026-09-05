@echo off
rem ==============================================================================
rem Tapo Cloud Video Daily Backup Script for Windows Task Scheduler
rem ==============================================================================
setlocal

rem === Configuration ===
rem Backup destination directory (default is TapoBackups folder in your user profile)
set "BACKUP_DIR=%USERPROFILE%\TapoBackups"

rem Number of past days to download (default: 7 days)
set "DAYS=7"

rem Overwrite existing files (0 = skip existing duplicates, 1 = overwrite)
set "OVERWRITE=0"

rem Concurrent download threads (default: 8)
set "CONCURRENCY=8"

rem Optional: specific camera(s) to backup (leave blank or 'all' for all cameras)
rem Examples: set "CAMERA=정우방" or set "CAMERA=정우방,정우"
set "CAMERA="
rem =====================

set "SCRIPT_DIR=%~dp0"

if exist "%SCRIPT_DIR%venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe"
) else if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [%DATE% %TIME%] Starting Tapo video backup...
echo Saving videos to: %BACKUP_DIR%

if defined CAMERA (
    echo Target camera(s): %CAMERA%
    "%PYTHON_EXE%" "%SCRIPT_DIR%tapo-cli.py" download-videos --days %DAYS% --path "%BACKUP_DIR%" --overwrite %OVERWRITE% --camera "%CAMERA%" --concurrency %CONCURRENCY%
) else (
    "%PYTHON_EXE%" "%SCRIPT_DIR%tapo-cli.py" download-videos --days %DAYS% --path "%BACKUP_DIR%" --overwrite %OVERWRITE% --concurrency %CONCURRENCY%
)

set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% equ 0 (
    echo [%DATE% %TIME%] Backup completed successfully.
) else (
    echo [%DATE% %TIME%] Backup failed with exit code %EXIT_CODE%.
)

exit /b %EXIT_CODE%
