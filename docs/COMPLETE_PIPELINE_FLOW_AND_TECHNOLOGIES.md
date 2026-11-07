# Complete Pipeline Flow, Technologies & KPI Analytics Specification

A clear, simple, and to-the-point guide documenting the entire end-to-end architecture, technology stack, dataset filtering, table referencing, and computation logic for all 12 Business KPIs.

---

## 1. Executive Summary & Core Objective

The **Data Certification KPI & Performance Analytics System** automates the end-to-end auditing of IT Configuration Items (CIs) in ServiceNow. It pulls certification tasks and discrepancy records, verifies data integrity, calculates **12 deterministic, audit-ready KPIs**, and presents actionable intelligence through interactive executive dashboards and formatted Excel reports.

### Key System Highlights:
- **Two Operating Modes**: 
  - **Live Mode**: Connects directly to enterprise ServiceNow Table API with corporate proxy and Windows SSL certificate auto-negotiation.
  - **Demo Mode**: Runs 100% offline using high-fidelity local test datasets (no network or credentials needed).
- **Deterministic & Explainable**: Pure mathematical computation using pandas/numpy — zero external AI black-box dependencies.
- **Strict Relationship Integrity**: Tasks and discrepancies are joined strictly on primary record keys (`sys_id`), preventing false matches.

---

## 2. End-to-End Technologies Used

| Category | Technology / Library | Purpose in This Project |
| :--- | :--- | :--- |
| **Core Language** | **Python 3.10+** | Base runtime for data ingestion, cleaning, analytics engine, and report generation. |
| **Web UI Dashboard** | **Streamlit (`>=1.28.0`)** | Interactive browser application providing 11 executive and operational analytical pages. |
| **Data Processing** | **Pandas (`>=2.1.0`)** | High-performance tabular data manipulation, filtering, joins, aggregation, and date parsing. |
| **Scientific Computing** | **NumPy** | Working day calendar calculations (`busday_count`), holiday exclusion, and vector math. |
| **Interactive Visuals** | **Plotly (`>=5.18.0`)** | Responsive charts: Daily burn-down bars, cumulative lines, boxplots, radar charts, and donut metrics. |
| **REST API Client** | **Requests (`>=2.31.0`)** | HTTP client for ServiceNow Table API (`/api/now/table/`) with exponential backoff and retry logic. |
| **Enterprise TLS / SSL** | **wincertstore / ssl / certifi** | Auto-extracts Windows OS Certificate Store CAs so corporate inspection proxies (Zscaler/Netskope) work without disabling TLS. |
| **Configuration** | **PyYAML (`>=6.0.1`)** & **python-dotenv** | Loads `.env` credentials and YAML configurations (`settings.yaml`, `kpi_definitions.yaml`, `certification_cycles.yaml`). |
| **Reporting / Excel** | **openpyxl (`>=3.1.2`)** | Generates multi-tab, auto-styled Excel workbooks with colored headers, borders, and number formatting. |
| **Persistence / Storage** | **SQLite (`sqlite3`)** & **Parquet (`pyarrow`)** | SQLite logs execution history (`run_history.sqlite`); Parquet saves compressed, immutable point-in-time audit snapshots. |
| **Automated Execution** | **PowerShell, Batch (`.bat`), VBScript (`.vbs`)** | One-click silent launch scripts (`Launch_Data_Certification_Analytics.bat`, `Launch_Silently.vbs`). |
| **Testing** | **Pytest (`>=7.4.0`)** | Automated unit and integration test suite covering SSL, pipeline flow, KPI math, and RCA logic. |
| **Version Control** | **Git & GitHub** | Distributed source versioning and remote backup repository. |

---

## 3. Complete End-to-End Pipeline Flow

The pipeline executes sequentially in **8 automated stages**:

