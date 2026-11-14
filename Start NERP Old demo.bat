@echo off
rem ===== NERP - the older demo company (kitchen cabinets, steel) =====
rem Database data\mm_old_demo.db, port 8085. "Start NERP.bat" now opens the ceramic
rem example company; the first start moved the older demo database here.
cd /d "%~dp0"
set "MM_DB=%~dp0data\mm_old_demo.db"
where pythonw >nul 2>nul && (start "" pythonw "%~dp0run.py" --port 8085 %* & exit /b 0)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0run.py" --port 8085 %* & exit /b 0)
where python >nul 2>nul && (start "NERP old demo server" /min python "%~dp0run.py" --port 8085 %* & exit /b 0)
echo.
echo  Python was not found on this computer.
echo  Install Python 3 from python.org and tick "Add python.exe to PATH".
echo.
pause
