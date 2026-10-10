import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class KPIEngine:
    """
    Core Analytics Engine for Data Certification Performance.
    Calculates all 12 Business KPIs deterministically with complete audit metadata:
    numerator, denominator, eligibility, excluded counts, warnings, and breakdowns.
    """

    def __init__(self, kpi_config: Optional[Dict[str, Any]] = None, cycle_config: Optional[Dict[str, Any]] = None):
        self.kpi_config = kpi_config or {}
        self.cycle_config = cycle_config or {}

    def _to_dt(self, val: Any) -> Any:
        """Converts scalar or series to naive datetime for clean arithmetic."""
        if isinstance(val, pd.Series):
            s = pd.to_datetime(val, errors='coerce')
            if hasattr(s.dt, 'tz') and s.dt.tz is not None:
                return s.dt.tz_localize(None)
            return s
        elif val is not None:
            ts = pd.to_datetime(val)
            if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                return ts.tz_localize(None)
            return ts
        return None

    def _col(self, df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """Finds first matching column name from candidates."""
        for c in candidates:
            if c in df.columns:
                return c
        return None

    def _create_kpi_result(
        self,
        name: str,
        value: Optional[float],
        numerator: Optional[float],
        denominator: Optional[float],
        excluded_count: int,
        unit: str,
        desired_trend: str,
        available: bool = True,
        details: Any = None,
        warnings: Optional[List[str]] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Standardized KPI result dictionary."""
        return {
            "name": name,
            "value": round(float(value), 2) if value is not None and not np.isnan(value) else None,
            "numerator": int(numerator) if numerator is not None and not np.isnan(numerator) else None,
            "denominator": int(denominator) if denominator is not None and not np.isnan(denominator) else None,
            "excluded_count": int(excluded_count),
            "unit": unit,
            "desired_trend": desired_trend,
            "available": available,
            "calculation_timestamp": datetime.now(timezone.utc).isoformat(),
            "data_quality_warnings": warnings or [],
            "details": details or {},
            "notes": notes
        }

    # =========================================================================
    # KPI 1: Certification Completion %
    # Formula: Successfully Certified Eligible Tasks / Total Eligible Assigned Tasks * 100
    # =========================================================================
    def kpi_1_certification_completion(self, tasks_df: pd.DataFrame) -> Dict[str, Any]:
        """
        KPI 1: Certification Completion %
        Measures progress toward certifying all in-scope tasks. Cancelled tasks are excluded.
        """
        name = "Certification Completion %"
        unit = "%"
        desired_trend = "higher"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        id_col = self._col(tasks_df, ['sys_id', 'task_id', 'number']) or 'sys_id'

        exclude_statuses = ["Cancelled", "canceled"]
        completion_statuses = ["Closed Complete", "Closed Incomplete"]

        eligible = tasks_df[~tasks_df[state_col].isin(exclude_statuses)]
        completed = eligible[eligible[state_col].isin(completion_statuses)]
        
        excluded_count = len(tasks_df) - len(eligible)
        numerator = eligible[eligible[state_col] == 'Closed Complete'][id_col].nunique() if 'Closed Complete' in eligible[state_col].values else completed[id_col].nunique()
        denominator = eligible[id_col].nunique()
        remaining = denominator - completed[id_col].nunique()

        value = (numerator / denominator * 100.0) if denominator > 0 else 0.0

        details = {
            "completed_tasks": int(completed[id_col].nunique()),
            "total_eligible_tasks": int(denominator),
            "remaining_tasks": int(max(0, remaining)),
            "cancelled_excluded": int(excluded_count)
        }

        return self._create_kpi_result(name, value, numerator, denominator, excluded_count, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 2: Daily Closure Rate
    # Formula: Tasks Completed During the Period / Working Days Elapsed
    # =========================================================================
    def kpi_2_daily_closure_rate(self, tasks_df: pd.DataFrame, working_days_elapsed: int = 1) -> Dict[str, Any]:
        """
        KPI 2: Daily Closure Rate
        Average throughput of completed tasks per working day elapsed.
        """
        name = "Daily Closure Rate"
        unit = "tasks/day"
        desired_trend = "higher"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, working_days_elapsed, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        closed_col = self._col(tasks_df, ['closed_at', 'completed_at'])

        completed = tasks_df[tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"])]
        numerator = len(completed)
        days = max(1, working_days_elapsed)

        value = float(numerator) / days

        # Calculate daily breakdown if closed timestamp exists
        daily_breakdown = {}
        if closed_col and closed_col in completed.columns:
            try:
                completed_dates = pd.to_datetime(completed[closed_col], errors='coerce').dt.date
                daily_counts = completed_dates.value_counts().sort_index()
                daily_breakdown = {str(k): int(v) for k, v in daily_counts.items() if pd.notna(k)}
            except Exception as e:
                logger.warning(f"Failed to calculate daily closure breakdown: {e}")

        details = {
            "total_completed": numerator,
            "working_days_elapsed": days,
            "daily_closures": daily_breakdown
        }

        return self._create_kpi_result(name, value, numerator, days, 0, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 3: On-Time Completion %
    # Formula: Tasks Completed On or Before Due Date / Completed Eligible Tasks With Valid Due Dates * 100
    # =========================================================================
    def kpi_3_on_time_completion(self, tasks_df: pd.DataFrame) -> Dict[str, Any]:
        """
        KPI 3: On-Time Completion %
        Measures punctuality of completed tasks against assigned due date.
        """
        name = "On-Time Completion %"
        unit = "%"
        desired_trend = "higher"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        closed_col = self._col(tasks_df, ['closed_at', 'completed_at']) or 'closed_at'
        due_col = self._col(tasks_df, ['due_date']) or 'due_date'

        completed = tasks_df[tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"])].copy()
        if completed.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["No completed tasks"])

        valid = completed.dropna(subset=[due_col, closed_col]).copy()
        excluded_count = len(completed) - len(valid)

        if valid.empty:
            return self._create_kpi_result(name, None, 0, 0, excluded_count, unit, desired_trend, False, warnings=["No completed tasks with valid due date and completion date"])

        valid['due_dt'] = self._to_dt(valid[due_col])
        valid['closed_dt'] = self._to_dt(valid[closed_col])
        valid = valid.dropna(subset=['due_dt', 'closed_dt'])

        on_time = valid[valid['closed_dt'] <= valid['due_dt']]
        late = valid[valid['closed_dt'] > valid['due_dt']]

        numerator = len(on_time)
        denominator = len(valid)
        value = (numerator / denominator * 100.0) if denominator > 0 else 0.0

        details = {
            "on_time_count": numerator,
            "late_count": len(late),
            "valid_completed": denominator,
            "excluded_missing_dates": excluded_count
        }

        return self._create_kpi_result(name, value, numerator, denominator, excluded_count, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 4: Average Completion Time
    # Formula: Average(Valid Completion Timestamp - Creation Timestamp) in days
    # =========================================================================
    def kpi_4_avg_completion_time(self, tasks_df: pd.DataFrame) -> Dict[str, Any]:
        """
        KPI 4: Average Completion Time (days)
        Cycle time from creation to completion. Reports mean, median, min, max.
        """
        name = "Average Completion Time"
        unit = "days"
        desired_trend = "lower"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        created_col = self._col(tasks_df, ['sys_created_on', 'created_at']) or 'sys_created_on'
        closed_col = self._col(tasks_df, ['closed_at', 'completed_at']) or 'closed_at'

        completed = tasks_df[tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"])].copy()
        valid = completed.dropna(subset=[created_col, closed_col]).copy()
        excluded_count = len(completed) - len(valid)

        if valid.empty:
            return self._create_kpi_result(name, None, 0, 0, excluded_count, unit, desired_trend, False, warnings=["No tasks with valid creation and closure timestamps"])

        valid['created_dt'] = self._to_dt(valid[created_col])
        valid['closed_dt'] = self._to_dt(valid[closed_col])
        valid = valid.dropna(subset=['created_dt', 'closed_dt'])

        # Remove impossible date sequences where closed < created
        impossible = valid[valid['closed_dt'] < valid['created_dt']]
        if not impossible.empty:
            excluded_count += len(impossible)
            valid = valid[valid['closed_dt'] >= valid['created_dt']]

        if valid.empty:
            return self._create_kpi_result(name, None, 0, 0, excluded_count, unit, desired_trend, False, warnings=["All records had invalid date sequences"])

        durations_days = (valid['closed_dt'] - valid['created_dt']).dt.total_seconds() / 86400.0

        mean_val = durations_days.mean()
        median_val = durations_days.median()
        min_val = durations_days.min()
        max_val = durations_days.max()

        details = {
            "mean_days": round(float(mean_val), 2),
            "median_days": round(float(median_val), 2),
            "min_days": round(float(min_val), 2),
            "max_days": round(float(max_val), 2),
            "count_tasks": len(durations_days)
        }

        return self._create_kpi_result(name, mean_val, durations_days.sum(), len(durations_days), excluded_count, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 5: Discrepancy Rate
    # Formula: Certified Records With At Least One Valid Linked Discrepancy / Certified Records in Scope * 100
    # =========================================================================
    def kpi_5_discrepancy_rate(self, tasks_df: pd.DataFrame, disc_df: pd.DataFrame) -> Dict[str, Any]:
        """
        KPI 5: Discrepancy Rate %
        Numerator counts distinct certified records that have at least one valid discrepancy.
        """
        name = "Discrepancy Rate"
        unit = "%"
        desired_trend = "lower"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        task_id_col = self._col(tasks_df, ['sys_id', 'task_id']) or 'sys_id'
        denominator = tasks_df[task_id_col].nunique()

        if denominator == 0:
            return self._create_kpi_result(name, 0.0, 0, 0, 0, unit, desired_trend, True)

        if disc_df is None or disc_df.empty:
            return self._create_kpi_result(name, 0.0, 0, denominator, 0, unit, desired_trend, True, details={"affected_records": 0, "total_records": denominator})

        disc_task_col = self._col(disc_df, ['u_certification_task', 'linked_task']) or 'u_certification_task'

        # Link discrepancies to tasks in scope
        valid_tasks = set(tasks_df[task_id_col].dropna().unique())
        linked_disc = disc_df[disc_df[disc_task_col].isin(valid_tasks)]
        
        # Count DISTINCT affected tasks in numerator (not rows)
        numerator = linked_disc[disc_task_col].nunique()
        value = (numerator / denominator * 100.0) if denominator > 0 else 0.0

        details = {
            "affected_records": numerator,
            "total_records_in_scope": denominator,
            "total_discrepancy_rows": len(disc_df),
            "linked_discrepancy_rows": len(linked_disc)
        }

        return self._create_kpi_result(name, value, numerator, denominator, 0, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 6: Data Accuracy / Pass Rate
    # Formula: Certified Records Passing Defined Validation Without Discrepancy / Certified Records Evaluated * 100
    # =========================================================================
    def kpi_6_data_accuracy(self, tasks_df: pd.DataFrame, disc_df: pd.DataFrame) -> Dict[str, Any]:
        """
        KPI 6: Data Accuracy / Pass Rate %
        Evaluated records that completed with zero discrepancies.
        """
        name = "Data Accuracy / Pass Rate"
        unit = "%"
        desired_trend = "higher"

        kpi_5 = self.kpi_5_discrepancy_rate(tasks_df, disc_df)
        if not kpi_5['available']:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=kpi_5['data_quality_warnings'])

        total = kpi_5['denominator']
        affected = kpi_5['numerator']
        passed = max(0, total - affected)

        value = (passed / total * 100.0) if total > 0 else 100.0

        details = {
            "passed_records": passed,
            "failed_discrepant_records": affected,
            "evaluated_records": total
        }

        return self._create_kpi_result(name, value, passed, total, 0, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 7: Rejection / Rework Rate
    # Formula: Eligible Tasks Returned for Rework / Eligible Tasks Submitted for Review * 100
    # =========================================================================
    def kpi_7_rejection_rate(self, tasks_df: pd.DataFrame) -> Dict[str, Any]:
        """
        KPI 7: Rejection / Rework Rate %
        Measures quality issues necessitating task rework or rejection.
        """
        name = "Rejection / Rework Rate"
        unit = "%"
        desired_trend = "lower"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        rework_col = self._col(tasks_df, ['u_rework_count', 'rework_count'])

        # Check if rework is tracked via field or status
        has_rework_col = rework_col is not None and rework_col in tasks_df.columns
        has_rework_state = 'Returned for Rework' in tasks_df[state_col].values or 'Rework' in tasks_df[state_col].values

        if not has_rework_col and not has_rework_state:
            return self._create_kpi_result(
                name, None, 0, len(tasks_df), 0, unit, desired_trend, False,
                warnings=["Historical rework tracking requires 'u_rework_count' field or 'Returned for Rework' state in cert_task table."],
                notes="Unavailable: source system does not provide rework indicators."
            )

        denominator = len(tasks_df)
        rework_tasks = 0

        if has_rework_col:
            rework_tasks = len(tasks_df[pd.to_numeric(tasks_df[rework_col], errors='coerce').fillna(0) > 0])
        elif has_rework_state:
            rework_tasks = len(tasks_df[tasks_df[state_col].isin(['Returned for Rework', 'Rework'])])

        value = (rework_tasks / denominator * 100.0) if denominator > 0 else 0.0

        details = {
            "reworked_tasks": rework_tasks,
            "submitted_tasks": denominator
        }

        return self._create_kpi_result(name, value, rework_tasks, denominator, 0, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 8: Aging / Backlog
    # Formula: Task Age = As-of Timestamp - Task Creation Timestamp for Open Tasks
    # =========================================================================
    def kpi_8_backlog_aging(self, tasks_df: pd.DataFrame, as_of_date: Optional[Any] = None) -> Dict[str, Any]:
        """
        KPI 8: Aging / Backlog
        Aging buckets for currently open tasks (0-4 days, 5-9 days, 10-14 days, 15+ days).
        """
        name = "Aging / Backlog"
        unit = "days"
        desired_trend = "lower"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        created_col = self._col(tasks_df, ['sys_created_on', 'created_at']) or 'sys_created_on'
        due_col = self._col(tasks_df, ['due_date'])

        open_statuses = ["Open", "Work in Progress", "Pending Review", "Pending"]
        open_tasks = tasks_df[tasks_df[state_col].isin(open_statuses)].copy()

        if open_tasks.empty:
            buckets = {"0-4 days": 0, "5-9 days": 0, "10-14 days": 0, "15+ days": 0}
            return self._create_kpi_result(name, 0.0, 0, len(tasks_df), 0, unit, desired_trend, True, details={"buckets": buckets, "open_count": 0, "overdue_count": 0})

        as_of = self._to_dt(as_of_date) if as_of_date else self._to_dt('2026-10-23')
        open_tasks['created_dt'] = self._to_dt(open_tasks[created_col])
        valid_open = open_tasks.dropna(subset=['created_dt']).copy()

        ages = (as_of - valid_open['created_dt']).dt.total_seconds() / 86400.0
        valid_open['age_days'] = ages

        buckets = {
            "0-4 days": int(len(ages[(ages >= 0) & (ages <= 4)])),
            "5-9 days": int(len(ages[(ages > 4) & (ages <= 9)])),
            "10-14 days": int(len(ages[(ages > 9) & (ages <= 14)])),
            "15+ days": int(len(ages[ages > 14]))
        }

        # Overdue open tasks
        overdue_count = 0
        if due_col and due_col in valid_open.columns:
            valid_open['due_dt'] = self._to_dt(valid_open[due_col])
            overdue_count = int(len(valid_open[valid_open['due_dt'] < as_of]))

        avg_age = float(ages.mean()) if not ages.empty else 0.0

        details = {
            "average_age_days": round(avg_age, 2),
            "open_count": len(valid_open),
            "overdue_count": overdue_count,
            "buckets": buckets
        }

        return self._create_kpi_result(name, avg_age, int(len(valid_open)), len(tasks_df), 0, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 9: Productivity per Certifier
    # Formula: Eligible Tasks Completed by Certifier / Applicable Working Days
    # =========================================================================
    def kpi_9_productivity(self, tasks_df: pd.DataFrame, working_days: int = 1) -> Dict[str, Any]:
        """
        KPI 9: Productivity per Certifier (tasks/certifier/day)
        Measures completion throughput normalized by team size and working days.
        """
        name = "Productivity per Certifier"
        unit = "tasks/certifier/day"
        desired_trend = "higher"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, working_days, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        assigned_col = self._col(tasks_df, ['assigned_to', 'certifier']) or 'assigned_to'

        completed = tasks_df[tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"])]
        days = max(1, working_days)

        if completed.empty or assigned_col not in completed.columns:
            return self._create_kpi_result(name, 0.0, 0, days, 0, unit, desired_trend, True, details={})

        certifier_counts = completed[assigned_col].value_counts()
        num_certifiers = max(1, certifier_counts.nunique())

        total_completed = len(completed)
        avg_productivity = (total_completed / num_certifiers) / days

        details = {
            "total_completed": total_completed,
            "certifier_count": num_certifiers,
            "working_days": days,
            "avg_closures_per_certifier": round(total_completed / num_certifiers, 1),
            "by_certifier": {str(k): int(v) for k, v in certifier_counts.head(15).items()}
        }

        return self._create_kpi_result(name, avg_productivity, total_completed, days * num_certifiers, 0, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 10: Last-Minute Closure %
    # A. Near-deadline closure share
    # B. Near-deadline open backlog
    # =========================================================================
    def kpi_10_last_minute_closure(self, tasks_df: pd.DataFrame, window_days: int = 5, as_of_date: Optional[Any] = None) -> Dict[str, Any]:
        """
        KPI 10: Last-Minute Closure %
        A: Completed within final N days before due date.
        B: Open tasks with due date falling within next N days.
        """
        name = "Last-Minute Closure %"
        unit = "%"
        desired_trend = "lower"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        closed_col = self._col(tasks_df, ['closed_at', 'completed_at']) or 'closed_at'
        due_col = self._col(tasks_df, ['due_date']) or 'due_date'

        completed = tasks_df[tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"])].copy()
        valid = completed.dropna(subset=[due_col, closed_col]).copy()
        excluded_count = len(completed) - len(valid)

        near_deadline_closures = 0
        denominator = len(valid)

        if not valid.empty:
            valid['due_dt'] = self._to_dt(valid[due_col])
            valid['closed_dt'] = self._to_dt(valid[closed_col])
            valid = valid.dropna(subset=['due_dt', 'closed_dt'])
            
            # Difference in days between due date and closure
            days_before_due = (valid['due_dt'] - valid['closed_dt']).dt.total_seconds() / 86400.0
            # Within window (e.g. 0 to 5 days before due date)
            near_deadline = valid[(days_before_due >= 0) & (days_before_due <= window_days)]
            near_deadline_closures = len(near_deadline)

        value = (near_deadline_closures / denominator * 100.0) if denominator > 0 else 0.0

        # Part B: Near-deadline open backlog
        as_of = self._to_dt(as_of_date) if as_of_date else self._to_dt('2026-10-23')
        open_statuses = ["Open", "Work in Progress", "Pending Review", "Pending"]
        open_tasks = tasks_df[tasks_df[state_col].isin(open_statuses)].copy()
        
        near_deadline_open_count = 0
        if not open_tasks.empty and due_col in open_tasks.columns:
            open_tasks['due_dt'] = self._to_dt(open_tasks[due_col])
            window_end = as_of + pd.Timedelta(days=int(window_days))
            imminent = open_tasks[(open_tasks['due_dt'] >= as_of) & (open_tasks['due_dt'] <= window_end)]
            near_deadline_open_count = len(imminent)

        details = {
            "near_deadline_closures": near_deadline_closures,
            "completed_with_due_date": denominator,
            "window_days": window_days,
            "near_deadline_open_backlog": near_deadline_open_count,
            "as_of_date": str(as_of.date())
        }

        return self._create_kpi_result(name, value, near_deadline_closures, denominator, excluded_count, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 11: Exception Resolution Time
    # Formula: Valid Resolution Timestamp - Exception Creation Timestamp in days
    # =========================================================================
    def kpi_11_exception_resolution(self, disc_df: pd.DataFrame) -> Dict[str, Any]:
        """
        KPI 11: Exception Resolution Time (days)
        Measures duration to investigate and resolve data exceptions.
        """
        name = "Exception Resolution Time"
        unit = "days"
        desired_trend = "lower"

        if disc_df is None or disc_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["No discrepancies in scope"])

        created_col = self._col(disc_df, ['sys_created_on', 'created_at']) or 'sys_created_on'
        resolved_col = self._col(disc_df, ['u_resolved_at', 'u_resolved_on', 'resolved_at']) or 'u_resolved_at'
        state_col = self._col(disc_df, ['state', 'status', 'u_status']) or 'state'

        resolved = disc_df[disc_df[state_col].isin(['Resolved', 'Closed', 'resolved'])].copy()
        valid = resolved.dropna(subset=[created_col, resolved_col]).copy()
        excluded_count = len(disc_df) - len(valid)

        if valid.empty:
            unresolved_count = len(disc_df) - len(resolved)
            return self._create_kpi_result(
                name, None, 0, 0, excluded_count, unit, desired_trend, False,
                warnings=["No resolved exceptions with valid timestamps"],
                details={"unresolved_exceptions": unresolved_count}
            )

        valid['created_dt'] = self._to_dt(valid[created_col])
        valid['resolved_dt'] = self._to_dt(valid[resolved_col])
        valid = valid.dropna(subset=['created_dt', 'resolved_dt'])
        valid = valid[valid['resolved_dt'] >= valid['created_dt']]

        durations = (valid['resolved_dt'] - valid['created_dt']).dt.total_seconds() / 86400.0

        mean_val = float(durations.mean())
        median_val = float(durations.median())
        unresolved_count = len(disc_df) - len(resolved)

        details = {
            "mean_days": round(mean_val, 2),
            "median_days": round(median_val, 2),
            "resolved_count": len(valid),
            "unresolved_count": unresolved_count
        }

        return self._create_kpi_result(name, mean_val, durations.sum(), len(durations), excluded_count, unit, desired_trend, True, details=details)

    # =========================================================================
    # KPI 12: Final SLA Achievement
    # Formula: Completed On or Before Final Cycle Deadline / Total Eligible Assigned to Cycle * 100
    # =========================================================================
    def kpi_12_sla_achievement(self, tasks_df: pd.DataFrame, final_deadline: Optional[Any] = None) -> Dict[str, Any]:
        """
        KPI 12: Final SLA Achievement %
        Denominator includes incomplete tasks at cycle deadline.
        """
        name = "Final SLA Achievement %"
        unit = "%"
        desired_trend = "higher"

        if tasks_df is None or tasks_df.empty:
            return self._create_kpi_result(name, None, 0, 0, 0, unit, desired_trend, False, warnings=["Empty tasks dataset"])

        state_col = self._col(tasks_df, ['state', 'status']) or 'state'
        closed_col = self._col(tasks_df, ['closed_at', 'completed_at']) or 'closed_at'
        id_col = self._col(tasks_df, ['sys_id', 'task_id']) or 'sys_id'

        exclude_statuses = ["Cancelled", "canceled"]
        eligible = tasks_df[~tasks_df[state_col].isin(exclude_statuses)].copy()
        denominator = eligible[id_col].nunique()
        excluded_count = len(tasks_df) - len(eligible)

        if denominator == 0:
            return self._create_kpi_result(name, 0.0, 0, 0, excluded_count, unit, desired_trend, True)

        deadline = self._to_dt(final_deadline) if final_deadline else self._to_dt('2026-12-23')

        completed = eligible[eligible[state_col].isin(["Closed Complete", "Closed Incomplete"])].copy()
        
        on_time = 0
        late = 0
        incomplete = denominator - len(completed)

        if not completed.empty and closed_col in completed.columns:
            completed['closed_dt'] = self._to_dt(completed[closed_col])
            valid_completed = completed.dropna(subset=['closed_dt'])
            
            on_time_df = valid_completed[valid_completed['closed_dt'] <= deadline]
            late_df = valid_completed[valid_completed['closed_dt'] > deadline]
            
            on_time = len(on_time_df)
            late = len(late_df) + (len(completed) - len(valid_completed))

        value = (on_time / denominator * 100.0) if denominator > 0 else 0.0

        details = {
            "completed_on_time": on_time,
            "completed_late": late,
            "incomplete_at_deadline": incomplete,
            "final_deadline": str(deadline.date()),
            "total_cycle_workload": denominator
        }

        return self._create_kpi_result(name, value, on_time, denominator, excluded_count, unit, desired_trend, True, details=details)

    # =========================================================================
    # Consolidator: Calculate all 12 KPIs
    # =========================================================================
    def calculate_all_kpis(
        self,
        tasks_df: pd.DataFrame,
        disc_df: pd.DataFrame,
        working_days: int = 15,
        as_of_date: Optional[Any] = None,
        final_deadline: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Calculates all 12 Business KPIs and returns consolidated dictionary."""
        results = {}
        results['kpi_1_certification_completion'] = self.kpi_1_certification_completion(tasks_df)
        results['kpi_2_daily_closure_rate'] = self.kpi_2_daily_closure_rate(tasks_df, working_days)
        results['kpi_3_on_time_completion'] = self.kpi_3_on_time_completion(tasks_df)
        results['kpi_4_avg_completion_time'] = self.kpi_4_avg_completion_time(tasks_df)
        results['kpi_5_discrepancy_rate'] = self.kpi_5_discrepancy_rate(tasks_df, disc_df)
        results['kpi_6_data_accuracy'] = self.kpi_6_data_accuracy(tasks_df, disc_df)
        results['kpi_7_rejection_rate'] = self.kpi_7_rejection_rate(tasks_df)
        results['kpi_8_backlog_aging'] = self.kpi_8_backlog_aging(tasks_df, as_of_date)
        results['kpi_9_productivity'] = self.kpi_9_productivity(tasks_df, working_days)
        results['kpi_10_last_minute_closure'] = self.kpi_10_last_minute_closure(tasks_df, as_of_date=as_of_date)
        results['kpi_11_exception_resolution'] = self.kpi_11_exception_resolution(disc_df)
        results['kpi_12_sla_achievement'] = self.kpi_12_sla_achievement(tasks_df, final_deadline)
        return results
