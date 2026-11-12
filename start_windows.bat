@echo off
setlocal
rem TrueShape: double-click this file to set up (first time only) and start the app.
cd /d "%~dp0"
title TrueShape

rem Find a real Python 3.9 or newer: the "py" launcher first, then "python".
rem (Testing it skips the Microsoft Store placeholder that some PCs have.)
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

rem The setup lives outside this folder, so OneDrive or a USB stick never has to copy it.
set "VENV=%LOCALAPPDATA%\TrueShape\venv"
if not defined LOCALAPPDATA set "VENV=%~dp0.venv"
if exist "%VENV%\installed.txt" goto run

echo Setting up TrueShape for the first time. This takes a minute or two...
%PY% -m venv "%VENV%"
if errorlevel 1 goto setupfail
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto setupfail
echo ok>"%VENV%\installed.txt"

:run
"%VENV%\Scripts\python.exe" run.py
echo.
pause
exit /b 0

:nopython
echo Python 3.9 or newer was not found.
echo Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH" during setup.
echo Then double-click this file again.
pause
exit /b 1

:setupfail
echo.
echo Setup did not finish. Check the internet connection and double-click this file again.
echo If it keeps failing, delete this folder and try once more: %VENV%
pause
exit /b 1
