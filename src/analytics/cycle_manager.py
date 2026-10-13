import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date

logger = logging.getLogger(__name__)

class CycleManager:
    """Manages certification cycles, boundaries, working days, and cycle comparisons."""

    def __init__(self, cycle_config: Dict[str, Any], holidays: Optional[List[str]] = None):
        self.config = cycle_config or {}
        self.holidays = [pd.to_datetime(h).date() for h in (holidays or self.config.get('holidays', ['2026-01-01', '2026-12-25']))]
        self._init_cycles()

    def _init_cycles(self):
        """Extracts current and previous cycle from config."""
        self.cycles = self.config.get('cycles', {})
        self.current_cycle = self.config.get('current_cycle', {
            'name': 'Q4-2026',
            'quarter_label': 'Oct-Dec 2026',
            'start_date': '2026-10-01',
            'end_date': '2026-12-31',
            'final_deadline': '2026-12-23'
        })
        self.previous_cycle = self.config.get('previous_cycle', {
            'name': 'Q1-2026',
            'quarter_label': 'Jan-Mar 2026',
            'start_date': '2026-01-01',
            'end_date': '2026-03-31',
            'final_deadline': '2026-03-24'
        })
        self.comparison_settings = self.config.get('comparison_settings', {
            'mode': 'like_for_like',
            'align_by': 'working_days_elapsed'
        })

    def get_cycle_by_name(self, name: str) -> Dict[str, Any]:
        """Returns cycle dict by name."""
        if name in self.cycles:
            return self.cycles[name]
        if self.current_cycle.get('name') == name:
            return self.current_cycle
        if self.previous_cycle.get('name') == name:
            return self.previous_cycle
        return {'name': name, 'start_date': '2026-10-01', 'end_date': '2026-12-31', 'final_deadline': '2026-12-23'}

    def assign_cycle_to_dataframe(self, df: pd.DataFrame, date_col: str = 'sys_created_on') -> pd.DataFrame:
        """Assigns quarter cycle name (Q4-2026, Q1-2026, Q4-2025, Q1-2025) based on timestamp."""
        if df is None or df.empty:
            return df
            
        col_to_use = None
        for cand in [date_col, 'sys_created_on', 'created_at', 'closed_at']:
            if cand in df.columns:
                col_to_use = cand
                break
                
        if not col_to_use:
            df['certification_cycle'] = 'Q4-2026'
            return df
            
        dt_series = pd.to_datetime(df[col_to_use], errors='coerce')
        if hasattr(dt_series.dt, 'tz') and dt_series.dt.tz is not None:
            dt_series = dt_series.dt.tz_localize(None)

        def _match_cycle(ts):
            if pd.isna(ts):
                return 'Unknown'
            # Check configured cycle boundaries
            for c_name, c_info in self.cycles.items():
                s = pd.to_datetime(c_info.get('start_date'))
                e = pd.to_datetime(c_info.get('end_date'))
                if s <= ts <= e:
                    return c_name
            # Fallback by year and month
            y = ts.year
            m = ts.month
            if y == 2026 and 10 <= m <= 12:
                return 'Q4-2026'
            elif y == 2026 and 1 <= m <= 3:
                return 'Q1-2026'
            elif y == 2025 and 10 <= m <= 12:
                return 'Q4-2025'
            elif y == 2025 and 1 <= m <= 3:
                return 'Q1-2025'
            return 'Other'

        df['certification_cycle'] = dt_series.apply(_match_cycle)
        return df

    def calculate_working_days(self, start_date: Any, end_date: Any) -> int:
        """Calculates working days elapsed between two dates respecting holidays and weekends."""
        try:
            if start_date is None or end_date is None:
                return 0
            s = pd.to_datetime(start_date).date()
            e = pd.to_datetime(end_date).date()
            if s > e:
                return 0
            # np.busday_count counts days strictly in [start, end)
            # To include start and end as elapsed working days if end is on a working day:
            start_d = np.datetime64(s)
            end_d = np.datetime64(e)
            days = np.busday_count(start_d, end_d, holidays=self.holidays)
            # Add 1 if end date is itself a business day to be inclusive of end day
            if np.is_busday(end_d, holidays=self.holidays):
                days += 1
            return max(1, int(days))
        except Exception as e:
            logger.error(f"Error calculating working days between {start_date} and {end_date}: {e}")
            return 1

    def get_cycle_metadata(self, cycle: Dict[str, Any], as_of_date: Optional[Any] = None) -> Dict[str, Any]:
        """Provides rich metadata about a cycle including working days."""
        start = pd.to_datetime(cycle.get('start_date', '2026-10-01'))
        end = pd.to_datetime(cycle.get('end_date', '2026-12-31'))
        deadline = pd.to_datetime(cycle.get('final_deadline', end))
        
        as_of = pd.to_datetime(as_of_date) if as_of_date else pd.to_datetime('2026-10-23') # Default demo date or now
        
        total_working_days = self.calculate_working_days(start, end)
        end_for_elapsed = min(as_of, end)
        elapsed_working_days = self.calculate_working_days(start, end_for_elapsed) if as_of >= start else 0
        
        return {
            "name": cycle.get('name', 'Cycle'),
            "start_date": str(start.date()),
            "end_date": str(end.date()),
            "final_deadline": str(deadline.date()),
            "total_working_days": total_working_days,
            "elapsed_working_days": elapsed_working_days,
            "is_active": start <= as_of <= end,
            "as_of_date": str(as_of.date())
        }

    def compare_metrics(self, current_kpis: Dict[str, Any], prev_kpis: Dict[str, Any], mode: str = "like_for_like") -> List[Dict[str, Any]]:
        """
        Compares current vs previous cycle KPI values.
        Returns detailed comparison rows with:
        - metric_name
        - current_value
        - previous_value
        - absolute_change
        - percentage_change
        - pp_change (for percentage metrics)
        - desired_trend
        - status (favorable, unfavorable, neutral)
        """
        rows = []
        all_keys = list(set(list(current_kpis.keys()) + list(prev_kpis.keys())))
        
        for key in sorted(all_keys):
            curr_item = current_kpis.get(key, {})
            prev_item = prev_kpis.get(key, {})
            
            curr_val = curr_item.get('value')
            prev_val = prev_item.get('value')
            
            # Format metric display name
            display_name = curr_item.get('name', key.replace('kpi_', '').replace('_', ' ').title())
            unit = curr_item.get('unit', '%')
            desired_trend = curr_item.get('desired_trend', 'higher')
            
            abs_change = None
            pct_change = None
            pp_change = None
            favorable = None
            
            if curr_val is not None and prev_val is not None:
                abs_change = curr_val - prev_val
                if prev_val != 0:
                    pct_change = (abs_change / abs(prev_val)) * 100
                if unit == '%':
                    pp_change = abs_change # Percentage point difference
                
                if desired_trend == 'higher':
                    favorable = abs_change > 0
                elif desired_trend == 'lower':
                    favorable = abs_change < 0
                    
            rows.append({
                "metric_key": key,
                "metric_name": display_name,
                "current_value": curr_val,
                "previous_value": prev_val,
                "unit": unit,
                "abs_change": abs_change,
                "pct_change": pct_change,
                "pp_change": pp_change,
                "desired_trend": desired_trend,
                "is_favorable": favorable,
                "comparison_mode": mode
            })
            
        return rows