```
 ┌────────────────────────────────────────────────────────┐
 │ 1. Ingestion: ServiceNow API / Offline Synthetic CSV  │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 2. Normalization: Timezones (UTC), Field Map, Stripping│
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 3. Data Validation: Quarantine Duplicates & Date Errors│
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 4. Relationship Resolution: Foreign Key Match (sys_id) │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 5. Campaign Assignment: Strict Date Window Filtering   │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 6. KPI Engine: Deterministic Computation of 12 Metrics │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 7. Storage: SQLite Execution Logs & Parquet Snapshots   │
 └───────────────────────────┬────────────────────────────┘
                             │
                             ▼
 ┌────────────────────────────────────────────────────────┐
 │ 8. Delivery: Multi-Tab Excel, CSVs, Streamlit UI       │
 └────────────────────────────────────────────────────────┘
```

### Detailed Step-by-Step Flow:

1. **Step 1: Configuration & Credential Initialization (`src/config/loader.py`)**
   - Reads `.env` for mode (`APP_MODE=live` or `demo`), API URL, and credentials.
   - Loads business YAML rules: KPI formulas, thresholds, target campaign dates, and field mappings.
   - Validates that date boundaries and required config keys are non-empty.

2. **Step 2: Data Extraction & Ingestion (`src/connectors/`, `src/extraction/`)**
   - **Live Mode**: Calls ServiceNow REST API using batch offset pagination (`sysparm_limit=1000`, `sysparm_offset`). Uses `sysparm_display_value=all` and automatically flattens `{value, display_value}` records.
   - **Demo Mode**: Loads pre-packaged CSV datasets (`data/synthetic/cert_tasks.csv` and `data/synthetic/discrepancies.csv`).
   - Corporate SSL certificates are negotiated automatically without compromising TLS security.

3. **Step 3: Normalization (`src/data_processing/normalizer.py`)**
   - Standardizes timestamp strings into ISO 8601 UTC datetimes (`sys_created_on`, `due_date`, `closed_at`, `u_resolved_on`).
   - Normalizes text values (strips whitespace, handles `null`, `nan`, empty strings).
   - Maps vendor column names to standardized canonical field names.

4. **Step 4: Quality Checks & Validation (`src/data_processing/validator.py`)**
   - **Missing Field Check**: Ensures mandatory primary keys (`sys_id`) and status (`state`) exist.
   - **Duplicate Detection**: Identifies and deduplicates records by `sys_id`.
   - **Chronological Sequence Check**: Flags and quarantines records where `closed_at < sys_created_on` (physically impossible dates).
   - Separates records into three clean buckets: `Valid`, `Invalid` (quarantined), and `Excluded` (e.g. cancelled).

5. **Step 5: Relationship Resolution (`src/data_processing/relationships.py`)**
   - Strictly links discrepancy rows to certification tasks using:
     $$\text{u\_failed\_data\_certifications.u\_certification\_task} = \text{cert\_task.sys\_id}$$
   - Identifies orphaned discrepancies (issues referencing a non-existent parent task).
   - Aggregates `discrepancy_count` onto parent tasks for fast downstream filtering.

6. **Step 6: Campaign Window Assignment & Date Filtering (`src/analytics/cycle_manager.py`)**
   - Evaluates each task's `sys_created_on` against designated business campaign dates.
   - Tags each task with its specific campaign quarter (e.g., `Q4-2026`, `Q2-2026`, `Q4-2025`, `Q2-2025`).
   - Imputes missing `due_date` values with the exact campaign deadline at 23:59:59.
   - Calculates the exact number of working days elapsed (excluding weekends and official holidays).

7. **Step 7: KPI Analytics Engine Execution (`src/analytics/kpi_engine.py`)**
   - Runs all 12 KPI calculation methods deterministically.
   - Records audit metadata for every metric: exact numerator, denominator, count of excluded records, target threshold, and data quality warnings.

8. **Step 8: Output Delivery & UI Presentation (`src/storage/`, `src/reporting/`, `src/dashboard/`)**
   - Archives raw and processed datasets into timestamped directories (`data/runs/run_YYYYMMDD_HHMMSS/`).
   - Saves run audit entry into SQLite (`data/processed/run_history.sqlite`).
   - Generates formatted, multi-tab Excel reports (`reports/Data_Certification_KPI_Report_latest.xlsx`).
   - Exports individual analytical CSV files (`reports/*.csv`).
   - Powers the 11-page interactive Streamlit dashboard (`streamlit run src/dashboard/app.py`).

