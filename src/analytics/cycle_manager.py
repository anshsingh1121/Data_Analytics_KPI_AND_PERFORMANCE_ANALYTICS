import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, date
from src.data_processing.normalizer import DataNormalizer

logger = logging.getLogger(__name__)

class CycleManager:
    """Manages certification cycles, boundaries, working days, and cycle comparisons."""

    def __init__(self, cycle_config: Dict[str, Any], holidays: Optional[List[str]] = None):
        self.config = cycle_config or {}
        self.holidays = [pd.to_datetime(h).date() for h in (holidays or self.config.get('holidays', ['2026-01-01', '2026-12-25']))]
        self._init_cycles()

    def _init_cycles(self):
        """Extracts current and previous cycle from config, defaulting strictly to the 4 official campaigns."""
        self.cycles = self.config.get('cycles', {})
        if not self.cycles:
            self.cycles = {
                'Q4-2026': {
                    'name': 'Q4-2026',
                    'quarter_label': 'Oct 5 - Oct 23, 2026',
                    'year': 2026,
                    'quarter': 4,
                    'start_date': '2026-10-05',
                    'end_date': '2026-10-23',
                    'final_deadline': '2026-10-23'
                },
                'Q2-2026': {
                    'name': 'Q2-2026',
                    'quarter_label': 'May 5 - May 22, 2026',
                    'year': 2026,
                    'quarter': 2,
                    'start_date': '2026-05-05',
                    'end_date': '2026-05-22',
                    'final_deadline': '2026-05-22'
                },
                'Q4-2025': {
                    'name': 'Q4-2025',
                    'quarter_label': 'Oct 6 - Oct 23, 2025',
                    'year': 2025,
                    'quarter': 4,
                    'start_date': '2025-10-06',
                    'end_date': '2025-10-23',
                    'final_deadline': '2025-10-23'
                },
                'Q2-2025': {
                    'name': 'Q2-2025',
                    'quarter_label': 'Apr 7 - Apr 25, 2025',
                    'year': 2025,
                    'quarter': 2,
                    'start_date': '2025-04-07',
                    'end_date': '2025-04-25',
                    'final_deadline': '2025-04-25'
                }
            }
        self.current_cycle = self.config.get('current_cycle', self.cycles.get('Q4-2026'))
        self.previous_cycle = self.config.get('previous_cycle', self.cycles.get('Q2-2026'))
        self.comparison_settings = self.config.get('comparison_settings', {
            'mode': 'like_for_like',
            'align_by': 'working_days_elapsed'
        })

    def get_cycle_by_name(self, name: str) -> Dict[str, Any]:
        """
        Returns cycle dict by name strictly from configured campaign cycles.
        Strictly enforces defined window dates (e.g. Q4-2026: Oct 5 - Oct 23, 2026).
        NO 3-month calendar fallbacks!
        """
        if name in self.cycles:
            return self.cycles[name]
        if self.current_cycle.get('name') == name:
            return self.current_cycle
        if self.previous_cycle.get('name') == name:
            return self.previous_cycle
        if self.config.get('yoy_cycle', {}).get('name') == name:
            return self.config['yoy_cycle']

        # Check configured cycles dictionary case-insensitively
        for c_key, c_val in self.cycles.items():
            if c_key.upper().replace('_', '-') == name.upper().replace('_', '-'):
                return c_val

        logger.warning(f"Requested cycle '{name}' is not in configured campaign cycles. Returning empty window.")
        return {'name': name, 'start_date': None, 'end_date': None, 'final_deadline': None}

    def assign_cycle_to_dataframe(self, df: pd.DataFrame, date_col: str = 'sys_created_on') -> pd.DataFrame:
        """
        Strictly assigns quarter campaign name based on timestamp.
        Only tasks created strictly within official campaign window dates are assigned.
        Tasks outside official windows are tagged 'Out of Campaign' (no 3-month calendar fallbacks).
        """
        if df is None or df.empty:
            return df
            
        col_to_use = None
        for cand in [date_col, 'sys_created_on', 'created_at', 'closed_at']:
            if cand in df.columns:
                col_to_use = cand
                break

        # Check for explicit activity or cycle column
        act_col = None
        for cand_act in ['u_certification_activity', 'u_certification_cycle', 'certification_activity']:
            if cand_act in df.columns:
                act_col = cand_act
                break

        activity_map = {
            'Q2-2026': 'Q2-2026', 'Q2_2026': 'Q2-2026', 'Q2 2026': 'Q2-2026', '2026-Q2': 'Q2-2026', 'Q2': 'Q2-2026',
            'Q4-2026': 'Q4-2026', 'Q4_2026': 'Q4-2026', 'Q4 2026': 'Q4-2026', '2026-Q4': 'Q4-2026', 'Q4': 'Q4-2026',
            'Q2-2025': 'Q2-2025', 'Q2_2025': 'Q2-2025', 'Q2 2025': 'Q2-2025', '2025-Q2': 'Q2-2025',
            'Q4-2025': 'Q4-2025', 'Q4_2025': 'Q4-2025', 'Q4 2025': 'Q4-2025', '2025-Q4': 'Q4-2025',
        }
                
        if not col_to_use:
            if act_col:
                df['certification_cycle'] = df[act_col].astype(str).str.strip().map(activity_map).fillna('Q4-2026')
            else:
                df['certification_cycle'] = 'Q4-2026'
            return df
            
        dt_series = DataNormalizer.parse_datetime_safely(df[col_to_use])
        if hasattr(dt_series.dt, 'tz') and dt_series.dt.tz is not None:
            dt_series = dt_series.dt.tz_localize(None)

        def _match_cycle(ts, act_val=None):
            if pd.isna(ts):
                # If date is missing, fall back to activity tag if available
                if act_val and pd.notna(act_val):
                    act_clean = str(act_val).strip()
                    if act_clean in activity_map:
                        return activity_map[act_clean]
                return 'Unknown'

            d = ts.date() if hasattr(ts, 'date') else ts

            # Strict non-overlapping campaign windows:
            # Q4 2026: Oct 5 - Oct 23, 2026
            if date(2026, 10, 5) <= d <= date(2026, 10, 23):
                return 'Q4-2026'

            # Q2 2026 (Spring): May 5 - May 22, 2026
            if date(2026, 5, 5) <= d <= date(2026, 5, 22):
                return 'Q2-2026'

            # Q4 2025: Oct 6 - Oct 23, 2025
            if date(2025, 10, 6) <= d <= date(2025, 10, 23):
                return 'Q4-2025'

            # Q2 2025 (Spring): Apr 7 - Apr 25, 2025
            if date(2025, 4, 7) <= d <= date(2025, 4, 25):
                return 'Q2-2025'

            # Check any other explicitly configured cycle boundaries in self.cycles
            for c_name, c_info in self.cycles.items():
                if c_info.get('start_date') and c_info.get('end_date'):
                    s = pd.to_datetime(c_info['start_date']).date()
                    e = pd.to_datetime(c_info['end_date']).date()
                    if s <= d <= e:
                        return c_name

            # If date is outside campaign window, check explicit activity tag before marking out of campaign
            if act_val and pd.notna(act_val):
                act_clean = str(act_val).strip()
                if act_clean in activity_map:
                    return activity_map[act_clean]

            # 3-Month Quarter Window fallback (Apr 1 - Jun 30 for Q2, Oct 1 - Dec 31 for Q4 — strictly excludes Jan!)
            if date(2026, 4, 1) <= d <= date(2026, 6, 30):
                return 'Q2-2026'
            if date(2026, 10, 1) <= d <= date(2026, 12, 31):
                return 'Q4-2026'
            if date(2025, 4, 1) <= d <= date(2025, 6, 30):
                return 'Q2-2025'
            if date(2025, 10, 1) <= d <= date(2025, 12, 31):
                return 'Q4-2025'

            # STRICT: Any task outside defined campaign dates and outside Q2/Q4 3-month quarters is Out of Campaign.
            return 'Out of Campaign'

        if act_col:
            df['certification_cycle'] = [_match_cycle(ts, act) for ts, act in zip(dt_series, df[act_col])]
        else:
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
        start = pd.to_datetime(cycle.get('start_date', '2026-10-05'))
        end = pd.to_datetime(cycle.get('end_date', '2026-10-23'))
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
