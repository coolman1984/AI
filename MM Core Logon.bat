@echo off
rem ===== MM Core Logon - desktop client (like SAP Logon / SAP GUI) =====
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw "%~dp0gui\main.py" & exit /b 0)
where pyw >nul 2>nul && (start "" pyw -3 "%~dp0gui\main.py" & exit /b 0)
where python >nul 2>nul && (start "MM Core Logon" /min python "%~dp0gui\main.py" & exit /b 0)
echo.
echo  Python was not found on this computer.
echo  Install Python 3 from python.org (keep "tcl/tk and IDLE" ticked) and "Add python.exe to PATH".
echo.
pause
