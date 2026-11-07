@echo off
rem ===== MM Core - delete all data and start EMPTY (no demo data) =====
cd /d "%~dp0.."
echo This deletes ALL data in MM Core and starts an empty system.
choice /m "Continue"
if errorlevel 2 exit /b 0
call "%~dp0..\Start MM Core.bat" --reset --empty
