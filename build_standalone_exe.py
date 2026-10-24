"""
STANDALONE EXECUTABLE BUILD SCRIPT
==================================
Compiles the application into a standalone Windows desktop executable
distribution folder using PyInstaller.
"""

import os
import sys
import time
import shutil
import tempfile
import zipfile
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

def build():
    print("=" * 70)
    print("BUILDING STANDALONE EXECUTABLE APPLICATION")
    print("=" * 70)

    dist_dir = PROJECT_ROOT / "dist"
    spec_file = PROJECT_ROOT / "DataCertificationAnalytics.spec"

    if not spec_file.exists():
        print(f"[ERROR] Specification file not found: {spec_file}")
        return 1

    # Use a non-cloud local directory for assembly to prevent OneDrive sync file-locks on DLLs
    local_build_root = Path(tempfile.gettempdir()) / "DataCert_PyInstaller_Build"
    local_dist = local_build_root / "dist"
    local_work = local_build_root / "work"

    if local_build_root.exists():
        try:
            shutil.rmtree(local_build_root)
        except Exception:
            pass
    local_build_root.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        f"--distpath={local_dist}",
        f"--workpath={local_work}",
        str(spec_file)
    ]

    print(f"[*] Running PyInstaller compilation in isolated build area...")
    ret = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if ret.returncode != 0:
        print("[ERROR] PyInstaller compilation failed.")
        return ret.returncode

    app_source = local_dist / "DataCertificationAnalytics"
    app_target = dist_dir / "DataCertificationAnalytics"

    print("[*] Preparing distribution assets...")
    # Initialize runtime folders inside the built app
    (app_source / "data" / "processed").mkdir(parents=True, exist_ok=True)
    (app_source / "data" / "runs").mkdir(parents=True, exist_ok=True)
    (app_source / "data" / "snapshots").mkdir(parents=True, exist_ok=True)
    (app_source / "reports").mkdir(parents=True, exist_ok=True)

    # Copy config folder
    if (PROJECT_ROOT / "config").exists():
        shutil.copytree(PROJECT_ROOT / "config", app_source / "config", dirs_exist_ok=True)

    # Copy current processed data if available
    src_tasks = PROJECT_ROOT / "data" / "processed" / "cert_tasks_processed.csv"
    src_disc = PROJECT_ROOT / "data" / "processed" / "discrepancies_processed.csv"
    if src_tasks.exists():
        shutil.copy2(src_tasks, app_source / "data" / "processed" / "cert_tasks_processed.csv")
    if src_disc.exists():
        shutil.copy2(src_disc, app_source / "data" / "processed" / "discrepancies_processed.csv")

    # Copy .env.example
    if (PROJECT_ROOT / ".env.example").exists():
        shutil.copy2(PROJECT_ROOT / ".env.example", app_source / ".env.example")
    elif (PROJECT_ROOT / ".env").exists():
        shutil.copy2(PROJECT_ROOT / ".env", app_source / ".env.example")

    # Create quick-start README for non-technical users
    readme_text = """# Data Certification KPI & Performance Analytics (Standalone App)

## How to Run (Non-Technical Users)
1. Double-click DataCertificationAnalytics.exe
2. Your default web browser (Microsoft Edge or Google Chrome) will automatically open displaying the interactive dashboard.
3. No Python or terminal installation is required on this computer.

## How to Execute the Analytics Pipeline
1. Open the dashboard by double-clicking DataCertificationAnalytics.exe.
2. Go to the ServiceNow API & Integration tab.
3. Click "Execute Full Analytics Pipeline".
4. A new dedicated folder will be automatically created under:
   data/runs/run_YYYYMMDD_HHMMSS/
   containing both the raw ServiceNow records and the processed data.
5. Consolidated Excel and CSV reports are refreshed in the reports/ folder.
"""
    with open(app_source / "README.txt", "w", encoding="utf-8") as rf:
        rf.write(readme_text)

    # Create standalone ZIP archive directly from the clean isolated build
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dist_dir / "DataCertificationAnalytics_Standalone.zip"
    print(f"[*] Creating distribution ZIP archive at: {zip_path}...")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(app_source):
            for file in files:
                abs_f = Path(root) / file
                rel_f = abs_f.relative_to(app_source)
                zipf.write(abs_f, Path("DataCertificationAnalytics") / rel_f)

    # Sync into project dist directory
    if app_target.exists():
        for _ in range(5):
            try:
                shutil.rmtree(app_target)
                break
            except Exception:
                time.sleep(1)
    try:
        shutil.copytree(app_source, app_target, dirs_exist_ok=True)
    except Exception as ex:
        print(f"[NOTE] Mirrored to local folder with notice: {ex}")

    print("\n" + "=" * 70)
    print("STANDALONE APPLICATION BUILT SUCCESSFULLY!")
    print(f"Standalone Folder: {app_target}")
    print(f"Standalone ZIP:    {zip_path}")
    print(f"Executable:        {app_target / 'DataCertificationAnalytics.exe'}")
    print("Non-technical users can simply double-click DataCertificationAnalytics.exe")
    print("to launch the dashboard in their browser.")
    print("=" * 70)
    return 0

if __name__ == "__main__":
    sys.exit(build())
