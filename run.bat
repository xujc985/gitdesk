@echo off
setlocal
cd /d "%~dp0"
rem GitDesk launcher. Keep this file ANSI/ASCII for Windows cmd.exe.
python -c "import PySide6" >nul 2>nul
if errorlevel 1 goto install
goto launch

:install
echo [GitDesk] Installing Qt runtime, please wait...
python -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto failed
goto launch

:launch
where pythonw >nul 2>nul
if errorlevel 1 (
    python "%~dp0gitdesk.pyw" %*
) else (
    start "GitDesk" pythonw "%~dp0gitdesk.pyw" %*
)
exit /b 0

:failed
echo.
echo [GitDesk] Startup failed. Please check Python, pip and network.
echo Run this command for details: python "%~dp0main.py"
pause
exit /b 1