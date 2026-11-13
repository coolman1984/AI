@echo off
rem ===== NERP - switch the user logon ON (user + password) =====
cd /d "%~dp0.."
if not exist data mkdir data
(echo login)> "data\login_on.flag"
echo.
echo  User logon is now ON. Close NERP (power button) and start it again.
echo  Demo users: ADMIN / admin, SALES1 / sales1 ... (password = user name in small letters)
echo.
pause
