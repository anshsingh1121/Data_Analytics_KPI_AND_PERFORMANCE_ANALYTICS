import logging
import os
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

class DeadlineMonitor:
    """
    Automated monitor for detecting tasks approaching deadlines, overdue tasks,
    and operational SLA risks.
    """

    def __init__(self, warning_window_days: int = 5):
        self.warning_window_days = warning_window_days

    def monitor(self, tasks_df: pd.DataFrame, as_of_date: Optional[Any] = None) -> Dict[str, Any]:
        """
        Scans open certification tasks and flags:
        1. Overdue tasks (due_date < as_of_date)
        2. Near-deadline tasks (due_date between as_of_date and as_of_date + warning_window_days)
        3. Assignee risk exposure
        """
        if tasks_df is None or tasks_df.empty:
            logger.info("DeadlineMonitor: No tasks in scope.")
            return {"overdue_tasks": [], "near_deadline_tasks": [], "summary": {"overdue": 0, "near_deadline": 0, "total_open": 0}}

        state_col = 'state' if 'state' in tasks_df.columns else 'status'
        due_col = 'due_date' if 'due_date' in tasks_df.columns else None
        num_col = 'number' if 'number' in tasks_df.columns else 'sys_id'
        assignee_col = 'assigned_to' if 'assigned_to' in tasks_df.columns else 'certifier'
        app_col = 'cmdb_ci' if 'cmdb_ci' in tasks_df.columns else 'application'

        open_statuses = ["Open", "Work in Progress", "Pending Review", "Pending"]
        open_tasks = tasks_df[tasks_df[state_col].isin(open_statuses)].copy()

        if open_tasks.empty or due_col not in open_tasks.columns:
            return {"overdue_tasks": [], "near_deadline_tasks": [], "summary": {"overdue": 0, "near_deadline": 0, "total_open": len(open_tasks)}}

        as_of = pd.to_datetime(as_of_date) if as_of_date else pd.to_datetime('2026-10-23')
        open_tasks['due_dt'] = pd.to_datetime(open_tasks[due_col], errors='coerce')
        valid_open = open_tasks.dropna(subset=['due_dt']).copy()

        # Overdue tasks
        overdue_df = valid_open[valid_open['due_dt'] < as_of].copy()
        overdue_df['Days Overdue'] = ((as_of - overdue_df['due_dt']).dt.total_seconds() / 86400.0).round(1)
        overdue_df['Risk Level'] = overdue_df['Days Overdue'].apply(lambda d: "CRITICAL" if d > 5 else "HIGH")

        # Near-deadline tasks (within warning window)
        window_end = as_of + timedelta(days=self.warning_window_days)
        near_df = valid_open[(valid_open['due_dt'] >= as_of) & (valid_open['due_dt'] <= window_end)].copy()
        near_df['Days Remaining'] = ((near_df['due_dt'] - as_of).dt.total_seconds() / 86400.0).round(1)
        near_df['Risk Level'] = near_df['Days Remaining'].apply(lambda d: "HIGH" if d <= 2 else "MEDIUM")

        def build_records(df_in, extra_col):
            records = []
            for _, r in df_in.iterrows():
                records.append({
                    "task_id": str(r[num_col]),
                    "due_date": str(r['due_dt'].date()),
                    "application": str(r[app_col]) if app_col in r else "N/A",
                    "assigned_to": str(r[assignee_col]) if assignee_col in r else "N/A",
                    "status": str(r[state_col]),
                    extra_col: r[extra_col],
                    "risk_level": r['Risk Level']
                })
            return records

        overdue_records = build_records(overdue_df, 'Days Overdue')
        near_records = build_records(near_df, 'Days Remaining')

        summary = {
            "total_open": len(valid_open),
            "overdue": len(overdue_records),
            "near_deadline": len(near_records),
            "warning_window_days": self.warning_window_days,
            "as_of_date": str(as_of.date())
        }

        logger.info(f"Deadline Check completed: {summary['overdue']} overdue, {summary['near_deadline']} near deadline (within {self.warning_window_days} days).")
        return {
            "summary": summary,
            "overdue_tasks": overdue_records,
            "near_deadline_tasks": near_records
        }