---

## 4. Datasets, Schema & Filtering Logic

### 4.1 The Two Core ServiceNow Tables

| Table Business Name | ServiceNow Table Name | Role | Primary / Foreign Keys |
| :--- | :--- | :--- | :--- |
| **Table 1: Certification Tasks** | `cert_task` | Holds every certification work order assigned to a certifier. | **Primary Key**: `sys_id`<br>**Foreign Key to CMDB**: `cmdb_ci` |
| **Table 2: Discrepancy Records** | `u_failed_data_certifications` | Holds individual field-level audit failure items. | **Primary Key**: `sys_id`<br>**Foreign Key to Task**: `u_certification_task` |

### 4.2 Cross-Referencing & Linkage Rules
- **Rule 1 (Strict FK Join)**: Discrepancy records link to tasks strictly via `u_failed_data_certifications.u_certification_task == cert_task.sys_id`.
- **Rule 2 (No Application Name Joining)**: The system **never** joins tasks and discrepancies using application name or `cmdb_ci` alone. Because an application can undergo multiple certification cycles across different years, joining on application name causes massive cartesian multiplications and false discrepancy counts.
- **Rule 3 (Distinct Task Attribution)**: When computing task discrepancy rates, distinct task IDs (`sys_id`) are counted in the numerator, rather than raw discrepancy row counts (one task with 5 field failures is counted as 1 discrepant task).

### 4.3 Campaign Date Windows & Strict Filtering Waterfall

Campaign cycles are strictly bounded by configured business dates:

| Campaign Quarter | Season | Official Date Range | Working Days | Default Due Deadline |
| :---: | :---: | :---: | :---: | :---: |
| **Q4 2026** | Autumn | **Oct 5, 2026 – Oct 23, 2026** | 15 Working Days | `2026-10-23 23:59:59` |
| **Q2 2026 (Q1 Spring)** | Spring | **May 5, 2026 – May 22, 2026** | 14 Working Days | `2026-05-22 23:59:59` |
| **Q4 2025** | Autumn | **Oct 6, 2025 – Oct 23, 2025** | 14 Working Days | `2025-10-23 23:59:59` |
| **Q2 2025 (Q1 Spring)** | Spring | **Apr 7, 2025 – Apr 25, 2025** | 15 Working Days | `2025-04-25 23:59:59` |

#### Strict Campaign Window Filtering (No 3-Month Calendar Fallbacks):
When assigning tasks to a quarter or filtering during pipeline execution, the pipeline strictly respects configured dates:
1. **Strict Timestamp Boundary (Primary)**: Filters task `sys_created_on` between the exact `start_date` and `end_date` of the campaign window (e.g. May 5 – May 22, 2026 for Q2-2026).
2. **Exact Cycle Tag Match (Secondary)**: If filtering by column tags, only records matching the exact cycle identifier (`certification_cycle == 'Q2-2026'`) are admitted.
3. **Out-of-Campaign Strict Handling**: Any record whose creation date falls outside official campaign dates is tagged as `'Out of Campaign'`. The engine **strictly prohibits** and rejects any 3-month calendar math fallbacks (e.g. mapping June or January records to Q2 via `(month - 1) // 3 + 1`), guaranteeing absolute boundary integrity.

