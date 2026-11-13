@echo off
rem ===== NERP - put the icons (Dashboard, NERP, NERP Logon) on the desktop =====
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0icons\create_shortcuts.ps1"
echo.
pause
