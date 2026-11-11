@echo off
rem ===== MM Core Dashboard - the ERP dashboard in its own window =====
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "%~dp0dashboard.py" %* & exit /b 0)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0dashboard.py" %* & exit /b 0)
where python >nul 2>nul && (start "MM Core Dashboard" /min python "%~dp0dashboard.py" %* & exit /b 0)
echo.
echo  Python was not found on this computer.
echo  Install Python 3 from python.org and tick "Add python.exe to PATH".
echo.
pause
