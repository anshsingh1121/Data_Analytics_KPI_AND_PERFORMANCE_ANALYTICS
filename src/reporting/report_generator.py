import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class ReportGenerator:
    """
    Generates structured DataFrames for all 8 standard analytical reports:
    1. kpi_summary
    2. cycle_comparison
    3. daily_trends
    4. backlog_analysis
    5. discrepancy_analysis
    6. certifier_productivity
    7. exception_resolution
    8. data_quality_report
    """

    def __init__(self, cycle_metadata: Optional[Dict[str, Any]] = None, app_mode: str = "demo"):
        self.cycle_metadata = cycle_metadata or {}
        self.app_mode = app_mode
        self.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    def build_kpi_summary_df(self, kpis: Dict[str, Any]) -> pd.DataFrame:
        """Builds DataFrame of all 12 KPIs with formulas, values, units, denominators, and status."""
        rows = []
        for key, res in kpis.items():
            rows.append({
                "KPI Code": key,
                "KPI Name": res.get("name", key),
                "Value": res.get("value"),
                "Unit": res.get("unit", ""),
                "Numerator": res.get("numerator"),
                "Denominator": res.get("denominator"),
                "Excluded Count": res.get("excluded_count", 0),
                "Desired Trend": res.get("desired_trend", ""),
                "Available": res.get("available", True),
                "Warnings": "; ".join(res.get("data_quality_warnings", [])) if res.get("data_quality_warnings") else "None",
                "Mode": self.app_mode,
                "Report Timestamp": self.generated_at
            })
        return pd.DataFrame(rows)

    def build_cycle_comparison_df(self, comparison_rows: List[Dict[str, Any]]) -> pd.DataFrame:
        """Builds DataFrame of current vs previous cycle comparison."""
        if not comparison_rows:
            return pd.DataFrame(columns=["Metric", "Current Value", "Previous Value", "Abs Change", "Pct Change", "PP Change", "Favorable"])
        rows = []
        for r in comparison_rows:
            rows.append({
                "Metric": r.get("metric_name", r.get("metric_key")),
                "Current Value": r.get("current_value"),
                "Previous Value": r.get("previous_value"),
                "Unit": r.get("unit", ""),
                "Absolute Change": round(r.get("abs_change", 0), 2) if r.get("abs_change") is not None else None,
                "Percentage Change (%)": round(r.get("pct_change", 0), 2) if r.get("pct_change") is not None else None,
                "Percentage Points (pp)": round(r.get("pp_change", 0), 2) if r.get("pp_change") is not None else None,
                "Desired Trend": r.get("desired_trend", ""),
                "Favorable": "Yes" if r.get("is_favorable") is True else "No" if r.get("is_favorable") is False else "N/A"
            })
        return pd.DataFrame(rows)

    def build_daily_trends_df(self, tasks_df: pd.DataFrame) -> pd.DataFrame:
        """Builds daily completion trends and cumulative closures."""
        if tasks_df is None or tasks_df.empty:
            return pd.DataFrame()
        state_col = 'state' if 'state' in tasks_df.columns else 'status'
        closed_col = 'closed_at' if 'closed_at' in tasks_df.columns else 'completed_at'

        completed = tasks_df[tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"])].copy()
        if completed.empty or closed_col not in completed.columns:
            return pd.DataFrame()

        completed['closed_date'] = pd.to_datetime(completed[closed_col], errors='coerce').dt.date
        valid = completed.dropna(subset=['closed_date'])

        daily = valid.groupby('closed_date').size().reset_index(name='Daily Closures')
        daily = daily.sort_values('closed_date')
        daily['Cumulative Closures'] = daily['Daily Closures'].cumsum()
        daily['7-Day Moving Avg'] = daily['Daily Closures'].rolling(7, min_periods=1).mean().round(1)
        daily['Date'] = daily['closed_date'].astype(str)
        return daily[['Date', 'Daily Closures', 'Cumulative Closures', '7-Day Moving Avg']]

    def build_backlog_analysis_df(self, tasks_df: pd.DataFrame, as_of_date: Optional[Any] = None) -> pd.DataFrame:
        """Builds aging and backlog distribution for open tasks."""
        if tasks_df is None or tasks_df.empty:
            return pd.DataFrame()
        state_col = 'state' if 'state' in tasks_df.columns else 'status'
        created_col = 'sys_created_on' if 'sys_created_on' in tasks_df.columns else 'created_at'
        due_col = 'due_date' if 'due_date' in tasks_df.columns else None
        app_col = 'cmdb_ci' if 'cmdb_ci' in tasks_df.columns else 'application'

        open_tasks = tasks_df[tasks_df[state_col].isin(["Open", "Work in Progress", "Pending Review"])].copy()
        if open_tasks.empty:
            return pd.DataFrame(columns=["Task Number", "Application", "Assigned To", "Age (Days)", "Aging Bucket", "Overdue"])

        as_of = pd.to_datetime(as_of_date) if as_of_date else pd.to_datetime('2026-10-23')
        if hasattr(as_of, 'tzinfo') and as_of.tzinfo is not None:
            as_of = as_of.tz_localize(None)

        open_tasks['created_dt'] = pd.to_datetime(open_tasks[created_col], errors='coerce')
        if hasattr(open_tasks['created_dt'].dt, 'tz') and open_tasks['created_dt'].dt.tz is not None:
            open_tasks['created_dt'] = open_tasks['created_dt'].dt.tz_localize(None)

        valid = open_tasks.dropna(subset=['created_dt']).copy()

        valid['Age (Days)'] = ((as_of - valid['created_dt']).dt.total_seconds() / 86400.0).round(1)
        
        def bucket(age):
            if age <= 4: return "0-4 days"
            elif age <= 9: return "5-9 days"
            elif age <= 14: return "10-14 days"
            else: return "15+ days"

        valid['Aging Bucket'] = valid['Age (Days)'].apply(bucket)

        if due_col and due_col in valid.columns:
            valid['due_dt'] = pd.to_datetime(valid[due_col], errors='coerce')
            if hasattr(valid['due_dt'].dt, 'tz') and valid['due_dt'].dt.tz is not None:
                valid['due_dt'] = valid['due_dt'].dt.tz_localize(None)
            valid['Overdue'] = valid['due_dt'].apply(lambda d: "Yes" if pd.notna(d) and d < as_of else "No")
        else:
            valid['Overdue'] = "Unknown"

        number_col = 'number' if 'number' in valid.columns else 'sys_id'
        assignee_col = 'assigned_to' if 'assigned_to' in valid.columns else 'certifier'

        res = pd.DataFrame({
            "Task Number": valid[number_col],
            "Application": valid[app_col] if app_col in valid.columns else "N/A",
            "Assigned To": valid[assignee_col] if assignee_col in valid.columns else "N/A",
            "Age (Days)": valid['Age (Days)'],
            "Aging Bucket": valid['Aging Bucket'],
            "Overdue": valid['Overdue']
        })
        return res.sort_values('Age (Days)', ascending=False)

    def build_discrepancy_analysis_df(self, disc_df: pd.DataFrame) -> pd.DataFrame:
        """Builds breakdown of discrepancies by category, field, and resolution status."""
        if disc_df is None or disc_df.empty:
            return pd.DataFrame(columns=["Category", "Total Discrepancies", "Resolved Count", "Open Count", "Resolution Rate %"])

        disc_df = disc_df.copy()

        cat_col = 'u_issue_category' if 'u_issue_category' in disc_df.columns else 'category'
        state_col = None
        for cand in ['u_status', 'state', 'status']:
            if cand in disc_df.columns:
                state_col = cand
                break

        if cat_col not in disc_df.columns:
            disc_df[cat_col] = "General"

        if state_col:
            grouped = disc_df.groupby(cat_col).agg(
                Total_Discrepancies=(cat_col, 'count'),
                Resolved_Count=(state_col, lambda s: (s.isin(['Resolved', 'Closed', 'resolved'])).sum())
            ).reset_index()
        else:
            grouped = disc_df.groupby(cat_col).agg(
                Total_Discrepancies=(cat_col, 'count')
            ).reset_index()
            grouped['Resolved_Count'] = 0

        grouped['Open Count'] = grouped['Total_Discrepancies'] - grouped['Resolved_Count']
        grouped['Resolution Rate %'] = ((grouped['Resolved_Count'] / grouped['Total_Discrepancies']) * 100.0).round(1)
        grouped.columns = ["Category", "Total Discrepancies", "Resolved Count", "Open Count", "Resolution Rate %"]
        return grouped.sort_values('Total Discrepancies', ascending=False)

    def build_certifier_productivity_df(self, tasks_df: pd.DataFrame, working_days: int = 15, sort_by: str = "worst") -> pd.DataFrame:
        """
        Builds certifier performance table with dedicated metrics to identify
        slowest certifiers / worst performers (people taking more time, low completion rates, high open backlog).
        """
        if tasks_df is None or tasks_df.empty:
            return pd.DataFrame(columns=["Certifier", "Assigned Tasks", "Completed Tasks", "Open Tasks", "Completion Rate %", "Avg Completion Time (Days)", "Daily Rate", "Performance Status"])

        assignee_col = 'assigned_to' if 'assigned_to' in tasks_df.columns else 'certifier'
        state_col = 'state' if 'state' in tasks_df.columns else 'status'
        created_col = 'sys_created_on' if 'sys_created_on' in tasks_df.columns else 'created_at'
        closed_col = 'closed_at' if 'closed_at' in tasks_df.columns else 'completed_at'

        if assignee_col not in tasks_df.columns:
            return pd.DataFrame()

        total = tasks_df.groupby(assignee_col).size().rename('Assigned Tasks')
        completed_mask = tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"])
        completed_df = tasks_df[completed_mask].copy()
        completed = completed_df.groupby(assignee_col).size().rename('Completed Tasks')

        prod = pd.concat([total, completed], axis=1).fillna(0).reset_index()
        prod.columns = ["Certifier", "Assigned Tasks", "Completed Tasks"]
        prod['Assigned Tasks'] = prod['Assigned Tasks'].astype(int)
        prod['Completed Tasks'] = prod['Completed Tasks'].astype(int)
        prod['Open Tasks'] = prod['Assigned Tasks'] - prod['Completed Tasks']
        prod['Completion Rate %'] = ((prod['Completed Tasks'] / prod['Assigned Tasks']) * 100.0).round(1)
        prod['Daily Rate'] = (prod['Completed Tasks'] / max(1, working_days)).round(2)

        # Calculate Average Completion Time (Days) per certifier (time taken to complete tasks)
        if not completed_df.empty and created_col in completed_df.columns and closed_col in completed_df.columns:
            completed_df['c_dt'] = pd.to_datetime(completed_df[created_col], errors='coerce')
            completed_df['cl_dt'] = pd.to_datetime(completed_df[closed_col], errors='coerce')
            completed_df['days_taken'] = (completed_df['cl_dt'] - completed_df['c_dt']).dt.total_seconds() / 86400.0
            avg_time = completed_df.groupby(assignee_col)['days_taken'].mean().round(1).rename('Avg Completion Time (Days)')
            prod = prod.merge(avg_time, left_on='Certifier', right_index=True, how='left')
            prod['Avg Completion Time (Days)'] = prod['Avg Completion Time (Days)'].fillna(0.0)
        else:
            prod['Avg Completion Time (Days)'] = 0.0

        # Performance Flag for worst performers / slow closures
        def _classify(row):
            if row['Completion Rate %'] < 50.0 or row['Avg Completion Time (Days)'] > 10.0:
                return "Needs Urgent Attention (Slow / High Backlog)"
            elif row['Completion Rate %'] < 80.0 or row['Avg Completion Time (Days)'] > 6.0:
                return "Moderate / Slower Pace"
            return "Good / On Track"

        prod['Performance Status'] = prod.apply(_classify, axis=1)

        # Sort: "worst" puts certifiers taking more time and with low completion rates at the top
        if sort_by == "worst":
            sorted_prod = prod.sort_values(by=['Avg Completion Time (Days)', 'Open Tasks', 'Completion Rate %'], ascending=[False, False, True]).reset_index(drop=True)
        else:
            sorted_prod = prod.sort_values('Completed Tasks', ascending=False).reset_index(drop=True)

        # Add clean 1-based Rank column so roster is clearly ordered
        sorted_prod.insert(0, 'Rank', [f"#{i+1}" for i in range(len(sorted_prod))])
        return sorted_prod

    def build_exception_resolution_df(self, disc_df: pd.DataFrame) -> pd.DataFrame:
        """Builds exception resolution duration distribution."""
        if disc_df is None or disc_df.empty:
            return pd.DataFrame(columns=["Discrepancy Number", "Task", "Category", "Field", "Duration (Days)", "Status"])

        disc_df = disc_df.copy()
        num_col = 'number' if 'number' in disc_df.columns else 'sys_id'
        task_col = 'u_certification_task' if 'u_certification_task' in disc_df.columns else 'linked_task'
        cat_col = 'u_issue_category' if 'u_issue_category' in disc_df.columns else 'category'
        field_col = 'u_field' if 'u_field' in disc_df.columns else ('u_field_name' if 'u_field_name' in disc_df.columns else 'field')
        state_col = 'u_status' if 'u_status' in disc_df.columns else ('state' if 'state' in disc_df.columns else 'status')
        created_col = 'sys_created_on' if 'sys_created_on' in disc_df.columns else 'created_at'
        resolved_col = 'u_resolved_on' if 'u_resolved_on' in disc_df.columns else ('u_resolved_at' if 'u_resolved_at' in disc_df.columns else 'resolved_at')

        if created_col in disc_df.columns:
            disc_df['created_dt'] = pd.to_datetime(disc_df[created_col], errors='coerce')
            if hasattr(disc_df['created_dt'].dt, 'tz') and disc_df['created_dt'].dt.tz is not None:
                disc_df['created_dt'] = disc_df['created_dt'].dt.tz_localize(None)
        else:
            disc_df['created_dt'] = None

        if resolved_col in disc_df.columns:
            disc_df['resolved_dt'] = pd.to_datetime(disc_df[resolved_col], errors='coerce')
            if hasattr(disc_df['resolved_dt'].dt, 'tz') and disc_df['resolved_dt'].dt.tz is not None:
                disc_df['resolved_dt'] = disc_df['resolved_dt'].dt.tz_localize(None)
        else:
            disc_df['resolved_dt'] = None

        durations = []
        for _, row in disc_df.iterrows():
            if pd.notna(row['created_dt']) and pd.notna(row['resolved_dt']):
                dur = round((row['resolved_dt'] - row['created_dt']).total_seconds() / 86400.0, 1)
                durations.append(max(0.0, dur))
            else:
                durations.append(None)

        disc_df['Duration (Days)'] = durations

        res = pd.DataFrame({
            "Discrepancy Number": disc_df[num_col] if num_col in disc_df.columns else "N/A",
            "Linked Task": disc_df[task_col] if task_col in disc_df.columns else "N/A",
            "Category": disc_df[cat_col] if cat_col in disc_df.columns else "N/A",
            "Field": disc_df[field_col] if field_col in disc_df.columns else "N/A",
            "Duration (Days)": disc_df['Duration (Days)'],
            "Status": disc_df[state_col] if state_col in disc_df.columns else "N/A"
        })
        return res

    def build_data_quality_report_df(self, tasks_df: pd.DataFrame, disc_df: pd.DataFrame, qa_stats: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """Builds audit data quality report DataFrame."""
        rows = []
        
        # Check task completeness
        total_tasks = len(tasks_df) if tasks_df is not None else 0
        state_col = 'state' if tasks_df is not None and 'state' in tasks_df.columns else 'status'
        closed_col = 'closed_at' if tasks_df is not None and 'closed_at' in tasks_df.columns else 'completed_at'
        due_col = 'due_date' if tasks_df is not None and 'due_date' in tasks_df.columns else None

        rows.append({"Table": "cert_task", "Metric": "Total Records Extracted", "Value": str(total_tasks), "Status": "PASS"})
        if tasks_df is not None and not tasks_df.empty:
            dup_tasks = tasks_df.duplicated(subset=['sys_id']).sum() if 'sys_id' in tasks_df.columns else 0
            rows.append({"Table": "cert_task", "Metric": "Duplicate Records", "Value": str(dup_tasks), "Status": "PASS" if dup_tasks == 0 else "WARNING"})
            
            missing_states = tasks_df[state_col].isna().sum() if state_col in tasks_df.columns else total_tasks
            rows.append({"Table": "cert_task", "Metric": "Missing Statuses", "Value": str(missing_states), "Status": "PASS" if missing_states == 0 else "FAIL"})

            if due_col and due_col in tasks_df.columns:
                missing_dues = tasks_df[due_col].isna().sum()
                rows.append({"Table": "cert_task", "Metric": "Missing Due Dates", "Value": str(missing_dues), "Status": "INFO"})

        total_disc = len(disc_df) if disc_df is not None else 0
        rows.append({"Table": "u_failed_data_certifications", "Metric": "Total Discrepancies", "Value": str(total_disc), "Status": "PASS"})
        if disc_df is not None and not disc_df.empty:
            task_link_col = 'u_certification_task' if 'u_certification_task' in disc_df.columns else 'linked_task'
            if tasks_df is not None and task_link_col in disc_df.columns and 'sys_id' in tasks_df.columns:
                valid_task_ids = set(tasks_df['sys_id'].dropna().unique())
                orphaned = (~disc_df[task_link_col].isin(valid_task_ids)).sum()
                rows.append({"Table": "u_failed_data_certifications", "Metric": "Orphaned Discrepancies", "Value": str(orphaned), "Status": "PASS" if orphaned == 0 else "WARNING"})

        return pd.DataFrame(rows)
