import os
import random
import uuid
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_synthetic_data(output_dir: str = 'data/synthetic'):
    """
    Generates realistic synthetic datasets for certification performance analysis.
    Reflects the exact business requirements:
    - Previous cycle (Q3-2026): 5,000 tasks (~95% completion, ~91% on-time, ~12% discrepancy, ~6% rework, ~8 days avg time)
    - Current cycle (Q4-2026): 5,200 tasks (~97% completion, ~96% on-time, ~8% discrepancy, ~3% rework, ~6 days avg time)
    Includes multiple applications, 25 certifiers, various issue categories, open & overdue backlogs, and near-deadline tasks.
    """
    os.makedirs(output_dir, exist_ok=True)
    random.seed(42)
    np.random.seed(42)

    cycles = ['Q3-2026', 'Q4-2026']
    num_tasks = {'Q3-2026': 5000, 'Q4-2026': 5200}
    discrepancy_rates = {'Q3-2026': 0.12, 'Q4-2026': 0.08}
    rework_rates = {'Q3-2026': 0.06, 'Q4-2026': 0.03}
    completion_rates = {'Q3-2026': 0.95, 'Q4-2026': 0.97}
    on_time_rates = {'Q3-2026': 0.91, 'Q4-2026': 0.96}

    applications = [
        'App-Finance', 'App-HR', 'App-CRM', 'App-ERP', 'App-Security', 
        'App-DataWarehouse', 'App-Compliance', 'App-Risk', 'App-Treasury', 
        'App-Audit', 'App-Legal', 'App-Marketing', 'App-Operations', 
        'App-IT-Infra', 'App-Analytics'
    ]

    certifiers = [f"Certifier_{i:02d}" for i in range(1, 26)]
    
    base_dates = {
        'Q3-2026': datetime(2026, 7, 1),
        'Q4-2026': datetime(2026, 10, 1)
    }

    cycle_deadlines = {
        'Q3-2026': datetime(2026, 9, 23),
        'Q4-2026': datetime(2026, 12, 23)
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
        avg_days = 8 if cycle == 'Q3-2026' else 6

        for i in range(n):
            task_id = str(uuid.uuid4())
            app = random.choice(applications)
            certifier = random.choice(certifiers)
            created_on = base_date + timedelta(days=random.randint(0, 15), hours=random.randint(8, 17))
            
            # Due date 14 days after creation
            due_date = created_on + timedelta(days=14)

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
                    # Completed between 1 and 14 days, centered around avg_days
                    days_taken = max(1, min(14, int(np.random.normal(avg_days, 2.0))))
                    closed_at = created_on + timedelta(days=days_taken, hours=random.randint(1, 8))
                    if closed_at > due_date:
                        closed_at = due_date - timedelta(hours=random.randint(2, 24))
                else:
                    # Late completion (1-5 days after due date)
                    closed_at = due_date + timedelta(days=random.randint(1, 5), hours=random.randint(1, 12))
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
                'sys_created_on': created_on.strftime('%Y-%m-%d %H:%M:%S'),
                'due_date': due_date.strftime('%Y-%m-%d %H:%M:%S'),
                'closed_at': closed_at.strftime('%Y-%m-%d %H:%M:%S') if closed_at else None,
                'u_certification_activity': cycle,
                'u_rework_count': random.randint(1, 3) if has_rework else 0
            })

            # Discrepancy generation linked by task_id
            if random.random() < disc_rate:
                disc_id = str(uuid.uuid4())
                issue_category = random.choice([
                    'Missing Data', 'Invalid Format', 'Stale Reference', 
                    'Inconsistent Value', 'Unauthorized Change', 'Duplicate Entry'
                ])
                field_name = random.choice(['owner', 'cost_center', 'department', 'manager', 'location', 'classification'])
                
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
                    'u_application': app,
                    'u_field': field_name,
                    'u_cmdb_ci': app,
                    'u_issue_category': issue_category,
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
