@echo off
rem ===== NERP - switch the user logon OFF (no password) =====
cd /d "%~dp0.."
if exist "data\login_on.flag" del "data\login_on.flag"
echo.
echo  User logon is now OFF - no password. Close NERP (power button) and start it again.
echo.
pause
