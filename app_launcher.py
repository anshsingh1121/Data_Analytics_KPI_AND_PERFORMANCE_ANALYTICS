"""
DATA CERTIFICATION KPI & PERFORMANCE ANALYTICS — APPLICATION LAUNCHER
======================================================================
1-Click desktop launcher for launching the interactive dashboard in
any standard browser without requiring command-line or technical setup.
"""

import os
import sys
import time
import socket
import subprocess
import threading
import webbrowser
from pathlib import Path

# Resolve base directories
PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def find_available_port(start_port: int = 8501, max_port: int = 8530) -> int:
    """Finds an available local port starting from 8501."""
    for port in range(start_port, max_port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            if s.connect_ex(('127.0.0.1', port)) != 0:
                return port
    return start_port

def wait_for_server_and_open_browser(port: int, timeout: int = 25):
    """Monitors local server startup and opens the browser once ready."""
    import urllib.request
    url = f"http://127.0.0.1:{port}"
    health_url = f"{url}/_stcore/health"
    
    start_time = time.time()
    opened = False
    
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(health_url, headers={'User-Agent': 'DataCertLauncher'})
            with urllib.request.urlopen(req, timeout=1) as resp:
                if resp.status == 200:
                    webbrowser.open(url)
                    opened = True
                    break
        except Exception:
            time.sleep(0.4)
            
    if not opened:
        # Fallback open if health endpoint didn't respond in time
        webbrowser.open(url)

def main():
    print("=" * 70)
    print("  DATA CERTIFICATION KPI & PERFORMANCE ANALYTICS")
    print("  Desktop Application Launcher")
    print("=" * 70)

    # Ensure required data directories exist
    (PROJECT_ROOT / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "data" / "runs").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "reports").mkdir(parents=True, exist_ok=True)

    target_port = find_available_port(8501)
    app_script = PROJECT_ROOT / "src" / "dashboard" / "app.py"

    if not app_script.exists():
        print(f"[ERROR] Dashboard entry point not found at: {app_script}")
        input("Press Enter to exit...")
        sys.exit(1)

    print(f"[*] Starting local analytics engine on port {target_port}...")
    print(f"[*] Launching your web browser automatically at http://127.0.0.1:{target_port}")
    print("=" * 70)
    print("  DASHBOARD IS RUNNING")
    print(f"  URL: http://127.0.0.1:{target_port}")
    print("  To close the application, simply close this window.")
    print("=" * 70)

    # Start browser opener in background thread
    opener_thread = threading.Thread(
        target=wait_for_server_and_open_browser,
        args=(target_port,),
        daemon=True
    )
    opener_thread.start()

    # Launch Streamlit process
    streamlit_cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_script),
        f"--server.port={target_port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none"
    ]

    try:
        proc = subprocess.Popen(streamlit_cmd, cwd=PROJECT_ROOT)
        proc.wait()
    except KeyboardInterrupt:
        print("\n[*] Shutting down application gracefully...")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        print("[*] Application stopped.")

if __name__ == "__main__":
    main()
