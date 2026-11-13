@echo off
rem ===== NERP - copy the database to data\backup =====
cd /d "%~dp0.."
where python >nul 2>nul && (python run.py --backup) || (py -3 run.py --backup)
pause
