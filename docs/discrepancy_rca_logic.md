# Discrepancy Reason & Scenario Analytics — Enterprise Logic & Guide

## 1. Executive Overview
The **Discrepancy Reason & Scenario Analytics** engine categorizes ServiceNow Data Certification discrepancies and audit failures across all **23 certified CMDB configuration attributes and governance categories**:

1. `u_access_reviewer` (Access Reviewer Missing / Unassigned)
2. `incorrect access reviewer` (Invalid, Departing, or Unauthorized Access Reviewer)
3. `u_business_delegate` (Business Delegate Continuity)
4. `u_license_financial_owner` (License & Cost Center Financial Signatory)
5. `owned_by` (Primary Application / System Executive Owner)
6. `managed_by` (Delivery & Engineering Manager)
7. `business_criticality` (Business Impact Tiering & SLA Classification)
8. `u_customer_money_mover` (Customer Funds Movement SOX Compliance Flag)
9. `u_change_control` (Change Advisory Board & CAB Governance Profile)
10. `u_dr_strategy` (Disaster Recovery Architecture & Failover Standard)
11. `u_hosting_strategy` (Hosting Strategy & Cloud Infrastructure Fabric)
12. `u_hardware_platform` (Underlying Compute Platform Architecture)
13. `support_group` (L2 / L3 Operational Support Routing Queue)
14. `assignment_group` (Primary Incident & Task Assignment Queue)
15. `install_status` (Operational Lifecycle State vs CMDB Verification)
16. `u_end_of_life_date` (Vendor & Internal Software Sunset / EOL Date)
17. `u_version` (Deployed Software Release Version Baseline)
18. `application_type` (Application Archetype: COTS, Custom, SaaS, Hybrid)
19. `u_asl_type` (Application Service Level Agreement Tier)
20. `u_user_interface` (Presentation Layer Architecture)
21. `u_source_code_location` (Authoritative Version Control Git Repository URL)
22. `manufacturer` (Third-Party Software Vendor Master Reconciliation)
23. `short_description` (Application Summary & Purpose Documentation)

---

## 2. Governance Domains (High-Level Rollups)
The 23 audited attributes are structured into 6 enterprise governance domains:
- **Ownership & Custodianship**: `u_access_reviewer`, `incorrect access reviewer`, `owned_by`, `managed_by`, `u_business_delegate`, `u_license_financial_owner`
- **Risk, Governance & Compliance**: `business_criticality`, `u_customer_money_mover`, `u_change_control`
- **Architecture & Hosting**: `u_dr_strategy`, `u_hosting_strategy`, `u_hardware_platform`
- **Support & Operations**: `support_group`, `assignment_group`
- **Lifecycle & Release**: `install_status`, `u_end_of_life_date`, `u_version`
- **Application Baseline**: `application_type`, `u_asl_type`, `u_user_interface`, `u_source_code_location`, `manufacturer`, `short_description`

---

## 3. How the Classification Logic Works (Step-by-Step)

```
[Failed Certification Discrepancy]
                   │
                   ▼
  Step 1: Check Specific Audited Field (u_field)
  Does u_field match one of the certified attributes?
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
    [Yes: Field Match]   [No / Raw Free Text]
         │                   │
         ▼                   ▼
  Step 2A: Disambiguate      Step 2B: Full Regex &
  u_access_reviewer vs       Keyword Matching against
  incorrect access reviewer  all 23 categories
         │                   │
         └─────────┬─────────┘
                   ▼
  Step 3: Enrich with Enterprise Metadata
  (Domain, Risk Severity, Hex Color, Actionable Remediation)
```

1. **Specific Audited Field Detection**: If `u_field` contains an audited attribute name, the engine maps it with 100% confidence.
2. **Access Reviewer Disambiguation**: When `u_field == 'u_access_reviewer'`, the engine evaluates text notes for departure, invalidity, or vacant reviewer cues (`left company`, `ineligible`, `unauthorized`, `wrong reviewer`) to separate `incorrect access reviewer` from standard blank `u_access_reviewer`.
3. **Keyword & Regex Fallback**: If `u_field` is missing, the engine scans the combined text across `description`, `short_description`, `u_resolution_notes`, and task notes.
4. **Enrichment**: Every record receives category display name, governance domain, risk severity, recommended remediation playbook, and confidence score.

---

## 4. Complete Catalog of 23 Audited Categories

