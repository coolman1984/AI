@echo off
rem ===== MM Core - run all quality checks (tests, process catalog, data consistency) =====
cd /d "%~dp0.."
python tools\qa\check_all.py
echo.
pause
