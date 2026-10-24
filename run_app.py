"""
DATA CERTIFICATION KPI & PERFORMANCE ANALYTICS — STANDALONE APP ENTRYPOINT
==========================================================================
Entrypoint for the PyInstaller-frozen standalone desktop application.
Initializes runtime folders, auto-detects ports, launches the embedded
Streamlit engine, and opens the default browser automatically.
"""

import os
import sys
import time
import socket
import threading
import webbrowser
from pathlib import Path

# Resolve runtime base directory
if getattr(sys, 'frozen', False):
    # PyInstaller temp extracted root
    BASE_DIR = Path(sys._MEIPASS)
    # The directory where the .exe itself resides
    EXE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent
    EXE_DIR = BASE_DIR

# Set working directory to EXE_DIR so user outputs (data/runs, reports) persist next to exe
os.chdir(EXE_DIR)
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
if str(EXE_DIR) not in sys.path:
    sys.path.insert(0, str(EXE_DIR))

# Ensure required runtime folders exist next to the executable
(EXE_DIR / "data" / "processed").mkdir(parents=True, exist_ok=True)
(EXE_DIR / "data" / "runs").mkdir(parents=True, exist_ok=True)
(EXE_DIR / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
(EXE_DIR / "reports").mkdir(parents=True, exist_ok=True)

# Copy default config if not present next to exe
if (BASE_DIR / "config").exists() and not (EXE_DIR / "config").exists():
    import shutil
    try:
        shutil.copytree(BASE_DIR / "config", EXE_DIR / "config")
    except Exception:
        pass

def find_available_port(start_port: int = 8501, max_port: int = 8530) -> int:
    """Finds an open local port."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port

def wait_for_server_and_open_browser(port: int, timeout: int = 25):
    """Monitors server health and opens the browser."""
    import urllib.request
    url = f"http://127.0.0.1:{port}"
    health_url = f"{url}/_stcore/health"
    start_time = time.time()
    opened = False
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(health_url, headers={'User-Agent': 'DataCertApp'})
            with urllib.request.urlopen(req, timeout=1) as resp:
                if resp.status == 200:
                    webbrowser.open(url)
                    opened = True
                    break
        except Exception:
            time.sleep(0.4)
    if not opened:
        webbrowser.open(url)

if __name__ == "__main__":
    from streamlit.web import cli as stcli

    port = find_available_port(8501)
    
    app_script = BASE_DIR / "src" / "dashboard" / "app.py"
    if not app_script.exists():
        app_script = EXE_DIR / "src" / "dashboard" / "app.py"

    print("=" * 70)
    print("  DATA CERTIFICATION KPI & PERFORMANCE ANALYTICS — STANDALONE APP")
    print(f"  Starting engine on port {port}...")
    print(f"  Opening browser at http://127.0.0.1:{port}")
    print("=" * 70)

    # Launch browser opener thread
    threading.Thread(
        target=wait_for_server_and_open_browser,
        args=(port,),
        daemon=True
    ).start()

    sys.argv = [
        "streamlit",
        "run",
        str(app_script),
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none"
    ]
    sys.exit(stcli.main())
