# KPI Definitions & Formula Catalog

This document defines the mathematical formulas, eligibility criteria, denominators, exclusions, and business interpretation for all 12 Data Certification KPIs.

---

### KPI 1 — Certification Completion %
- **Formula**: `Completion % = Successfully Certified Eligible Tasks / Total Eligible Assigned Tasks × 100`
- **Numerator**: Distinct count of eligible completed tasks (`state == 'Closed Complete'`).
- **Denominator**: Distinct count of total eligible tasks assigned to the cycle.
- **Exclusions**: Cancelled tasks (`state == 'Cancelled'`).
- **Desired Trend**: **Higher** (Target: ≥ 95.0%).

---

### KPI 2 — Daily Closure Rate
- **Formula**: `Daily Closure Rate = Tasks Completed During the Period / Working Days Elapsed`
- **Numerator**: Distinct count of completed tasks during the period.
- **Denominator**: Working days elapsed in the cycle (Monday–Friday, minus configured holidays).
- **Desired Trend**: **Higher** (Target: ≥ 300 tasks/day).

---

### KPI 3 — On-Time Completion %
- **Formula**: `On-Time Completion % = Tasks Completed On or Before Due Date / Completed Eligible Tasks With Valid Due Dates × 100`
- **Numerator**: Completed tasks where `closed_at <= due_date`.
- **Denominator**: Completed tasks with valid, non-null due dates.
- **Exclusions**: Incomplete tasks and tasks with missing due dates.
- **Desired Trend**: **Higher** (Target: ≥ 95.0%).

---

### KPI 4 — Average Completion Time
- **Formula**: `Average Completion Time = Average(Valid Completion Timestamp − Creation Timestamp)`
- **Numerator**: Sum of calendar days elapsed between `sys_created_on` and `closed_at`.
- **Denominator**: Completed tasks with valid timestamps.
- **Additional Metrics**: Median duration, minimum, and maximum duration.
- **Desired Trend**: **Lower** (Target: ≤ 6.0 days).

---

### KPI 5 — Discrepancy Rate
- **Formula**: `Discrepancy Rate = Certified Records With ≥1 Valid Linked Discrepancy / Certified Records in Scope × 100`
- **Numerator**: Distinct certified records with at least one linked discrepancy in `u_failed_data_certifications`.
- **Denominator**: Distinct certified records in scope.
- **Critical Note**: Count distinct records, not the raw count of discrepancy rows.
- **Desired Trend**: **Lower** (Target: ≤ 8.0%).

---

### KPI 6 — Data Accuracy / Pass Rate
- **Formula**: `Pass Rate = Certified Records Passing Defined Validation Without Discrepancy / Certified Records Evaluated × 100`
- **Numerator**: Certified records with zero discrepancies (`total_records - affected_records`).
- **Denominator**: Certified records evaluated.
- **Desired Trend**: **Higher** (Target: ≥ 92.0%).

---

### KPI 7 — Rejection / Rework Rate
- **Formula**: `Rework Rate = Eligible Tasks Returned for Rework / Eligible Tasks Submitted for Review × 100`
- **Numerator**: Tasks with `u_rework_count > 0` or in state `Returned for Rework`.
- **Denominator**: Total eligible tasks submitted for review.
- **Availability Rule**: If source system lacks rework indicators, marked unavailable (`N/A`) with an explanatory diagnostic.
- **Desired Trend**: **Lower** (Target: ≤ 3.0%).

---

### KPI 8 — Aging / Backlog
- **Formula**: `Task Age = As-of Timestamp − Task Creation Timestamp` (for open tasks).
- **Aging Buckets**:
  - `0–4 days`
  - `5–9 days`
  - `10–14 days`
  - `15+ days`
- **Desired Trend**: **Lower** (Target average age: ≤ 5.0 days).

---

### KPI 9 — Productivity per Certifier
- **Formula**: `Productivity = Eligible Tasks Completed by Certifier / Applicable Working Days`
- **Interpretation**: Measures throughput normalized across team members and elapsed working days. Avoids unfair ranking by raw totals.
- **Desired Trend**: **Higher** (Target: ≥ 12.0 tasks/certifier/day).

---

### KPI 10 — Last-Minute Closure %
- **Measure A (Near-Deadline Closure Share)**:
  `Completed Within Final N Days Before Due Date / Completed Tasks With Due Dates × 100` (Default N = 5 days).
- **Measure B (Near-Deadline Open Backlog)**:
  Count and table of open tasks whose due date falls within the next N days from analysis timestamp.
- **Desired Trend**: **Lower** (Target: ≤ 10.0%).

---

### KPI 11 — Exception Resolution Time
- **Formula**: `Exception Resolution Time = Valid Resolution Timestamp − Exception Creation Timestamp`
- **Population**: Resolved discrepancies in `u_failed_data_certifications`.
- **Additional Metrics**: Median turnaround, counts and aging of unresolved exceptions.
- **Desired Trend**: **Lower** (Target: ≤ 5.0 days).

---

### KPI 12 — Final SLA Achievement %
- **Formula**: `Final SLA Achievement % = Eligible Tasks Completed On or Before Final Cycle Deadline / Total Eligible Tasks Assigned to Cycle × 100`
- **Critical Distinction**: The denominator explicitly includes tasks that remain incomplete at cycle deadline. It is distinct from KPI 3 (On-Time Completion %).
- **Desired Trend**: **Higher** (Target: ≥ 95.0%).
