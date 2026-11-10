#!/bin/bash
# TrueShape: double-click this file to set up (first time only) and start the app.
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 was not found. Install it from https://www.python.org/downloads/ and run this again."
  read -n 1 -s -r -p "Press any key to close."
  exit 1
fi
if [ ! -x ".venv/bin/python" ]; then
  echo "Setting up TrueShape for the first time. This takes a minute..."
  python3 -m venv .venv
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt
fi
.venv/bin/python run.py
