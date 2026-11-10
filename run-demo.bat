@echo off
REM Double-click to run Data-Align's built-in demo (needs Docker Desktop running).
cd /d "%~dp0"
docker run --rm -v "%cd%:/app" -w /app python:3.12-slim python -m dataalign demo --out dataalign_output
echo.
echo Opening the report that found the planted problems...
start "" "dataalign_output\defective\report.html"
pause
