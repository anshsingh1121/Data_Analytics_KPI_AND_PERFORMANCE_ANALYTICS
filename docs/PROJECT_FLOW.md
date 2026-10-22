# Data Certification KPI & Performance Analytics — End-to-End Flow Guide

A brief, simple, and to-the-point guide explaining how the entire system works from end to end.

---

## 1. What Does This Project Do?

This system connects to **ServiceNow**, extracts **Data Certification Tasks** and **Discrepancies**, cleans and validates the data, calculates **12 audit-ready KPIs**, and presents the results in an interactive **Executive Dashboard** and **Excel/CSV Reports**.

---

## 2. The Two Operating Modes

| Mode | Configuration | What It Does |
| :--- | :--- | :--- |
| **Live Mode (Corporate)** | `APP_MODE=live` in `.env` | Connects directly to ServiceNow REST Table API, pulls real-time production records, and verifies corporate SSL certificates. |
| **Demo Mode (Offline)** | `APP_MODE=demo` in `.env` | Runs completely offline using sample data. No API credentials or internet needed. |

---

## 3. Data Sources (Two ServiceNow Tables)

1. **Table 1: `cert_task` (Certification Tasks)**
   - Records each item assigned to a certifier for validation.
   - Key fields: `sys_id` (Task ID), `number`, `state` (Status), `assigned_to` (Certifier), `cmdb_ci` (Application/CI), `sys_created_on`, `due_date`, `closed_at`.

2. **Table 2: `u_failed_data_certifications` (Discrepancy Records)**
   - Records specific field-level failures or audit mismatches.
   - Key fields: `sys_id`, `u_certification_task` (Link to parent task), `u_field`, `u_issue_category`, `u_status` (Resolved/Open), `u_resolved_on`.

---

## 4. End-to-End Flow Pipeline (Step by Step)

```
[ServiceNow API]
       │
       ▼
 [1. Extraction]        --> Pulls batch records with offset pagination & SSL handling
       │
       ▼
 [2. Normalization]     --> Standardizes timestamps, column mappings, string cleaning
       │
       ▼
 [3. Validation]        --> Checks schema rules, date sequences (created < closed)
       │
       ▼
 [4. Relationships]     --> Accurately joins discrepancies to parent tasks by sys_id
       │
       ▼
 [5. Campaign Filter]   --> Strictly validates date boundaries for annual quarters
       │
       ▼
 [6. KPI Calculation]   --> Computes all 12 KPIs, working days, and trend comparisons
       │
       ▼
 [7. Data Storage]      --> Caches processed CSVs & logs run metadata to SQLite
       │
       ▼
 [8. Dashboard & Export]--> Renders Streamlit UI & exports consolidated Excel workbooks
```

### Explanation of Steps:
1. **Extraction (`src/extraction/`):** Connects to ServiceNow via REST API, paginates through records, and handles corporate proxies and custom SSL certificates.
2. **Normalization (`src/data_processing/normalizer.py`):** Converts timestamps to UTC, trims text, and aligns raw table names to standard business names.
3. **Validation (`src/data_processing/validator.py`):** Separates valid records from invalid ones (e.g., checks that close dates are not earlier than creation dates).
4. **Relationship Resolver (`src/data_processing/relationships.py`):** Maps discrepancy records to their exact parent certification tasks using `u_certification_task = cert_task.sys_id`.
5. **Date-Wise Campaign Assignment (`src/analytics/cycle_manager.py`):** Strictly filters tasks into their exact business quarter windows based on creation dates.
6. **KPI Engine (`src/analytics/kpi_engine.py`):** Evaluates completion rates, SLAs, certifier turnaround times, and discrepancy rates.
7. **Storage (`src/storage/`):** Saves audit snapshots in Parquet format, logs run timestamps into SQLite (`run_history.sqlite`), and caches clean data in `data/processed/`.
8. **Dashboard & Exporters (`src/dashboard/` & `src/reporting/`):** Powers the browser dashboard and produces formatted multi-tab Excel files.

