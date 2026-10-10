import logging
import pandas as pd
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ProductivityAnalyzer:
    """Analyzes per-certifier metrics and workload."""

    def analyze(self, tasks_df: pd.DataFrame, working_days: int) -> pd.DataFrame:
        """Returns a DataFrame with certifier productivity stats."""
        if tasks_df.empty or 'assigned_to' not in tasks_df.columns:
            return pd.DataFrame()
            
        # Total assigned
        assigned = tasks_df.groupby('assigned_to').size().rename('total_assigned')
        
        # Completed
        completed_mask = tasks_df['state'].isin(["Closed Complete"])
        completed = tasks_df[completed_mask].groupby('assigned_to').size().rename('total_completed')
        
        # Combine
        prod_df = pd.concat([assigned, completed], axis=1).fillna(0)
        
        # Daily rate
        if working_days > 0:
            prod_df['daily_completion_rate'] = prod_df['total_completed'] / working_days
        else:
            prod_df['daily_completion_rate'] = 0.0
            
        return prod_df.reset_index()
