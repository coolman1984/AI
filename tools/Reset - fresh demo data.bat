@echo off
rem ===== NERP - delete all data and load fresh demo data =====
cd /d "%~dp0.."
echo This deletes ALL data in NERP and loads fresh demo data.
choice /m "Continue"
if errorlevel 2 exit /b 0
call "%~dp0..\Start NERP.bat" --reset