### 4.4 Working Days Calculation Logic
Working days elapsed are calculated using `numpy.busday_count`:
- Evaluates dates Monday through Friday.
- Excludes configured corporate public holidays (e.g. New Year's Day, Christmas).
- **Inclusive End Date**: Because `busday_count(start, end)` is half-open `[start, end)`, the engine checks if `end` is a business day; if so, it adds 1 to include the closing business day.

---

## 5. In-Depth Logic for All 12 Business KPIs

Every KPI is calculated deterministically with clear audit properties.

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE 12 CORE BUSINESS KPIS                               │
├───────────────────────────────┬───────────────────────────────┬─────────────────────────┤
│ 1. Certification Completion % │ 2. Daily Closure Rate         │ 3. On-Time Completion % │
│ 4. Average Completion Time    │ 5. Discrepancy Rate           │ 6. Data Accuracy Rate   │
│ 7. Rejection / Rework Rate    │ 8. Open Backlog Tasks         │ 9. Certifier Productiv. │
│ 10. Last-Minute Closure %     │ 11. Exception Resolution Time │ 12. Final SLA Achieve.  │
└───────────────────────────────┴───────────────────────────────┴─────────────────────────┘
```

---

### KPI 1: Certification Completion %
* **Simple Meaning**: What percentage of assigned tasks were successfully completed?
* **Mathematical Formula**:
  $$\text{Completion \%} = \frac{\text{Distinct Completed Tasks}}{\text{Total Distinct Eligible Assigned Tasks}} \times 100$$
* **Numerator**: Count of distinct tasks where `state == 'Closed Complete'`.
* **Denominator**: Count of distinct eligible assigned tasks in the campaign.
* **Exclusions**: Cancelled tasks (`state == 'Cancelled'` or `'canceled'`) are excluded from both numerator and denominator.
* **Thresholds**: Target $\ge 95.0\%$, Warning $90.0\%$, Critical $< 85.0\%$. Desired trend: **Higher**.
* **Edge Cases**: If denominator is 0, returns `0.0%` with an explanatory note.

---

### KPI 2: Daily Closure Rate
* **Simple Meaning**: On average, how many tasks does the organization close each working day?
* **Mathematical Formula**:
  $$\text{Daily Closure Rate} = \frac{\text{Total Tasks Completed During Period}}{\text{Working Days Elapsed}}$$
* **Numerator**: Count of all tasks closed during the period (`state in ['Closed Complete', 'Closed Incomplete']`).
* **Denominator**: Number of working business days elapsed in the campaign cycle (excluding weekends and holidays).
* **Thresholds**: Target $\ge 300.0\text{ tasks/day}$, Warning $250.0$, Critical $< 200.0$. Desired trend: **Higher**.
* **Edge Cases**: If working days elapsed $< 1$, denominator defaults to 1 to prevent division by zero.

---

### KPI 3: On-Time Completion %
* **Simple Meaning**: Out of the tasks that are finished, what percentage were done on or before their due date?
* **Mathematical Formula**:
  $$\text{On-Time Completion \%} = \frac{\text{Tasks Closed On or Before Due Date}}{\text{Completed Tasks with Valid Due Dates}} \times 100$$
* **Numerator**: Completed tasks where `closed_at <= due_date`.
* **Denominator**: Completed tasks having a valid, non-null `due_date`.
* **Exclusions**: 
  - Open tasks (not yet closed).
  - Tasks missing valid closure or due dates.
* **Fallback Logic**: If `due_date` is missing from source data, it is imputed with the campaign window end date at `23:59:59`.
* **Thresholds**: Target $\ge 95.0\%$, Warning $90.0\%$, Critical $< 85.0\%$. Desired trend: **Higher**.

---

### KPI 4: Average Completion Time
* **Simple Meaning**: How many days does it take on average to complete a task from start to finish?
* **Mathematical Formula**:
  $$\text{Average Completion Time} = \frac{\sum (\text{closed\_at} - \text{sys\_created\_on})\text{ in days}}{\text{Number of Valid Completed Tasks}}$$
* **Numerator**: Sum of calendar duration in fractional days:
  $$\text{Duration} = \frac{(\text{closed\_at} - \text{sys\_created\_on})\text{ in seconds}}{86,400}$$
* **Denominator**: Count of completed tasks with valid creation and completion timestamps.
* **Data Quality Filter**: Any record where `closed_at < sys_created_on` (negative duration) is quarantined as an invalid sequence and excluded from the calculation.
* **Additional Statistics Reported**: Median duration, Minimum days, Maximum days.
* **Thresholds**: Target $\le 6.0\text{ days}$, Warning $8.0\text{ days}$, Critical $> 10.0\text{ days}$. Desired trend: **Lower**.

---

### KPI 5: Discrepancy Rate
* **Simple Meaning**: What percentage of certified tasks had at least one data error or mismatch?
* **Mathematical Formula**:
  $$\text{Discrepancy Rate} = \frac{\text{Distinct Certified Tasks with }\ge 1\text{ Linked Discrepancy}}{\text{Total Distinct Certified Tasks in Scope}} \times 100$$
* **Numerator**: Distinct count of parent task IDs (`sys_id`) that exist in `u_failed_data_certifications.u_certification_task`.
* **Denominator**: Distinct count of certified tasks in scope (`cert_task.sys_id`).
* **Critical Rule**: Evaluates **distinct tasks**, not the raw count of discrepancy rows. For example, a single task with 6 field errors counts as 1 in the numerator.
* **Thresholds**: Target $\le 8.0\%$, Warning $12.0\%$, Critical $> 15.0\%$. Desired trend: **Lower**.

---

### KPI 6: Data Accuracy / Pass Rate
* **Simple Meaning**: What percentage of certified records were completely clean with zero errors?
* **Mathematical Formula**:
  $$\text{Data Accuracy Rate} = 100\% - \text{Discrepancy Rate} = \frac{\text{Tasks with Zero Linked Discrepancies}}{\text{Total Distinct Certified Tasks in Scope}} \times 100$$
* **Numerator**: Total tasks in scope minus tasks with linked discrepancies:
  $$\text{Passed Tasks} = \text{Total Evaluated} - \text{Distinct Discrepant Tasks}$$
* **Denominator**: Total certified tasks evaluated in scope.
* **Thresholds**: Target $\ge 92.0\%$, Warning $88.0\%$, Critical $< 85.0\%$. Desired trend: **Higher**.

---

### KPI 7: Rejection / Rework Rate
* **Simple Meaning**: What percentage of tasks had to be sent back to certifiers for rework?
* **Mathematical Formula**:
  $$\text{Rework Rate} = \frac{\text{Tasks with Rework Count } > 0 \text{ or State 'Returned for Rework'}}{\text{Total Tasks Submitted for Review}} \times 100$$
* **Numerator**: Tasks where `u_rework_count > 0` or `state in ['Returned for Rework', 'Rework']`.
* **Denominator**: Total tasks submitted for review.
* **Graceful Degradation Rule**: If the corporate ServiceNow instance does not track rework states or `u_rework_count`, the KPI engine flags this metric as `N/A` with an explanatory diagnostic note rather than throwing an error.
* **Thresholds**: Target $\le 3.0\%$, Warning $6.0\%$, Critical $> 10.0\%$. Desired trend: **Lower**.

---

### KPI 8: Open Backlog Tasks & Aging Distribution
* **Simple Meaning**: How many tasks are currently sitting open, and how old are they?
* **Mathematical Formula**:
  $$\text{Open Backlog Count} = \text{Count of Active Tasks where } \text{state} \in [\text{'Open'}, \text{'Work in Progress'}, \text{'Pending Review'}]$$
  $$\text{Task Age (days)} = \frac{\text{As-Of Date} - \text{sys\_created\_on}}{86,400\text{ seconds}}$$
* **Aging Buckets**:
  - `0–4 days` (Healthy / Normal)
  - `5–9 days` (Moderate Aging)
  - `10–14 days` (Critical Aging / Near Deadline)
  - `15+ days` (Overdue / High Risk)
* **Headline Metric**: Total open backlog task count (headline displays task count; average age and aging buckets are provided in detailed breakdown).
* **Thresholds**: Target $\le 50\text{ tasks}$, Warning $100\text{ tasks}$, Critical $> 200\text{ tasks}$. Desired trend: **Lower**.

---

### KPI 9: Productivity per Certifier
* **Simple Meaning**: How many tasks does each certifier finish per working day?
* **Mathematical Formula**:
  $$\text{Productivity} = \frac{\text{Total Completed Tasks}}{\text{Distinct Active Certifiers} \times \text{Applicable Working Days}}$$
* **Numerator**: Total tasks completed during the cycle.
* **Denominator**: Distinct assigned certifiers (`assigned_to`) multiplied by working days elapsed.
* **Why Normalized**: Normalizing by active certifiers and working days ensures fair team evaluations, regardless of team size or differing campaign durations.
* **Thresholds**: Target $\ge 12.0\text{ tasks/certifier/day}$, Warning $8.0$, Critical $< 5.0$. Desired trend: **Higher**.

---

### KPI 10: Last-Minute Closure %
* **Simple Meaning**: Are certifiers rushing to close tasks in the final 24 hours before the deadline?
* **Two-Part Measurement**:
  - **Part A (Near-Deadline Closure Share)**:
    $$\text{Last-Minute Closure \%} = \frac{\text{Tasks Closed Within 1 Day Prior to Due Date}}{\text{Completed Tasks with Valid Due Dates}} \times 100$$
    Where closure is within window: $0 \le (\text{due\_date} - \text{closed\_at}) \le 1\text{ day}$.
  - **Part B (Imminent Open Backlog)**: Count of active open tasks whose due date falls within the next 24 hours.
* **Thresholds**: Target $\le 10.0\%$, Warning $20.0\%$, Critical $> 30.0\%$. Desired trend: **Lower**.

---

### KPI 11: Exception Resolution Time
* **Simple Meaning**: When a data discrepancy is found, how many days does it take to fix and resolve it?
* **Mathematical Formula**:
  $$\text{Exception Resolution Time} = \frac{\sum (\text{u\_resolved\_on} - \text{sys\_created\_on})\text{ in days}}{\text{Number of Resolved Discrepancy Records}}$$
* **Population**: Valid records in `u_failed_data_certifications` where `u_status` or `state` is in `['Resolved', 'Closed']`.
* **Data Quality Filter**: Only considers non-negative durations where `u_resolved_on >= sys_created_on`.
* **Thresholds**: Target $\le 5.0\text{ days}$, Warning $8.0\text{ days}$, Critical $> 12.0\text{ days}$. Desired trend: **Lower**.

---

### KPI 12: Final SLA Achievement %
* **Simple Meaning**: Did the team achieve its overall commitment for the entire campaign workload by the final deadline?
* **Mathematical Formula**:
  $$\text{Final SLA Achievement \%} = \frac{\text{Tasks Completed On or Before Final Cycle Deadline}}{\text{Total Eligible Tasks Assigned to Cycle}} \times 100$$
* **Numerator**: Eligible tasks where `state == 'Closed Complete'` and `closed_at <= final_deadline`.
* **Denominator**: **All** eligible tasks assigned to the campaign cycle, **including tasks that were never finished** (incomplete backlog).
* **Crucial Distinction (KPI 3 vs KPI 12)**:
  - **KPI 3 (On-Time Completion %)**: Denominator is *only tasks that are already completed*. (Evaluates the punctuality of finished work).
  - **KPI 12 (Final SLA Achievement %)**: Denominator is the *total cycle workload*. Tasks left uncompleted directly lower this score. (Evaluates overall organizational delivery against the cycle deadline).
* **Thresholds**: Target $\ge 95.0\%$, Warning $90.0\%$, Critical $< 85.0\%$. Desired trend: **Higher**.

---

## 6. Discrepancy Root Cause Analysis (RCA) Engine

The system features an automated classification engine (`src/analytics/discrepancy_rca.py`) that organizes audit failures across **23 certified CMDB configuration fields** and **6 governance domains**:

```
                       ┌───────────────────────────────────────────────┐
                       │        6 AUDIT GOVERNANCE DOMAINS             │
                       └───────────────────────┬───────────────────────┘
          ┌─────────────────┬──────────────────┼─────────────────┬─────────────────┐
          ▼                 ▼                  ▼                 ▼                 ▼
   [Ownership &       [Risk, Governance  [Architecture &   [Support &        [Lifecycle &
   Custodianship]      & Compliance]       Hosting]         Operations]       Release]
   • u_access_reviewer • business_critic. • u_dr_strategy   • support_group   • install_status
   • incorrect rev.    • u_customer_money • u_hosting_strat • assignment_grp  • u_end_of_life
   • owned_by          • u_change_control • u_hardware_plat                   • u_version
   • managed_by
   • u_business_deleg.
   • u_license_fin_own
                                               │
                                               ▼
                                      [Application Baseline]
                                      • application_type  • u_asl_type
                                      • u_user_interface  • u_source_code_loc
                                      • manufacturer      • short_description
```

### RCA Decision Logic:
1. **Field-Based Match**: Evaluates `u_field` in `u_failed_data_certifications`.
2. **Access Reviewer Disambiguation**: When `u_field == 'u_access_reviewer'`, the engine checks notes for keywords (`left company`, `departed`, `unauthorized`, `wrong reviewer`) to distinguish between an unassigned reviewer (`u_access_reviewer`) and an invalid/departed person (`incorrect access reviewer`).
3. **Keyword / Regex Fallback**: If `u_field` is null, parses free text across `description` and `u_resolution_notes`.
4. **Enrichment**: Assigns risk severity (Critical, High, Medium, Low), domain rollup, and an actionable remediation playbook.

---

## 7. Storage, Run History & Report Formats

Every pipeline run produces persistent, auditable deliverables:

1. **Timestamped Archive Directory (`data/runs/run_YYYYMMDD_HHMMSS/`)**:
   - `raw_tasks_fetched.csv`: Exact raw payload from ServiceNow.
   - `raw_discrepancies_fetched.csv`: Exact raw discrepancy payload.
   - `cert_tasks_processed.csv`: Clean, normalized, validated task records.
   - `discrepancies_processed.csv`: Clean, linked discrepancy records.
   - `run_summary.json`: Metadata summary (row counts, run ID, status, execution duration).
2. **Active Working Cache (`data/processed/`)**:
   - Mirrored copies of the latest processed CSV files for immediate dashboard consumption.
   - `run_history.sqlite`: SQLite table tracking every historical run's timestamp, status, and record counts.
3. **Multi-Tab Excel Master Workbook (`reports/Data_Certification_KPI_Report_latest.xlsx`)**:
   - `2026 Spring vs Autumn`: Side-by-side comparison matrix for 2026.
   - `2025 Spring vs Autumn`: Side-by-side comparison matrix for 2025.
   - `All Quarters Overview`: 4-quarter historical trend table.
   - `Management Summary`: Executive 12-KPI summary table.
   - `Certifier Productivity`: Ranked roster of certifiers (worst performers prioritized).
   - `Daily Trends`: Day-by-day task closure breakdown.
   - `Backlog Analysis`: Aging bucket distribution.
   - `Discrepancies` & `Discrepancy RCA Scenarios`: Mismatch classifications and root cause actions.
   - `Data Quality`: Validation rates and quarantine log.

---

## 8. CLI Commands & Quick Reference

All pipeline operations can be executed from the terminal:

```powershell
# 1. Validate all configuration files and environment variables
python main.py validate-config

# 2. Test ServiceNow REST API connectivity and corporate SSL certificates
python main.py test-connection

# 3. Discover table schema and verify field mappings
python main.py discover-schema

# 4. Execute the complete pipeline (Live mode)
python main.py pipeline --mode live

# 5. Execute the complete pipeline using previously fetched local cache (Fast re-run)
python main.py pipeline --skip-fetch

# 6. Execute the complete pipeline in offline Demo mode
python main.py pipeline --mode demo

# 7. Launch the Streamlit interactive dashboard
streamlit run src/dashboard/app.py
```
