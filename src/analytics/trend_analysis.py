import logging
from datetime import timedelta
import pandas as pd
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class TrendAnalyzer:
    """Calculates daily trends, cumulative progress, and quarter-wise daily comparative velocity."""
    
    def calculate_daily_trends(self, tasks_df: pd.DataFrame, date_col: str = 'closed_at') -> pd.DataFrame:
        """Calculates daily closure trends."""
        if tasks_df.empty or date_col not in tasks_df.columns:
            return pd.DataFrame()
            
        df = tasks_df.dropna(subset=[date_col]).copy()
        df['date'] = pd.to_datetime(df[date_col]).dt.date
        
        daily_counts = df.groupby('date').size().reset_index(name='completed_count')
        daily_counts = daily_counts.sort_values('date')
        
        daily_counts['cumulative_completed'] = daily_counts['completed_count'].cumsum()
        daily_counts['moving_avg_7d'] = daily_counts['completed_count'].rolling(window=7, min_periods=1).mean()
        
        return daily_counts

    def build_working_day_daily_series(
        self,
        tasks_df: pd.DataFrame,
        start_date: Any,
        end_date: Any,
        holidays: Optional[List[Any]] = None
    ) -> pd.DataFrame:
        """
        Builds a daily trend series aligned by working days elapsed (Day 1, Day 2, ..., Day N)
        for a given campaign window [start_date, end_date].
        """
        if tasks_df is None or tasks_df.empty or not start_date or not end_date:
            return pd.DataFrame()

        s_date = pd.to_datetime(start_date).date()
        e_date = pd.to_datetime(end_date).date()
        if s_date > e_date:
            s_date, e_date = e_date, s_date

        holidays_set = set([pd.to_datetime(h).date() for h in (holidays or [])])

        # Generate list of working dates (Monday to Friday, excluding holidays)
        cur = s_date
        working_dates = []
        while cur <= e_date:
            if cur.weekday() < 5 and cur not in holidays_set:
                working_dates.append(cur)
            cur += timedelta(days=1)

        if not working_dates:
            cur = s_date
            while cur <= e_date:
                working_dates.append(cur)
                cur += timedelta(days=1)

        # Filter completed tasks
        state_col = 'state' if 'state' in tasks_df.columns else ('status' if 'status' in tasks_df.columns else None)
        closed_col = 'closed_at' if 'closed_at' in tasks_df.columns else ('completed_at' if 'completed_at' in tasks_df.columns else ('sys_updated_on' if 'sys_updated_on' in tasks_df.columns else None))

        if state_col:
            completion_matches = ["Closed Complete", "Closed Incomplete", "closed_complete", "closed_incomplete", "completed", "Closed"]
            completed = tasks_df[tasks_df[state_col].isin(completion_matches)].copy()
            if completed.empty and closed_col and closed_col in tasks_df.columns:
                completed = tasks_df[tasks_df[closed_col].notna()].copy()
        else:
            completed = tasks_df.copy()

        daily_counts = {}
        if closed_col and closed_col in completed.columns:
            close_dates = pd.to_datetime(completed[closed_col], errors='coerce').dt.date
            for d in close_dates.dropna():
                effective_d = d
                if effective_d < s_date:
                    effective_d = working_dates[0]
                elif effective_d > e_date:
                    effective_d = working_dates[-1]
                elif effective_d not in working_dates:
                    future_dates = [wd for wd in working_dates if wd >= effective_d]
                    if future_dates:
                        effective_d = future_dates[0]
                    else:
                        effective_d = working_dates[-1]
                daily_counts[effective_d] = daily_counts.get(effective_d, 0) + 1

        total_eligible = len(tasks_df)
        rows = []
        running_cum = 0

        for idx, w_date in enumerate(working_dates, 1):
            day_closures = daily_counts.get(w_date, 0)
            running_cum += day_closures
            cum_pct = round((running_cum / total_eligible * 100.0), 2) if total_eligible > 0 else 0.0
            date_label = f"{w_date.strftime('%b')} {w_date.day}"
            rows.append({
                "day_index": idx,
                "working_day": f"Day {idx}",
                "Day_Label": f"Day {idx}",
                "date": str(w_date),
                "date_label": date_label,
                "Date_Label": date_label,
                "Date": date_label,
                "daily_closures": day_closures,
                "Daily_Closures": day_closures,
                "cumulative_closures": running_cum,
                "cumulative_pct": cum_pct,
                "Cumulative_Pct": cum_pct
            })

        return pd.DataFrame(rows)

    def compare_quarter_daily_trends(
        self,
        tasks_a: pd.DataFrame,
        meta_a: Dict[str, Any],
        tasks_b: pd.DataFrame,
        meta_b: Dict[str, Any],
        holidays: Optional[List[Any]] = None
    ) -> pd.DataFrame:
        """
        Generates an aligned day-by-day comparative DataFrame between Quarter A and Quarter B.
        Aligned along Working Day Index (Day 1, Day 2, ...).
        """
        df_a = self.build_working_day_daily_series(
            tasks_a,
            meta_a.get('start_date'),
            meta_a.get('end_date'),
            holidays=holidays
        )
        df_b = self.build_working_day_daily_series(
            tasks_b,
            meta_b.get('start_date'),
            meta_b.get('end_date'),
            holidays=holidays
        )

        if df_a.empty and df_b.empty:
            return pd.DataFrame()

        max_days = max(len(df_a), len(df_b))
        q_name_a = meta_a.get('name', 'Quarter A')
        q_name_b = meta_b.get('name', 'Quarter B')

        rows = []
        cum_a_last = 0
        cum_b_last = 0
        pct_a_last = 0.0
        pct_b_last = 0.0

        for d_idx in range(1, max_days + 1):
            row_a = df_a[df_a['day_index'] == d_idx]
            row_b = df_b[df_b['day_index'] == d_idx]

            date_a = row_a.iloc[0]['date'] if not row_a.empty else "-"
            if not row_a.empty and 'date_label' in row_a.columns:
                date_label_a = str(row_a.iloc[0]['date_label'])
            elif date_a != "-":
                dt_a = pd.to_datetime(date_a, errors='coerce')
                date_label_a = f"{dt_a.strftime('%b')} {dt_a.day}" if pd.notna(dt_a) else "-"
            else:
                date_label_a = "-"

            date_b = row_b.iloc[0]['date'] if not row_b.empty else "-"
            if not row_b.empty and 'date_label' in row_b.columns:
                date_label_b = str(row_b.iloc[0]['date_label'])
            elif date_b != "-":
                dt_b = pd.to_datetime(date_b, errors='coerce')
                date_label_b = f"{dt_b.strftime('%b')} {dt_b.day}" if pd.notna(dt_b) else "-"
            else:
                date_label_b = "-"

            daily_a = int(row_a.iloc[0]['daily_closures']) if not row_a.empty else 0
            if not row_a.empty:
                cum_a_last = int(row_a.iloc[0]['cumulative_closures'])
                pct_a_last = float(row_a.iloc[0]['cumulative_pct'])

            daily_b = int(row_b.iloc[0]['daily_closures']) if not row_b.empty else 0
            if not row_b.empty:
                cum_b_last = int(row_b.iloc[0]['cumulative_closures'])
                pct_b_last = float(row_b.iloc[0]['cumulative_pct'])

            delta_daily = daily_a - daily_b
            delta_cum = cum_a_last - cum_b_last
            delta_pct = round(pct_a_last - pct_b_last, 2)

            pace_leader = q_name_a if pct_a_last > pct_b_last else (q_name_b if pct_b_last > pct_a_last else "Tied")

            chart_date_label = date_label_a if date_label_a != "-" else date_label_b

            rows.append({
                "Working Day": f"Day {d_idx}",
                "Day_Label": f"Day {d_idx}",
                "Date_Label": chart_date_label,
                "date_label": chart_date_label,
                "Date": chart_date_label,
                f"{q_name_a} Date": date_label_a,
                f"Date ({q_name_a})": date_label_a,
                f"{q_name_a} Daily": daily_a,
                f"{q_name_a} Cumulative": cum_a_last,
                f"{q_name_a} % Complete": pct_a_last,
                f"{q_name_b} Date": date_label_b,
                f"Date ({q_name_b})": date_label_b,
                f"{q_name_b} Daily": daily_b,
                f"{q_name_b} Cumulative": cum_b_last,
                f"{q_name_b} % Complete": pct_b_last,
                f"Daily Delta ({q_name_a} - {q_name_b})": delta_daily,
                f"Daily Difference (A - B)": delta_daily,
                f"Cumulative Delta ({q_name_a} - {q_name_b})": delta_cum,
                f"% Delta ({q_name_a} - {q_name_b})": delta_pct,
                "Pace Leader": pace_leader
            })

        return pd.DataFrame(rows)

    def compare_cycles(self, current_trends: pd.DataFrame, previous_trends: pd.DataFrame) -> pd.DataFrame:
        """Compares current vs previous cycle trends."""
        if 'elapsed_working_day' in current_trends.columns and 'elapsed_working_day' in previous_trends.columns:
            merged = pd.merge(
                current_trends, 
                previous_trends, 
                on='elapsed_working_day', 
                how='outer',
                suffixes=('_current', '_previous')
            )
            return merged.sort_values('elapsed_working_day')
        return current_trends