---

## 5. Defined Campaign Quarters (Date-Wise)

The system strictly validates records against these business campaign date ranges:

- **2026 Campaigns:**
  - **Q4 2026:** Oct 5, 2026 – Oct 23, 2026 (15 working days)
  - **Q1 2026:** May 5, 2026 – May 22, 2026 (14 working days)
- **2025 Campaigns:**
  - **Q4 2025:** Oct 6, 2025 – Oct 23, 2025 (14 working days)
  - **Q1 2025:** Apr 7, 2025 – Apr 25, 2025 (15 working days)

---

## 6. The 12 Core KPIs at a Glance

| # | KPI Name | Simple Meaning |
| :---: | :--- | :--- |
| **1** | **Certification Completion %** | Percentage of eligible tasks that are completed. |
| **2** | **Daily Closure Rate** | Average number of tasks closed per business working day. |
| **3** | **On-Time Completion %** | Percentage of completed tasks finished on or before their due date. |
| **4** | **Average Completion Time** | Average business days taken from task creation to closure. |
| **5** | **Discrepancy Rate** | Percentage of tasks that flagged at least one data failure. |
| **6** | **Data Accuracy / Pass Rate** | Inverse of discrepancy rate (records evaluated with zero issues). |
| **7** | **Rejection / Rework Rate** | Tasks returned to certifiers due to rework. |
| **8** | **Open Backlog Tasks** | Number of tasks currently pending and their age. |
| **9** | **Productivity per Certifier** | Tasks completed per active certifier per day. |
| **10** | **Last-Minute Closure %** | Open tasks closed within 24 hours of deadline. |
| **11** | **Exception Resolution Time** | Average days taken to resolve raised discrepancies. |
| **12** | **Final SLA Achievement %** | Tasks completed on or before the final campaign deadline. |

---

## 7. Dashboard Navigation Pages

The Streamlit dashboard (`http://localhost:8501`) contains 11 dedicated pages:
1. **Executive Overview:** 5 headline KPI cards, completion progress bar, daily closure burn-down, and priority risks.
2. **2026: Q1 vs Q4 Comparison:** Dedicated single-page matrix comparing May 2026 vs October 2026 campaigns.
3. **2025: Q1 vs Q4 Comparison:** Dedicated single-page matrix comparing April 2025 vs October 2025 campaigns.
4. **All-Quarters Overview:** Complete multi-quarter comparison tracking table across 2025 and 2026.
5. **Certifier Productivity (Worst Performers):** Ranked roster (`#1, #2, #3...`) identifying certifiers with longest completion times and high open backlogs.
6. **Backlog & SLA Monitoring:** Aging bucket breakdown (`0-4d`, `5-9d`, `10-14d`, `15+d`), urgent deadline tasks (≤1d), and overdue escalations.
7. **Daily Performance:** Daily closure bar charts, cumulative closure line charts, and 7-day moving averages.
8. **Data Quality & Discrepancies:** Mismatch breakdown by application, field name, and issue category.
9. **Exception Resolution:** Open vs. resolved discrepancy turnaround times.
10. **Data & Pipeline Health:** Extraction history, SQLite execution logs, and data quality scores.
11. **Settings & API Setup:** Connection status and live ServiceNow credentials verification.

---

## 8. Essential Commands

All actions can be run from the terminal or PowerShell:

```powershell
# 1. Validate all configuration files
python main.py validate-config

# 2. Test ServiceNow API connection and SSL certificates
python main.py test-connection

# 3. Run the complete extraction and KPI pipeline
python main.py pipeline

# 4. Launch the interactive browser dashboard
streamlit run src/dashboard/app.py
```

---

## 9. Corporate Production Deployment Checklist

On corporate production machines:
1. Set `APP_MODE=live` and your ServiceNow credentials in `.env`.
2. Ensure you have the core `src/` modules, `config/` YAML files, and `main.py`.
3. The demo synthetic generator (`synthetic_generator.py`) and `tests/` are **not required** and can be safely omitted.
