import logging
import pandas as pd
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TrendAnalyzer:
    """Calculates daily trends and cumulative progress for key metrics."""
    
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

    def compare_cycles(self, current_trends: pd.DataFrame, previous_trends: pd.DataFrame) -> pd.DataFrame:
        """Compares current vs previous cycle trends."""
        # This typically involves aligning them by 'elapsed_working_days' which should be pre-calculated
        # For simplicity, returning merged representation if day index exists
        if 'elapsed_working_day' in current_trends.columns and 'elapsed_working_day' in previous_trends.columns:
            merged = pd.merge(
                current_trends, 
                previous_trends, 
                on='elapsed_working_day', 
                how='outer',
                suffixes=('_current', '_previous')
            )
            return merged.sort_values('elapsed_working_day')
        return current_trends # fallback
