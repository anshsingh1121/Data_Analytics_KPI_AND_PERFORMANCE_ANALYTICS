import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ProductivityAnalyzer:
    """
    Analyzes team productivity and individual performance metrics
    based on the 'assigned_to' field for both tasks and discrepancies
    (u_failed_data_certifications_list).
    """

    def analyze(self, tasks_df: pd.DataFrame, working_days: int) -> pd.DataFrame:
        """Returns a DataFrame with certifier productivity stats."""
        cert_col = 'assigned_to' if 'assigned_to' in tasks_df.columns else ('certifier' if 'certifier' in tasks_df.columns else None)
        if tasks_df.empty or not cert_col:
            return pd.DataFrame()
            
        assigned = tasks_df.groupby(cert_col).size().rename('total_assigned')
        
        state_col = 'state' if 'state' in tasks_df.columns else ('status' if 'status' in tasks_df.columns else None)
        completed_mask = tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"]) if state_col else pd.Series(False, index=tasks_df.index)
        completed = tasks_df[completed_mask].groupby(cert_col).size().rename('total_completed')
        
        prod_df = pd.concat([assigned, completed], axis=1).fillna(0)
        
        if working_days > 0:
            prod_df['daily_completion_rate'] = prod_df['total_completed'] / working_days
        else:
            prod_df['daily_completion_rate'] = 0.0
            
        return prod_df.reset_index()

    def build_team_performance_df(
        self,
        df: pd.DataFrame,
        working_days: int = 15,
        sla_days_target: float = 5.0
    ) -> pd.DataFrame:
        """
        Builds Team Performance & Productivity Dashboard metrics using 'assigned_to':
        1. Tasks assigned
        2. Tasks completed
        3. Daily closure rate
        4. Average turnaround time (Days)
        5. SLA compliance (%)
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=[
                "Team Member", "Tasks assigned", "Tasks completed", "Open Backlog",
                "Daily closure rate", "Average turnaround time", "SLA compliance"
            ])

        assignee_col = 'assigned_to' if 'assigned_to' in df.columns else ('certifier' if 'certifier' in df.columns else None)
        if not assignee_col:
            return pd.DataFrame()

        # Status detection
        state_col = None
        for col in ['u_status', 'state', 'status']:
            if col in df.columns:
                state_col = col
                break

        # Date columns
        created_col = 'sys_created_on' if 'sys_created_on' in df.columns else ('created_at' if 'created_at' in df.columns else None)
        resolved_col = None
        for col in ['u_resolved_on', 'closed_at', 'resolved_at']:
            if col in df.columns:
                resolved_col = col
                break

        due_col = 'due_date' if 'due_date' in df.columns else None

        # Prepare working copy
        wdf = df.copy()
        wdf[assignee_col] = wdf[assignee_col].fillna("Unassigned").astype(str).str.strip()

        # Completed mask
        if state_col:
            is_completed = wdf[state_col].isin(['Resolved', 'Closed', 'Closed Complete', 'resolved', 'closed'])
        else:
            is_completed = pd.Series(True, index=wdf.index)

        wdf['is_completed'] = is_completed

        # Calculate turnaround days for each record
        if created_col and resolved_col:
            c_dt = pd.to_datetime(wdf[created_col], errors='coerce')
            r_dt = pd.to_datetime(wdf[resolved_col], errors='coerce')
            wdf['turnaround_days'] = (r_dt - c_dt).dt.total_seconds() / 86400.0
            wdf['turnaround_days'] = wdf['turnaround_days'].apply(lambda x: max(0.1, x) if pd.notna(x) else np.nan)
        else:
            wdf['turnaround_days'] = np.nan

        # SLA compliance check
        if due_col and resolved_col:
            d_dt = pd.to_datetime(wdf[due_col], errors='coerce')
            r_dt = pd.to_datetime(wdf[resolved_col], errors='coerce')
            wdf['is_sla_compliant'] = (r_dt <= d_dt)
        elif 'turnaround_days' in wdf.columns:
            wdf['is_sla_compliant'] = (wdf['turnaround_days'] <= sla_days_target)
        else:
            wdf['is_sla_compliant'] = True

        rows = []
        for assignee, grp in wdf.groupby(assignee_col):
            t_assigned = len(grp)
            comp_grp = grp[grp['is_completed']]
            t_completed = len(comp_grp)
            open_backlog = t_assigned - t_completed
            daily_closure = round(t_completed / max(1, working_days), 2)

            # Turnaround time
            valid_times = comp_grp['turnaround_days'].dropna()
            avg_turnaround = round(valid_times.mean(), 1) if not valid_times.empty else 0.0

            # SLA compliance
            if t_completed > 0:
                sla_met = comp_grp['is_sla_compliant'].sum()
                sla_pct = round((sla_met / t_completed) * 100.0, 1)
            else:
                sla_pct = 0.0

            comp_rate = round((t_completed / max(1, t_assigned)) * 100.0, 1)

            # Performance flag for lagging / worst performers
            if sla_pct < 80.0 or avg_turnaround > 7.0 or (open_backlog > 10 and comp_rate < 70.0):
                perf_status = "🚨 Needs Urgent Attention (Slow / High Backlog)"
            elif sla_pct < 90.0 or avg_turnaround > 5.0 or open_backlog > 5:
                perf_status = "⚠️ Slower Pace / At Risk"
            else:
                perf_status = "✅ On Target / High Performer"

            rows.append({
                "Team Member": assignee,
                "Tasks assigned": int(t_assigned),
                "Tasks completed": int(t_completed),
                "Open Backlog": int(open_backlog),
                "Completion Rate %": float(comp_rate),
                "Daily closure rate": float(daily_closure),
                "Average turnaround time": float(avg_turnaround),
                "SLA compliance": float(sla_pct),
                "Performance Status": perf_status
            })

        res_df = pd.DataFrame(rows)
        if not res_df.empty:
            res_df = res_df.sort_values(by=["Average turnaround time", "Open Backlog", "SLA compliance"], ascending=[False, False, True])
        return res_df
