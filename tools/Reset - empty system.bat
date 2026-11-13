@echo off
rem ===== NERP - delete all data and start EMPTY (no demo data) =====
cd /d "%~dp0.."
echo This deletes ALL data in NERP and starts an empty system.
choice /m "Continue"
if errorlevel 2 exit /b 0
call "%~dp0..\Start NERP.bat" --reset --empty
