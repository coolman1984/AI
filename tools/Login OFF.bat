@echo off
rem ===== MM Core - switch the user logon OFF (no password) =====
cd /d "%~dp0.."
if exist "data\login_on.flag" del "data\login_on.flag"
echo.
echo  User logon is now OFF - no password. Close MM Core (power button) and start it again.
echo.
pause
