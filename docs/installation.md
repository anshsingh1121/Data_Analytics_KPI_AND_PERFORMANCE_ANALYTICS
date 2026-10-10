# Windows Installation & Operational Guide

This document provides full instructions for setting up and running the Data Certification KPI & Performance Analysis System on Windows.

---

## 1. Prerequisites

- **Operating System**: Windows 10, Windows 11, or Windows Server 2019/2022.
- **Python**: Version 3.11 or 3.12 (64-bit recommended).
- **Network**: Internet access for installing dependencies via `pip` (or an enterprise internal PyPI mirror).

---

## 2. Step-by-Step Installation

### Step 1: Open Windows Command Prompt or PowerShell
Navigate to the project root directory:
```bat
cd "c:\Users\Ansh Singh\OneDrive\Desktop\DATA CERTIFICATION KPI and PERFORMANCE ANALYTICS"
```

### Step 2: Create and Activate Virtual Environment
```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

### Step 3: Upgrade pip and Install Dependencies
```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Verify installation:
```bat
python -c "import streamlit, pandas, plotly, requests, openpyxl, pytest; print('All core packages successfully imported!')"
```

---

## 3. Running the Synthetic Demo

The application includes an offline demonstration dataset with 10,200 certification tasks and 1,060 discrepancies:

```bat
REM 1. Validate configuration files
python main.py validate-config

REM 2. Generate synthetic data files
python main.py generate-demo

REM 3. Execute the full analytics pipeline
python main.py pipeline --mode demo

REM 4. Execute test suite
pytest -v

REM 5. Launch Streamlit Dashboard
streamlit run src/dashboard/app.py
```

---

## 4. Scheduling Automated Deadline Checks

To run the automated deadline and SLA check every morning at 08:00 AM on Windows:

Using PowerShell (Run as Administrator):
```powershell
$Action = New-ScheduledTaskAction -Execute "$PWD\.venv\Scripts\python.exe" -Argument "main.py deadline-check" -WorkingDirectory "$PWD"
$Trigger = New-ScheduledTaskTrigger -Daily -At 8:00am
Register-ScheduledTask -TaskName "DataCert_Deadline_Monitor" -Action $Action -Trigger $Trigger -Description "Daily Data Certification SLA & Deadline Check"
```
