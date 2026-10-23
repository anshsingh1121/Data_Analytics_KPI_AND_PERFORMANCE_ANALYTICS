import logging
import pandas as pd
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class BacklogAnalyzer:
    """Analyzes the backlog of open tasks."""

    def analyze(self, tasks_df: pd.DataFrame, as_of_date: datetime) -> Dict[str, Any]:
        """Calculates backlog metrics."""
        if tasks_df.empty:
            return {}
            
        state_col = 'state' if 'state' in tasks_df.columns else ('status' if 'status' in tasks_df.columns else None)
        if not state_col:
            return {"total_open": 0}
            
        open_tasks = tasks_df[tasks_df[state_col].isin(["Open", "Work in Progress", "Pending", "Pending Review"])].copy()
        
        if open_tasks.empty:
            return {"total_open": 0}
            
        created_col = 'sys_created_on' if 'sys_created_on' in open_tasks.columns else ('created_at' if 'created_at' in open_tasks.columns else None)
        if created_col:
            open_tasks['created_dt'] = pd.to_datetime(open_tasks[created_col], errors='coerce')
            as_of_dt = pd.to_datetime(as_of_date)
            if hasattr(open_tasks['created_dt'].dt, 'tz') and open_tasks['created_dt'].dt.tz is not None:
                open_tasks['created_dt'] = open_tasks['created_dt'].dt.tz_localize(None)
            if hasattr(as_of_dt, 'tzinfo') and as_of_dt.tzinfo is not None:
                as_of_dt = as_of_dt.tz_localize(None)
            open_tasks['age_days'] = (as_of_dt - open_tasks['created_dt']).dt.total_seconds() / (24 * 3600)
        else:
            open_tasks['age_days'] = 0.0
        
        # Overdue
        due_col = 'due_date' if 'due_date' in open_tasks.columns else ('u_due_date' if 'u_due_date' in open_tasks.columns else None)
        if due_col:
            open_tasks['due_dt'] = pd.to_datetime(open_tasks[due_col], errors='coerce')
            as_of_dt = pd.to_datetime(as_of_date)
            if hasattr(open_tasks['due_dt'].dt, 'tz') and open_tasks['due_dt'].dt.tz is not None:
                open_tasks['due_dt'] = open_tasks['due_dt'].dt.tz_localize(None)
            if hasattr(as_of_dt, 'tzinfo') and as_of_dt.tzinfo is not None:
                as_of_dt = as_of_dt.tz_localize(None)
            overdue_count = len(open_tasks[open_tasks['due_dt'] < as_of_dt])
        else:
            overdue_count = 0
            
        # Breakdown by assigned_to
        cert_col = 'assigned_to' if 'assigned_to' in open_tasks.columns else ('certifier' if 'certifier' in open_tasks.columns else None)
        if cert_col:
            by_certifier = open_tasks[cert_col].value_counts().to_dict()
        else:
            by_certifier = {}
            
        # Oldest tasks
        id_col = 'sys_id' if 'sys_id' in open_tasks.columns else ('number' if 'number' in open_tasks.columns else open_tasks.columns[0])
        oldest = open_tasks.nlargest(5, 'age_days')[[id_col, 'age_days']]
        oldest_dict = oldest.to_dict('records')
        
        return {
            "total_open": len(open_tasks),
            "overdue_count": overdue_count,
            "avg_age_days": open_tasks['age_days'].mean(),
            "by_certifier": by_certifier,
            "oldest_tasks": oldest_dict
        }
