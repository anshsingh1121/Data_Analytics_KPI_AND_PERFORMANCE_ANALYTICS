import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

@pytest.fixture
def mock_tasks_df():
    """Generates standard fixture tasks representing both cycles with known properties."""
    tasks = []
    # 100 sample tasks for fast deterministic unit tests
    # 70 closed complete, 10 closed incomplete, 5 cancelled, 10 open, 5 returned for rework
    base = datetime(2026, 10, 1)
    for i in range(100):
        t_id = f"task_{i:03d}"
        if i < 70:
            state = "Closed Complete"
            created = base + timedelta(days=i % 5)
            closed = created + timedelta(days=4)
            due = created + timedelta(days=5) # on time
        elif i < 80:
            state = "Closed Incomplete"
            created = base + timedelta(days=i % 5)
            closed = created + timedelta(days=8)
            due = created + timedelta(days=5) # late
        elif i < 85:
            state = "Cancelled"
            created = base + timedelta(days=i % 5)
            closed = None
            due = created + timedelta(days=5)
        elif i < 95:
            state = "Open"
            created = base + timedelta(days=i % 5)
            closed = None
            due = created + timedelta(days=5)
        else:
            state = "Returned for Rework"
            created = base + timedelta(days=i % 5)
            closed = None
            due = created + timedelta(days=5)

        tasks.append({
            "sys_id": t_id,
            "number": f"CERT{i:04d}",
            "state": state,
            "assigned_to": f"Certifier_{i % 5:02d}",
            "cmdb_ci": f"App_{i % 3:02d}",
            "sys_created_on": created.strftime('%Y-%m-%d %H:%M:%S'),
            "due_date": due.strftime('%Y-%m-%d %H:%M:%S'),
            "closed_at": closed.strftime('%Y-%m-%d %H:%M:%S') if closed else None,
            "u_certification_activity": "Q4-2026",
            "u_rework_count": 1 if state == "Returned for Rework" else 0
        })
    return pd.DataFrame(tasks)

@pytest.fixture
def mock_discrepancies_df():
    """Generates sample discrepancies linked to mock tasks."""
    discs = []
    base = datetime(2026, 10, 2)
    for i in range(20):
        t_id = f"task_{i:03d}"
        discs.append({
            "sys_id": f"disc_{i:03d}",
            "number": f"DISC{i:04d}",
            "u_certification_task": t_id,
            "u_issue_category": "Invalid Format" if i % 2 == 0 else "Missing Data",
            "u_field": "owner" if i % 2 == 0 else "cost_center",
            "u_status": "Resolved" if i < 15 else "Open",
            "sys_created_on": base.strftime('%Y-%m-%d %H:%M:%S'),
            "u_resolved_on": (base + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S') if i < 15 else None
        })
    return pd.DataFrame(discs)

@pytest.fixture
def illustrative_test_data():
    """
    Returns exact illustrative values from Section 13 of requirements:
    - Previous: 5000 tasks, 95% completion, 260 closure rate, 91% on-time, 12% disc, 6% rework, 8 days avg time
    - Current: 5200 tasks, 97% completion, 310 closure rate, 96% on-time, 8% disc, 3% rework, 6 days avg time
    """
    return {
        "previous": {
            "total_tasks": 5000,
            "completion": 95.0,
            "daily_closure": 260.0,
            "on_time": 91.0,
            "discrepancy_rate": 12.0,
            "rework_rate": 6.0,
            "avg_completion_time": 8.0
        },
        "current": {
            "total_tasks": 5200,
            "completion": 97.0,
            "daily_closure": 310.0,
            "on_time": 96.0,
            "discrepancy_rate": 8.0,
            "rework_rate": 3.0,
            "avg_completion_time": 6.0
        },
        "daily_closure_days": [
            {"day": 1, "previous": 220, "current": 270, "diff": 50},
            {"day": 2, "previous": 240, "current": 300, "diff": 60},
            {"day": 3, "previous": 260, "current": 320, "diff": 60},
            {"day": 4, "previous": 280, "current": 340, "diff": 60},
            {"day": 5, "previous": 300, "current": 350, "diff": 50},
        ]
    }
