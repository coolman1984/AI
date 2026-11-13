@echo off
rem ===== NERP LIVE - your real company data (separate from the demo) =====
rem Database data\company.db, port 8083. It starts EMPTY and never gets demo data:
rem load your data with ZIMPORT (Excel workbooks). The demo stays in "Start NERP.bat".
cd /d "%~dp0"
set "MM_DB=%~dp0data\company.db"
where pythonw >nul 2>nul && (start "" pythonw "%~dp0run.py" --empty --port 8083 %* & exit /b 0)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0run.py" --empty --port 8083 %* & exit /b 0)
where python >nul 2>nul && (start "NERP LIVE server" /min python "%~dp0run.py" --empty --port 8083 %* & exit /b 0)
echo.
echo  Python was not found on this computer.
echo  Install Python 3 from python.org and tick "Add python.exe to PATH".
echo.
pause
