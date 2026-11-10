@echo off
rem TrueShape: double-click this file to set up (first time only) and start the app.
cd /d "%~dp0"
where python >nul 2>&1
if errorlevel 1 (
  echo Python was not found. Install Python 3.9 or newer from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during setup. Then double-click this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Setting up TrueShape for the first time. This takes a minute...
  python -m venv .venv
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
".venv\Scripts\python.exe" run.py
pause
