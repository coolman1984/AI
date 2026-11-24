@echo off
rem ===== NERP - delete all data and load the CERAMIC FACTORY demo =====
cd /d "%~dp0.."
echo This deletes ALL data in NERP and loads the ceramic tile factory demo.
choice /m "Continue"
if errorlevel 2 exit /b 0
call "%~dp0..\Start NERP.bat" --reset --demo ceramic
