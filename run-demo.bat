@echo off
REM Double-click to run Data-Align's built-in demo.
REM Uses Python if it is installed; otherwise Docker Desktop (must be running).
cd /d "%~dp0"
set OUT=dataalign_output
set DONE=0

py -3 --version >nul 2>&1
if not errorlevel 1 (
  echo Running with Python...
  py -3 -m dataalign demo --out %OUT%
  if exist "%OUT%\defective\report.html" set DONE=1
)

if "%DONE%"=="0" (
  python --version >nul 2>&1
  if not errorlevel 1 (
    echo Running with Python...
    python -m dataalign demo --out %OUT%
    if exist "%OUT%\defective\report.html" set DONE=1
  )
)

if "%DONE%"=="0" (
  docker version >nul 2>&1
  if not errorlevel 1 (
    echo Running with Docker...
    docker run --rm -v "%cd%:/app" -w /app python:3.12-slim python -m dataalign demo --out %OUT%
    if exist "%OUT%\defective\report.html" set DONE=1
  )
)

echo.
if "%DONE%"=="1" (
  echo Opening the report that found the planted problems...
  start "" "%OUT%\defective\report.html"
) else (
  echo The demo could not run. You need ONE of these:
  echo   1. Python 3.11 or newer from python.org  ^(tick "Add Python to PATH"^)
  echo   2. Docker Desktop installed AND started ^(wait until it says Engine running^)
  echo Then double-click run-demo.bat again.
)
pause
