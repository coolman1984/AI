@echo off
rem ===== MM Core - put the icons (Dashboard, MM Core, MM Core Logon) on the desktop =====
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0icons\create_shortcuts.ps1"
echo.
pause
