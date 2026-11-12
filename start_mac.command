#!/bin/bash
# TrueShape: double-click this file to set up (first time only) and start the app.
# Linux: run  bash start_mac.command
cd "$(dirname "$0")" || exit 1

stop() { echo; echo "$1"; read -n 1 -s -r -p "Press any key to close."; echo; exit 1; }

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || stop "Python 3.9 or newer was not found. Install it from https://www.python.org/downloads/ and run this again."

VENV=".venv"
if [ ! -f "$VENV/installed.txt" ]; then
  echo "Setting up TrueShape for the first time. This takes a minute or two..."
  "$PY" -m venv "$VENV" || stop "Could not create the setup folder. On Ubuntu or Debian, run: sudo apt install python3-venv"
  "$VENV/bin/python" -m pip install --upgrade pip >/dev/null 2>&1
  "$VENV/bin/python" -m pip install -r requirements.txt || stop "Setup did not finish. Check the internet connection and run this again."
  echo ok > "$VENV/installed.txt"
fi
"$VENV/bin/python" run.py
