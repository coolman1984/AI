@echo off
rem ===== MM Core - delete all data and load fresh demo data =====
cd /d "%~dp0.."
echo This deletes ALL data in MM Core and loads fresh demo data.
choice /m "Continue"
if errorlevel 2 exit /b 0
call "%~dp0..\Start MM Core.bat" --reset