| # | Audited Category | Target Field | Governance Domain | Risk Level | Operational Remediation Playbook |
|---|---|---|---|---|---|
| 1 | **u_access_reviewer** | `u_access_reviewer` | Ownership & Custodianship | High | Designate and assign an active, certified employee custodian as primary Access Reviewer. |
| 2 | **incorrect access reviewer** | `u_access_reviewer` | Ownership & Custodianship | Critical | Urgent IAM review: reassign access certification authority from departed/ineligible personnel. |
| 3 | **u_business_delegate** | `u_business_delegate` | Ownership & Custodianship | Medium | Register a designated secondary business delegate for business continuity during sign-offs. |
| 4 | **u_license_financial_owner** | `u_license_financial_owner` | Ownership & Custodianship | Medium | Reconcile software license allocation and attach cost center financial owner for budget accountability. |
| 5 | **owned_by** | `owned_by` | Ownership & Custodianship | High | Confirm executive ownership sponsorship and register active VP/Director custodian in owned_by. |
| 6 | **managed_by** | `managed_by` | Ownership & Custodianship | High | Align technical service management hierarchy and assign responsible engineering delivery manager. |
| 7 | **business_criticality** | `business_criticality` | Risk, Governance & Compliance | Critical | Conduct formal Business Impact Analysis (BIA) and certify enterprise tiering classification. |
| 8 | **u_customer_money_mover** | `u_customer_money_mover` | Risk, Governance & Compliance | Critical | Urgent SOX & Risk verification: certify whether application initiates or routes customer monetary transfers. |
| 9 | **u_change_control** | `u_change_control` | Risk, Governance & Compliance | High | Enforce Change Advisory Board (CAB) governance profile and mandate formal change request linkage. |
| 10 | **u_dr_strategy** | `u_dr_strategy` | Architecture & Hosting | High | Validate disaster recovery tiering architecture and schedule annual technical failover test drill. |
| 11 | **u_hosting_strategy** | `u_hosting_strategy` | Architecture & Hosting | Medium | Align hosting deployment with enterprise cloud and data center hosting taxonomy. |
| 12 | **u_hardware_platform** | `u_hardware_platform` | Architecture & Hosting | Medium | Verify compute platform architecture and synchronize server specification attributes. |
| 13 | **support_group** | `support_group` | Support & Operations | Medium | Update ServiceNow support group routing to an active operational ITSM support team. |
| 14 | **assignment_group** | `assignment_group` | Support & Operations | Medium | Re-link default task assignment group to active organizational resolver group. |
| 15 | **install_status** | `install_status` | Lifecycle & Release | High | Synchronize CMDB operational status with verified physical and logical lifecycle state. |
| 16 | **u_end_of_life_date** | `u_end_of_life_date` | Lifecycle & Release | High | Record verified software/hardware sunset date and initiate scheduled migration roadmap. |
| 17 | **u_version** | `u_version` | Lifecycle & Release | Medium | Update deployed software release tag from build pipeline or discovery sensor. |
| 18 | **application_type** | `application_type` | Application Baseline | Low | Standardize application classification (COTS, Custom, SaaS, Hybrid) in service catalog. |
| 19 | **u_asl_type** | `u_asl_type` | Application Baseline | Medium | Confirm Application Service Level tiering agreement with Enterprise Architecture. |
| 20 | **u_user_interface** | `u_user_interface` | Application Baseline | Low | Document presentation layer architecture in application metadata catalog. |
| 21 | **u_source_code_location** | `u_source_code_location` | Application Baseline | Low | Link authoritative version control repository URL for audit traceability and security scans. |
| 22 | **manufacturer** | `manufacturer` | Application Baseline | Low | Reconcile third-party vendor name with approved enterprise vendor master catalog. |
| 23 | **short_description** | `short_description` | Application Baseline | Low | Provide concise, business-relevant application functional overview and scope. |

---

## 5. Dashboard Visuals & Capabilities

1. **Executive Metric Cards**: Total discrepancies, 23 categories monitored, primary failure driver, critical compliance risks, and resolution rate.
2. **Interactive Controls**: Filter by Governance Domain, Audited Category multiselect, Risk Severity, and live instant search.
3. **Discrepancy Breakdown by Category & Risk Severity**: Horizontal bar chart sorted by volume with percentage share callouts.
4. **Governance Domain Donut**: Visual share of defects across the 6 core pillars.
5. **Cross-Application Category Distribution**: Stacked horizontal bar chart for top enterprise applications.
6. **Top Failure Keyword Tokens**: Frequency analysis of extracted technical tokens.
7. **Quarter-over-Quarter Category Shift**: Volume and percentage point change between active and prior campaigns.
8. **Audited Category Health Matrix & Remediation Playbook**: Actionable guidance table for every category.
9. **Searchable Discrepancy Record Inspector**: Detailed record table with 1-click CSV export.
