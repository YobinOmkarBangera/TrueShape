"""
Start TrueShape:   python run.py      (Windows)
                   python3 run.py     (macOS / Linux)
The browser opens by itself. Stop the app with Ctrl+C.
"""
import socket
import sys
import threading
import webbrowser

if sys.version_info < (3, 9):
    sys.exit("TrueShape needs Python 3.9 or newer. You have Python " + sys.version.split()[0] + ".")

try:
    import uvicorn
    import fastapi, pandas, numpy, multipart  # noqa: F401
except ImportError as e:
    sys.exit("A package is missing (" + str(e) + ").\nRun this first:  python -m pip install -r requirements.txt")

HOST = "127.0.0.1"


def free_port(start=8000, tries=20):
    """Use 8000, or the next free port if something else is already using it."""
    for port in range(start, start + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((HOST, port)) != 0:
                return port
    sys.exit("Ports 8000-8019 are all busy. Close other apps and try again.")


if __name__ == "__main__":
    from backend.app import S
    S()                                      # load and score everything before the browser opens
    port = free_port()
    url = "http://%s:%d" % (HOST, port)
    print("TrueShape is running at " + url + "  (press Ctrl+C to stop)")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("backend.app:app", host=HOST, port=port, log_level="warning")
