import os
import random
import uuid
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_synthetic_data(output_dir: str = 'data/synthetic'):
    """
    Generates realistic synthetic datasets for certification performance analysis.
    Reflects the exact business requirements across all defined annual campaign quarters:
    - Q4-2026: Oct 5 - Oct 23, 2026 (5,200 tasks, ~97% completion, ~96% on-time, ~8% discrepancy)
    - Q2-2026: May 5 - May 22, 2026 (5,000 tasks, ~95% completion, ~91% on-time, ~12% discrepancy)
    - Q4-2025: Oct 6 - Oct 23, 2025 (4,800 tasks, ~94% completion, ~90% on-time, ~13% discrepancy)
    - Q2-2025: Apr 7 - Apr 25, 2025 (4,600 tasks, ~92% completion, ~88% on-time, ~15% discrepancy)
    Includes multiple applications, 25 certifiers, various issue categories, open & overdue backlogs, and near-deadline tasks.
    """
    os.makedirs(output_dir, exist_ok=True)
    random.seed(42)
    np.random.seed(42)

    cycles = ['Q4-2026', 'Q2-2026', 'Q4-2025', 'Q2-2025']
    num_tasks = {
        'Q4-2026': 5200,
        'Q2-2026': 5000,
        'Q4-2025': 4800,
        'Q2-2025': 4600
    }
    discrepancy_rates = {
        'Q4-2026': 0.08,
        'Q2-2026': 0.12,
        'Q4-2025': 0.13,
        'Q2-2025': 0.15
    }
    rework_rates = {
        'Q4-2026': 0.03,
        'Q2-2026': 0.06,
        'Q4-2025': 0.07,
        'Q2-2025': 0.08
    }
    completion_rates = {
        'Q4-2026': 0.97,
        'Q2-2026': 0.95,
        'Q4-2025': 0.94,
        'Q2-2025': 0.92
    }
    on_time_rates = {
        'Q4-2026': 0.96,
        'Q2-2026': 0.91,
        'Q4-2025': 0.90,
        'Q2-2025': 0.88
    }
    avg_days_map = {
        'Q4-2026': 6,
        'Q2-2026': 8,
        'Q4-2025': 8,
        'Q2-2025': 9
    }

    applications = [
        'App-Finance', 'App-HR', 'App-CRM', 'App-ERP', 'App-Security', 
        'App-DataWarehouse', 'App-Compliance', 'App-Risk', 'App-Treasury', 
        'App-Audit', 'App-Legal', 'App-Marketing', 'App-Operations', 
        'App-IT-Infra', 'App-Analytics'
    ]

    certifiers = [f"Certifier_{i:02d}" for i in range(1, 26)]
    
    base_dates = {
        'Q4-2026': datetime(2026, 10, 5),
        'Q2-2026': datetime(2026, 5, 5),
        'Q4-2025': datetime(2025, 10, 6),
        'Q2-2025': datetime(2025, 4, 7)
    }

    cycle_deadlines = {
        'Q4-2026': datetime(2026, 10, 23),
        'Q2-2026': datetime(2026, 5, 22),
        'Q4-2025': datetime(2025, 10, 23),
        'Q2-2025': datetime(2025, 4, 25)
    }

    max_creation_days = {
        'Q4-2026': 14,
        'Q2-2026': 13,
        'Q4-2025': 13,
        'Q2-2025': 14
    }

    tasks_data = []
    discrepancies_data = []

    for cycle in cycles:
        n = num_tasks[cycle]
        base_date = base_dates[cycle]
        deadline = cycle_deadlines[cycle]
        comp_rate = completion_rates[cycle]
        ontime_rate = on_time_rates[cycle]
        disc_rate = discrepancy_rates[cycle]
        rew_rate = rework_rates[cycle]
        avg_days = avg_days_map[cycle]
        max_d = max_creation_days.get(cycle, 14)

        for i in range(n):
            task_id = str(uuid.uuid4())
            app = random.choice(applications)
            certifier = random.choice(certifiers)
            created_on = base_date + timedelta(days=random.randint(0, max_d), hours=random.randint(8, 17))
            
            # SLA due date aligned with campaign deadline
            due_date = deadline - timedelta(days=random.randint(0, 3)) if random.random() < 0.3 else deadline

            # Determine status
            is_completed = (random.random() < comp_rate)
            is_cancelled = (not is_completed and random.random() < 0.2)
            has_rework = (random.random() < rew_rate)

            closed_at = None
            if is_completed:
                status = "Closed Complete"
                # On-time vs Late
                is_ontime = (random.random() < ontime_rate)
                if is_ontime:
                    days_taken = max(1, min(14, int(np.random.normal(avg_days, 2.0))))
                    closed_at = created_on + timedelta(days=days_taken, hours=random.randint(1, 8))
                    if closed_at > due_date:
                        closed_at = due_date - timedelta(hours=random.randint(2, 24))
                else:
                    # Late completion (1-4 days after due date)
                    closed_at = due_date + timedelta(days=random.randint(1, 4), hours=random.randint(1, 12))
            elif is_cancelled:
                status = "Cancelled"
            else:
                # Open or Work in Progress or Returned for Rework
                if has_rework:
                    status = "Returned for Rework"
                else:
                    status = random.choice(["Open", "Work in Progress", "Pending Review"])

            tasks_data.append({
                'sys_id': task_id,
                'number': f"CERT{20260000 + len(tasks_data) + 1}",
                'state': status,
                'assigned_to': certifier,
                'cmdb_ci': app,
                'short_description': f"Data Certification Review - {app} ({cycle})",
                'description': f"Certify CMDB configuration data, ownership, and operational attributes for {app} during {cycle} campaign.",
                'sys_created_on': created_on.strftime('%Y-%m-%d %H:%M:%S'),
                'due_date': due_date.strftime('%Y-%m-%d %H:%M:%S'),
                'closed_at': closed_at.strftime('%Y-%m-%d %H:%M:%S') if closed_at else None,
                'u_certification_activity': cycle,
                'u_rework_count': random.randint(1, 3) if has_rework else 0
            })

            # Discrepancy generation linked by task_id
            if random.random() < disc_rate:
                disc_id = str(uuid.uuid4())
                
                # The 22 Certified ServiceNow CMDB Audited Fields
                certified_fields = [
                    'u_access_reviewer', 'u_business_delegate', 'u_license_financial_owner',
                    'owned_by', 'managed_by', 'business_criticality', 'u_customer_money_mover',
                    'u_change_control', 'u_dr_strategy', 'u_hosting_strategy', 'support_group',
                    'assignment_group', 'install_status', 'u_end_of_life_date', 'u_version',
                    'application_type', 'u_asl_type', 'u_hardware_platform',
                    'u_source_code_location', 'u_user_interface', 'manufacturer', 'short_description'
                ]
                
                field_name = random.choice(certified_fields)
                
                if field_name == 'u_access_reviewer' and random.random() < 0.45:
                    issue_category = 'incorrect access reviewer'
                    chosen_desc = random.choice([
                        f"Discrepancy: incorrect access reviewer assigned for {app}; certifier is not authorized access reviewer.",
                        f"Incorrect access reviewer: Custodian left company or has inactive profile in Active Directory.",
                        f"Invalid access reviewer: Assigned reviewer role is vacant or unauthorized for access sign-off.",
                        f"Incorrect access reviewer: Custodian mismatch between IAM directory and CMDB application record."
                    ])
                    short_desc = f"incorrect access reviewer: {app} reviewer invalid or departed"
                elif field_name == 'u_access_reviewer':
                    issue_category = 'u_access_reviewer'
                    chosen_desc = random.choice([
                        f"Required field 'u_access_reviewer' is blank or unassigned in CMDB record.",
                        f"Missing access reviewer: No designated access reviewer specified during data certification check.",
                        f"Primary u_access_reviewer is empty or null for CI {app}.",
                        f"Unassigned custodian: u_access_reviewer not populated in application catalog."
                    ])
                    short_desc = f"u_access_reviewer: access reviewer missing on {app}"
                elif field_name == 'business_criticality':
                    issue_category = 'business_criticality'
                    chosen_desc = random.choice([
                        f"Criticality mismatch: business_criticality in CMDB differs from Business Impact Analysis (BIA) tier.",
                        f"Missing mandatory business_criticality tiering classification for CI {app}.",
                        f"Incorrect business_criticality: Marked Tier 3 but application handles core customer transactions.",
                        f"business_criticality discrepancy: Tier rating out of sync with enterprise architecture baseline."
                    ])
                    short_desc = f"business_criticality: tier rating discrepancy on {app}"
                elif field_name == 'u_customer_money_mover':
                    issue_category = 'u_customer_money_mover'
                    chosen_desc = random.choice([
                        f"Urgent SOX compliance gap: u_customer_money_mover flag uncertified or inconsistent with payment gateway audit.",
                        f"Missing value: u_customer_money_mover attribute is empty; requires financial transaction classification.",
                        f"u_customer_money_mover discrepancy: Application moves customer funds but flag is set to false.",
                        f"Customer funds movement audit: u_customer_money_mover requires compliance re-attestation."
                    ])
                    short_desc = f"u_customer_money_mover: funds movement audit gap on {app}"
                elif field_name == 'owned_by':
                    issue_category = 'owned_by'
                    chosen_desc = random.choice([
                        f"Application owner gap: owned_by attribute is blank or assigned to inactive personnel.",
                        f"owned_by discrepancy: Executive ownership not re-certified during annual campaign.",
                        f"Vacant owner: owned_by user has transitioned to a different division.",
                        f"Unassigned application custodian: owned_by is null for CI {app}."
                    ])
                    short_desc = f"owned_by: application owner missing or vacant on {app}"
                elif field_name == 'managed_by':
                    issue_category = 'managed_by'
                    chosen_desc = random.choice([
                        f"Technical manager discrepancy: managed_by engineering delivery lead not populated.",
                        f"managed_by vacant: Previous application manager reassigned to another business unit.",
                        f"Delivery leadership gap: managed_by requires active technical lead assignment.",
                        f"Inconsistent manager: managed_by record does not match IT organizational hierarchy."
                    ])
                    short_desc = f"managed_by: delivery manager unassigned on {app}"
                elif field_name == 'u_business_delegate':
                    issue_category = 'u_business_delegate'
                    chosen_desc = random.choice([
                        f"Business delegate missing: u_business_delegate is empty; alternate sign-off contact required.",
                        f"u_business_delegate discrepancy: Assigned business delegate has departed enterprise.",
                        f"Continuity risk: No secondary u_business_delegate configured for certification workflows."
                    ])
                    short_desc = f"u_business_delegate: delegate unassigned on {app}"
                elif field_name == 'u_license_financial_owner':
                    issue_category = 'u_license_financial_owner'
                    chosen_desc = random.choice([
                        f"License financial owner gap: u_license_financial_owner cost center budget owner not identified.",
                        f"u_license_financial_owner discrepancy: Financial cost center mismatch against SAP GL account.",
                        f"Budget owner vacant: u_license_financial_owner requires active corporate finance signatory."
                    ])
                    short_desc = f"u_license_financial_owner: financial owner gap on {app}"
                elif field_name == 'u_change_control':
                    issue_category = 'u_change_control'
                    chosen_desc = random.choice([
                        f"Change control governance discrepancy: u_change_control is unassigned; CAB review required.",
                        f"u_change_control violation: Application modified without approved change advisory process.",
                        f"Emergency change profile missing: u_change_control setting does not conform to enterprise policy."
                    ])
                    short_desc = f"u_change_control: change control governance gap on {app}"
                elif field_name == 'u_dr_strategy':
                    issue_category = 'u_dr_strategy'
                    chosen_desc = random.choice([
                        f"DR strategy discrepancy: u_dr_strategy specifies active-active but secondary site is decommissioned.",
                        f"Missing disaster recovery configuration: u_dr_strategy is unassigned in application catalog.",
                        f"u_dr_strategy gap: Recovery Time Objective (RTO) exceeds approved tier standard.",
                        f"Disaster recovery drift: u_dr_strategy out of sync with annual technical failover test drill."
                    ])
                    short_desc = f"u_dr_strategy: disaster recovery strategy gap on {app}"
                elif field_name == 'u_hosting_strategy':
                    issue_category = 'u_hosting_strategy'
                    chosen_desc = random.choice([
                        f"Hosting strategy mismatch: u_hosting_strategy indicates on-prem but workloads migrated to AWS.",
                        f"Missing hosting metadata: u_hosting_strategy unpopulated for cloud hybrid CI {app}.",
                        f"u_hosting_strategy discrepancy: Cloud provider hosting region differs from CMDB profile."
                    ])
                    short_desc = f"u_hosting_strategy: hosting strategy discrepancy on {app}"
                elif field_name == 'u_hardware_platform':
                    issue_category = 'u_hardware_platform'
                    chosen_desc = random.choice([
                        f"Hardware platform discrepancy: u_hardware_platform specifies legacy x86 architecture.",
                        f"Missing compute architecture: u_hardware_platform is null in server specification record.",
                        f"u_hardware_platform drift: Underlying hypervisor platform differs from cluster baseline."
                    ])
                    short_desc = f"u_hardware_platform: hardware platform gap on {app}"
                elif field_name == 'support_group':
                    issue_category = 'support_group'
                    chosen_desc = random.choice([
                        f"Support routing discrepancy: support_group points to disbanded L2 operations queue.",
                        f"Missing support group: support_group is empty; incident dispatch cannot be routed.",
                        f"support_group invalid: Assigned tier 2 support team has been merged into Global Operations."
                    ])
                    short_desc = f"support_group: operational support queue gap on {app}"
                elif field_name == 'assignment_group':
                    issue_category = 'assignment_group'
                    chosen_desc = random.choice([
                        f"Assignment group error: assignment_group not configured for primary incident routing.",
                        f"Inactive resolver: assignment_group queue is inactive or archived in ServiceNow ITSM.",
                        f"assignment_group discrepancy: Task assignment group differs from certified support model."
                    ])
                    short_desc = f"assignment_group: assignment group invalid on {app}"
                elif field_name == 'install_status':
                    issue_category = 'install_status'
                    chosen_desc = random.choice([
                        f"Install status gap: install_status marked operational but CI has been sunset / decommissioned.",
                        f"Stale lifecycle state: install_status shows installed but system has been shut down >90 days.",
                        f"install_status discrepancy: Operational state out of sync with discovery probe sensors."
                    ])
                    short_desc = f"install_status: lifecycle install status mismatch on {app}"
                elif field_name == 'u_end_of_life_date':
                    issue_category = 'u_end_of_life_date'
                    chosen_desc = random.choice([
                        f"End of life date discrepancy: u_end_of_life_date is past due but no retirement roadmap recorded.",
                        f"Missing sunset roadmap: u_end_of_life_date is unassigned for legacy vendor software.",
                        f"u_end_of_life_date audit: Commercial software version reached vendor end-of-support."
                    ])
                    short_desc = f"u_end_of_life_date: end of life date gap on {app}"
                elif field_name == 'u_version':
                    issue_category = 'u_version'
                    chosen_desc = random.choice([
                        f"Software version mismatch: u_version in CMDB differs from discovery build tag.",
                        f"Outdated release tag: u_version is empty or indicates unpatched legacy build.",
                        f"u_version discrepancy: Production deployed version deviates from certified release register."
                    ])
                    short_desc = f"u_version: software release version mismatch on {app}"
                elif field_name == 'application_type':
                    issue_category = 'application_type'
                    chosen_desc = random.choice([
                        f"Application type classification error: application_type marked COTS instead of in-house custom app.",
                        f"Missing archetype: application_type is unpopulated in application catalog register.",
                        f"application_type discrepancy: SaaS delivery model differs from configured package type."
                    ])
                    short_desc = f"application_type: archetype classification gap on {app}"
                elif field_name == 'u_asl_type':
                    issue_category = 'u_asl_type'
                    chosen_desc = random.choice([
                        f"ASL tier discrepancy: u_asl_type service level agreement not aligned with EA tiering.",
                        f"Missing service level: u_asl_type is blank for enterprise application {app}.",
                        f"u_asl_type mismatch: Service availability tier differs from business SLA agreement."
                    ])
                    short_desc = f"u_asl_type: application service level tier gap on {app}"
                elif field_name == 'u_user_interface':
                    issue_category = 'u_user_interface'
                    chosen_desc = random.choice([
                        f"User interface architecture gap: u_user_interface metadata missing from application catalog.",
                        f"u_user_interface discrepancy: Application marked Web UI but operates exclusively via REST API.",
                        f"Presentation tier drift: u_user_interface specification requires architecture update."
                    ])
                    short_desc = f"u_user_interface: UI architecture specification gap on {app}"
                elif field_name == 'u_source_code_location':
                    issue_category = 'u_source_code_location'
                    chosen_desc = random.choice([
                        f"Source code location gap: u_source_code_location Git repository link is invalid or empty.",
                        f"Repository URL broken: u_source_code_location points to decommissioned Bitbucket server.",
                        f"u_source_code_location audit: GitHub repository link required for automated security scans."
                    ])
                    short_desc = f"u_source_code_location: Git repository link missing on {app}"
                elif field_name == 'manufacturer':
                    issue_category = 'manufacturer'
                    chosen_desc = random.choice([
                        f"Vendor reconciliation gap: manufacturer does not match approved enterprise vendor master.",
                        f"Missing OEM vendor: manufacturer is blank for third-party commercial package {app}.",
                        f"manufacturer discrepancy: Software publisher name non-compliant with standard naming convention."
                    ])
                    short_desc = f"manufacturer: vendor master mismatch on {app}"
                else:  # short_description
                    issue_category = 'short_description'
                    chosen_desc = random.choice([
                        f"Missing summary description: short_description is blank or non-compliant with CMDB standards.",
                        f"short_description discrepancy: Summary text does not articulate business function for {app}.",
                        f"Catalog hygiene gap: short_description requires concise functional scope description."
                    ])
                    short_desc = f"short_description: application summary description missing on {app}"

                is_resolved = (random.random() < 0.88)
                created_disc = created_on + timedelta(days=random.randint(1, 3))
                resolved_disc = None
                if is_resolved:
                    res_days = max(1, int(np.random.normal(5 if cycle == 'Q4-2026' else 7, 2)))
                    resolved_disc = created_disc + timedelta(days=res_days)

                discrepancies_data.append({
                    'sys_id': disc_id,
                    'number': f"DISC{20260000 + len(discrepancies_data) + 1}",
                    'u_certification_task': task_id,
                    'assigned_to': certifier,
                    'u_application': app,
                    'u_field': field_name,
                    'u_cmdb_ci': app,
                    'u_issue_category': issue_category,
                    'short_description': short_desc,
                    'description': chosen_desc,
                    'u_status': 'Resolved' if is_resolved else 'Open',
                    'sys_created_on': created_disc.strftime('%Y-%m-%d %H:%M:%S'),
                    'u_resolved_on': resolved_disc.strftime('%Y-%m-%d %H:%M:%S') if resolved_disc else None,
                    'u_resolution_notes': f"Corrected {field_name} value according to source-of-truth master register." if is_resolved else None
                })

    df_tasks = pd.DataFrame(tasks_data)
    df_disc = pd.DataFrame(discrepancies_data)

    tasks_path = os.path.join(output_dir, 'cert_tasks.csv')
    disc_path = os.path.join(output_dir, 'discrepancies.csv')

    df_tasks.to_csv(tasks_path, index=False)
    df_disc.to_csv(disc_path, index=False)

    print(f"Generated synthetic cert_tasks: {len(df_tasks)} records -> {tasks_path}")
    print(f"Generated synthetic discrepancies: {len(df_disc)} records -> {disc_path}")

    return df_tasks, df_disc

if __name__ == '__main__':
    generate_synthetic_data()
