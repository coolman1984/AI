@echo off
rem ===== NERP Ceramic example - a ready ceramic company (Nile Ceramics) =====
rem Database data\ceramic.db, port 8084. The first start builds it: the Excel example
rem docs\ceramic\NERP_Ceramic_Example.xlsx + the whole month of November (purchasing,
rem production, sales, payroll, closing). The demo and your LIVE system stay as they are.
cd /d "%~dp0"
set "MM_DB=%~dp0data\ceramic.db"
if not exist "%MM_DB%" (
  where python >nul 2>nul || goto nopython
  python "%~dp0tools\demo\ceramic_example.py" --system "%MM_DB%"
)
where pythonw >nul 2>nul && (start "" pythonw "%~dp0run.py" --empty --port 8084 %* & exit /b 0)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0run.py" --empty --port 8084 %* & exit /b 0)
where python >nul 2>nul && (start "NERP Ceramic server" /min python "%~dp0run.py" --empty --port 8084 %* & exit /b 0)
:nopython
echo.
echo  Python was not found on this computer.
echo  Install Python 3 from python.org and tick "Add python.exe to PATH".
echo.
pause
