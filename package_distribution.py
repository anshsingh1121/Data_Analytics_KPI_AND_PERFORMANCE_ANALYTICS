"""
CORPORATE PORTABLE DISTRIBUTION PACKAGER
========================================
Creates a clean, production-ready portable bundle of the Data Certification
KPI & Performance Analytics application containing only the mandatory production
files required on corporate systems.
"""

import os
import shutil
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DIST_DIR = PROJECT_ROOT / "dist_corporate"

MANDATORY_DIRS = [
    "src",
    "config",
    "data/processed",
    "data/runs",
    "data/snapshots",
    "reports"
]

MANDATORY_FILES = [
    "main.py",
    "app_launcher.py",
    "Launch_Data_Certification_Analytics.bat",
    "Launch_Silently.vbs",
    "requirements.txt",
    ".env.example"
]

EXCLUDE_PATTERNS = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".github",
    ".vscode",
    ".idea",
    "*.pyc",
    "*.pyo"
}

def clean_copytree(src: Path, dst: Path):
    """Copies a directory tree excluding bytecode and cache directories."""
    dst.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(src):
        # Exclude unwanted directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_PATTERNS and not d.startswith('.')]
        
        rel_root = Path(root).relative_to(src)
        target_dir = dst / rel_root
        target_dir.mkdir(parents=True, exist_ok=True)
        
        for f in files:
            if not f.endswith(('.pyc', '.pyo')) and not f.startswith('.'):
                shutil.copy2(Path(root) / f, target_dir / f)

def build_corporate_package():
    print("=" * 70)
    print("BUILDING CLEAN CORPORATE DISTRIBUTION BUNDLE")
    print("=" * 70)

    target_app_dir = DIST_DIR / "DataCertificationAnalytics"
    if target_app_dir.exists():
        shutil.rmtree(target_app_dir)
    target_app_dir.mkdir(parents=True, exist_ok=True)

    print("\n[1/4] Copying mandatory production directories...")
    # Copy src and config
    clean_copytree(PROJECT_ROOT / "src", target_app_dir / "src")
    clean_copytree(PROJECT_ROOT / "config", target_app_dir / "config")
    
    # Create clean data directories
    for d in ["data/processed", "data/runs", "data/snapshots", "reports"]:
        (target_app_dir / d).mkdir(parents=True, exist_ok=True)

    # Copy initial verified processed data if present
    processed_tasks = PROJECT_ROOT / "data" / "processed" / "cert_tasks_processed.csv"
    processed_disc = PROJECT_ROOT / "data" / "processed" / "discrepancies_processed.csv"
    if processed_tasks.exists():
        shutil.copy2(processed_tasks, target_app_dir / "data" / "processed" / "cert_tasks_processed.csv")
    if processed_disc.exists():
        shutil.copy2(processed_disc, target_app_dir / "data" / "processed" / "discrepancies_processed.csv")

    print("[2/4] Copying mandatory execution and launcher files...")
    for f in MANDATORY_FILES:
        src_f = PROJECT_ROOT / f
        if src_f.exists():
            shutil.copy2(src_f, target_app_dir / f)

    # If .env exists in root, copy it as .env.example or preserve corporate template
    env_example = target_app_dir / ".env.example"
    if not env_example.exists() and (PROJECT_ROOT / ".env").exists():
        shutil.copy2(PROJECT_ROOT / ".env", env_example)

    print("[3/4] Generating Quick Start User Guide...")
    readme_text = """# Data Certification KPI & Performance Analytics
### Enterprise Portable Application

This package contains the fully contained Data Certification KPI and Performance Analytics System.

## How to Launch (Non-Tech Users)
Simply **double-click** either:
- `Launch_Data_Certification_Analytics.bat` (Standard launcher)
- `Launch_Silently.vbs` (Silent launcher — opens directly in browser without console window)

The dashboard will open automatically in Microsoft Edge or Google Chrome.

## How to Execute the Analytics Pipeline
1. Open the dashboard.
2. Navigate to the **ServiceNow API & Integration** tab.
3. Click the **🚀 Execute Full Analytics Pipeline** button.
4. The system will:
   - Extract raw records from ServiceNow (or ingest cached data).
   - Automatically create a **new dedicated folder** in `data/runs/run_YYYYMMDD_HHMMSS/`.
   - Save both the fetched raw records and the validated/processed records into that run folder.
   - Generate the updated Excel and CSV reports in `reports/`.
   - Update the active dashboard and display the summary on screen.

## Mandatory Files in this Package
- `src/` : Analytics engine, KPI calculations, ServiceNow connectors, and Streamlit dashboard.
- `config/` : KPI definitions, campaign cycle dates, field mappings, and system settings.
- `data/` : Processed records, dedicated run archives (`data/runs/`), and snapshots.
- `reports/` : Consolidated executive Excel and CSV reports.
- `main.py` : Command-line pipeline interface.
- `app_launcher.py` : Native desktop application runner.
- `.env.example` : Template for ServiceNow credentials and SSL proxy configuration.
"""
    with open(target_app_dir / "README.md", "w", encoding="utf-8") as rf:
        rf.write(readme_text)

    print("[4/4] Creating distribution ZIP archive...")
    zip_path = DIST_DIR / "DataCertificationAnalytics_Portable.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(target_app_dir):
            for file in files:
                abs_f = Path(root) / file
                rel_f = abs_f.relative_to(DIST_DIR)
                zipf.write(abs_f, rel_f)

    print("\n" + "=" * 70)
    print("CORPORATE DISTRIBUTION PACKAGE CREATED SUCCESSFULLY!")
    print(f"Folder:  {target_app_dir}")
    print(f"Archive: {zip_path}")
    print("=" * 70)

if __name__ == "__main__":
    build_corporate_package()
