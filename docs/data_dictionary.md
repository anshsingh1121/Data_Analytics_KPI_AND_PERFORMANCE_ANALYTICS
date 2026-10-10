# Data Dictionary — Data Certification Tables & Fields

## 1. Primary Table A: `cert_task` (Certification Task)

This table tracks individual data certification tasks assigned to data owners, certifiers, and application stewards.

| Field Name | Type | Key Role | Description | Sample Value |
|---|---|---|---|---|
| `sys_id` | String (UUID) | Primary Key | Unique 32-character identifier in ServiceNow | `a8c9b3e10f...` |
| `number` | String | Business ID | Human-readable task tracking number | `CERT20260001` |
| `state` | String | Status | Current task workflow status (`Closed Complete`, `Open`, etc.) | `Closed Complete` |
| `assigned_to` | String | Dimension | Assigned steward or certifier responsible for review | `Certifier_01` |
| `cmdb_ci` | String | Dimension | Target application or Configuration Item evaluated | `App-Finance` |
| `sys_created_on` | Datetime | Timestamp | Date and time the certification task was generated | `2026-10-01 08:30:00` |
| `due_date` | Datetime | Timestamp | Due date by which certification must be completed | `2026-10-15 17:00:00` |
| `closed_at` | Datetime (Nullable) | Timestamp | Timestamp when the task was completed or closed | `2026-10-07 14:15:00` |
| `u_certification_activity` | String | Dimension | Certification cycle name / tracking tag | `Q4-2026` |
| `u_rework_count` | Integer | Metric | Number of times task was returned for rework/corrections | `0` |

### Status Mappings:
- **Completed Statuses**: `Closed Complete`, `Closed Incomplete`
- **Open / Backlog Statuses**: `Open`, `Work in Progress`, `Pending Review`
- **Exclusion Statuses**: `Cancelled`
- **Rework Statuses**: `Returned for Rework`, `Rework`

---

## 2. Table B: `u_failed_data_certifications` (Discrepancies & Failures)

This table stores data quality exceptions, discrepancy findings, and attribute validation failures detected during certification.

| Field Name | Type | Key Role | Description | Sample Value |
|---|---|---|---|---|
| `sys_id` | String (UUID) | Primary Key | Unique discrepancy identifier | `d7f1c2a04e...` |
| `number` | String | Business ID | Human-readable discrepancy tracking code | `DISC20260001` |
| `u_certification_task` | String (UUID) | Foreign Key | Verified link to `cert_task.sys_id` | `a8c9b3e10f...` |
| `u_application` | String | Dimension | Application associated with the failed record | `App-Finance` |
| `u_field` | String | Attribute | Configuration item attribute that failed validation | `cost_center` |
| `u_issue_category` | String | Category | Classification of the failure | `Invalid Format` |
| `u_status` | String | Status | Resolution state (`Resolved`, `Open`, `In Progress`) | `Resolved` |
| `sys_created_on` | Datetime | Timestamp | When the discrepancy was logged | `2026-10-02 09:00:00` |
| `u_resolved_on` | Datetime (Nullable) | Timestamp | When the exception was remediated | `2026-10-06 11:30:00` |
| `u_resolution_notes` | String (Nullable) | Audit | Remediation details from certifier | `Updated cost center to 4102.` |

### Common Failure Categories:
- `Missing Data`: Mandatory field blank or unpopulated.
- `Invalid Format`: Data did not match standard regex or mask.
- `Stale Reference`: Linked user, department, or location is inactive.
- `Inconsistent Value`: Cross-field validation failure.
- `Unauthorized Change`: Change detected without approved RFC.
- `Duplicate Entry`: Record conflicts with existing primary identity.
