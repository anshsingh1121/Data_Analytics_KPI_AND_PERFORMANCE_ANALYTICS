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
            
        # Assuming normalized data where open states are "Open" or "Work in Progress"
        open_tasks = tasks_df[tasks_df['state'].isin(["Open", "Work in Progress", "Pending"])].copy()
        
        if open_tasks.empty:
            return {"total_open": 0}
            
        open_tasks['sys_created_on'] = pd.to_datetime(open_tasks['sys_created_on'])
        open_tasks['age_days'] = (pd.to_datetime(as_of_date) - open_tasks['sys_created_on']).dt.total_seconds() / (24 * 3600)
        
        # Overdue
        if 'due_date' in open_tasks.columns:
            open_tasks['due_date'] = pd.to_datetime(open_tasks['due_date'])
            overdue_count = len(open_tasks[open_tasks['due_date'] < pd.to_datetime(as_of_date)])
        else:
            overdue_count = 0
            
        # Breakdown by assigned_to
        if 'assigned_to' in open_tasks.columns:
            by_certifier = open_tasks['assigned_to'].value_counts().to_dict()
        else:
            by_certifier = {}
            
        # Oldest tasks
        oldest = open_tasks.nlargest(5, 'age_days')[['sys_id', 'age_days']]
        oldest_dict = oldest.to_dict('records')
        
        return {
            "total_open": len(open_tasks),
            "overdue_count": overdue_count,
            "avg_age_days": open_tasks['age_days'].mean(),
            "by_certifier": by_certifier,
            "oldest_tasks": oldest_dict
        }
