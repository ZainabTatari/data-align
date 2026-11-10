@echo off
REM Double-click to audit YOUR data: old data in mydata\old, new data in mydata\new.
cd /d "%~dp0"
set DONE=0
set RC=0

py -3 --version >nul 2>&1
if not errorlevel 1 (
  py -3 -m dataalign easy --no-open
  set RC=%errorlevel%
  set DONE=1
)
if "%DONE%"=="0" (
  python --version >nul 2>&1
  if not errorlevel 1 (
    python -m dataalign easy --no-open
    set RC=%errorlevel%
    set DONE=1
  )
)
if "%DONE%"=="0" (
  docker version >nul 2>&1
  if not errorlevel 1 (
    docker run --rm -v "%cd%:/app" -w /app python:3.12-slim python -m dataalign easy --no-open
    set RC=%errorlevel%
    set DONE=1
  )
)
echo.
if "%DONE%"=="0" (
  echo Cannot run: you need Python 3.11+ ^(python.org, tick "Add Python to PATH"^) OR Docker Desktop started.
  pause
  exit /b 1
)
if exist "my_report\report.html" (
  echo Opening your report...
  start "" "my_report\report.html"
) else (
  echo No report was created. Read the message above - it says what to fix.
)
pause
