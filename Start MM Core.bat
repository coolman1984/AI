@echo off
rem ===== MM Core - one click start =====
rem Starts the server hidden in the background and opens the browser.
rem The server stops by itself when you close the browser tab.
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "%~dp0run.py" %* & exit /b 0)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0run.py" %* & exit /b 0)
where python >nul 2>nul && (start "MM Core server" /min python "%~dp0run.py" %* & exit /b 0)
echo.
echo  Python was not found on this computer.
echo  Install Python 3 from python.org and tick "Add python.exe to PATH".
echo.
pause
