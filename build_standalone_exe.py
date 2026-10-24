"""
STANDALONE EXECUTABLE BUILD SCRIPT
==================================
Compiles the application into a standalone Windows desktop executable
distribution folder using PyInstaller.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def build():
    print("=" * 70)
    print("BUILDING STANDALONE EXECUTABLE APPLICATION")
    print("=" * 70)

    # Ensure clean dist/build folders
    dist_dir = PROJECT_ROOT / "dist"
    build_dir = PROJECT_ROOT / "build"
    spec_file = PROJECT_ROOT / "DataCertificationAnalytics.spec"

    if not spec_file.exists():
        print(f"[ERROR] Specification file not found: {spec_file}")
        return 1

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        str(spec_file)
    ]

    print(f"[*] Running PyInstaller build...")
    ret = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if ret.returncode != 0:
        print("[ERROR] PyInstaller compilation failed.")
        return ret.returncode

    app_dist = dist_dir / "DataCertificationAnalytics"
    if app_dist.exists():
        # Ensure runtime folders are initialized in dist
        (app_dist / "data" / "processed").mkdir(parents=True, exist_ok=True)
        (app_dist / "data" / "runs").mkdir(parents=True, exist_ok=True)
        (app_dist / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
        (app_dist / "reports").mkdir(parents=True, exist_ok=True)
        
        # Copy config folder
        if (PROJECT_ROOT / "config").exists():
            shutil.copytree(PROJECT_ROOT / "config", app_dist / "config", dirs_exist_ok=True)
            
        # Copy current processed data if available
        src_tasks = PROJECT_ROOT / "data" / "processed" / "cert_tasks_processed.csv"
        src_disc = PROJECT_ROOT / "data" / "processed" / "discrepancies_processed.csv"
        if src_tasks.exists():
            shutil.copy2(src_tasks, app_dist / "data" / "processed" / "cert_tasks_processed.csv")
        if src_disc.exists():
            shutil.copy2(src_disc, app_dist / "data" / "processed" / "discrepancies_processed.csv")

        # Copy .env.example
        if (PROJECT_ROOT / ".env.example").exists():
            shutil.copy2(PROJECT_ROOT / ".env.example", app_dist / ".env.example")
        elif (PROJECT_ROOT / ".env").exists():
            shutil.copy2(PROJECT_ROOT / ".env", app_dist / ".env.example")

        print("\n" + "=" * 70)
        print("STANDALONE APPLICATION BUILT SUCCESSFULLY!")
        print(f"Executable Location: {app_dist / 'DataCertificationAnalytics.exe'}")
        print("Non-technical users can simply double-click DataCertificationAnalytics.exe")
        print("to launch the dashboard in their browser.")
        print("=" * 70)
    return 0

if __name__ == "__main__":
    sys.exit(build())
