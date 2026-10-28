# Discrepancy Root Cause Analysis (RCA) — Logic & Guide

## 1. Overview
The **Discrepancy Reason & Scenario Analytics** tab categorizes failed ServiceNow Data Certification tasks by inspecting their **description** and **short description** fields. Instead of looking at raw text individually, it automatically groups failures into **8 root-cause scenarios** based on predefined keyword clusters.

---

## 2. How the Classification Logic Works (Step-by-Step)

```
[Failed Task / Discrepancy Description]
                   │
                   ▼
       Step 1: Text Cleaning
(strip whitespace, lowercase, remove punctuation)
                   │
                   ▼
     Step 2: Keyword Scanning
(scan text against 8 scenario keyword lists using word-boundary regex)
                   │
                   ▼
     Step 3: Best-Match Selection
(assign the scenario with the most matched keywords)
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
[Keywords Found]      [No Keywords Found]
         │                   │
Assigned to 1 of 8    Assigned to "Unclassified"
Standard Scenarios    (Ensures 0% data loss)
         │                   │
         └─────────┬─────────┘
                   ▼
       Step 4: Tag Metadata
(attach Category, Risk Level, Color, Actionable Next Step)
```

1. **Text Extraction**: The engine looks for text in `description`, `short_description`, `issue_description`, or linked `cert_task` notes.
2. **Keyword Matching**: It scans the text for specific keywords using word-boundary regular expressions (`\bkeyword\b`).
3. **Best Match Selection**: If multiple keywords match, the scenario with the highest count of matched keywords wins.
4. **Enrichment**: Each record is tagged with:
   - **Scenario Name**: Specific failure scenario.
   - **Category**: High-level grouping (e.g., Data Completeness, Lifecycle).
   - **Risk Level**: `Critical`, `High`, `Medium`, or `Low`.
   - **Matched Keywords**: The exact keyword(s) found in that text.
   - **Recommended Action**: The operational remediation step.
5. **Fallback Handling**: If a description has no matching keywords, it is marked as `Unclassified / Custom Discrepancy` so no data is ever lost.

---

## 3. The 8 Failure Scenarios & Keywords

| # | Failure Scenario | Risk Level | Trigger Keywords | Operational Action |
|---|---|---|---|---|
| 1 | **Missing / Unassigned Mandatory Data** | High | `missing`, `empty`, `blank`, `null`, `unassigned`, `not populated`, `no owner`, `no manager`, `no cost center` | Enforce mandatory field validation rules and assign custodian. |
| 2 | **Stale / Obsolete / Decommissioning Gaps** | High | `stale`, `retired`, `decommission`, `decommissioned`, `inactive`, `obsolete`, `dormant`, `legacy`, `sunset`, `shut down` | Verify physical state and retire the CI in CMDB. |
| 3 | **Attribute Value Mismatch & Inaccuracy** | Medium | `mismatch`, `incorrect`, `wrong`, `inconsistent`, `differs`, `does not match`, `discrepancy`, `out of sync` | Reconcile against source system (SAP, HR) and update attribute. |
| 4 | **Naming & Format Standard Violations** | Low | `format`, `syntax`, `naming`, `convention`, `pattern`, `invalid characters`, `invalid ip`, `hostname syntax` | Apply regex input masks to enforce naming patterns. |
| 5 | **Orphaned Records & Broken Relationships** | High | `orphan`, `unlinked`, `no parent`, `no relation`, `missing dependency`, `isolated`, `broken link` | Map CI to its parent Application Service in CMDB. |
| 6 | **Unauthorized Changes & Configuration Drift** | Critical | `unauthorized`, `out of band`, `unapproved`, `no change ticket`, `unauthorized change`, `drift` | Investigate unapproved change and enforce Change Control. |
| 7 | **Duplicate / Redundant Configuration Items** | Medium | `duplicate`, `repeated`, `redundant`, `collision`, `already exists`, `twin`, `cloned` | Use CMDB de-duplication wizard to merge/archive duplicates. |
| 8 | **Access, Role & Custodian Governance** | Medium | `access`, `permission`, `unauthorized user`, `role vacant`, `certifier unable`, `privilege`, `left company` | Reassign certification task to an active custodian. |
| 9 | **Unclassified / Custom Discrepancy** | Low | *(Fallback for descriptions with no match)* | Review task notes and add new keywords to taxonomy. |

---

## 4. Dynamic Keyword Discovery Logic
In addition to the 8 predefined scenarios, the engine runs a **dynamic tokenizer**:
- It extracts all words with 3+ letters across all descriptions.
- Filters out common English stopwords (`the`, `and`, `was`, `for`, `with`, etc.) and generic words (`task`, `cmdb`, `ci`).
- Ranks the most frequent remaining words to surface **emerging keywords** that may need new rules in the future.

---

## 5. Dashboard Visuals & Usage

1. **KPI Cards**: Shows total volume, percentage classified (coverage), top failure driver, and count of high/critical risk issues.
2. **Filter Controls**: Filter by Scenario, Risk Level, Application, or type any custom word in the live search box.
3. **Horizontal Bar Chart**: Ranks scenarios by volume, color-coded by risk severity.
4. **Donut Chart**: Displays high-level category percentage shares.
5. **Application Stacked Bar**: Identifies which applications have the highest volume of each failure type.
6. **Top Keywords Chart**: Displays the 12 most frequent words found in descriptions.
7. **Quarter Shift Table**: Compares scenario volume and share shifts across campaigns (e.g., Q4 vs Q2).
8. **Record Inspector**: Filterable table showing the discrepancy number, application, matched keywords, full description, and recommended action. Includes 1-click CSV download.
