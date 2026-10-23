import logging
import pandas as pd
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ProductivityAnalyzer:
    """Analyzes per-certifier metrics and workload."""

    def analyze(self, tasks_df: pd.DataFrame, working_days: int) -> pd.DataFrame:
        """Returns a DataFrame with certifier productivity stats."""
        cert_col = 'assigned_to' if 'assigned_to' in tasks_df.columns else ('certifier' if 'certifier' in tasks_df.columns else None)
        if tasks_df.empty or not cert_col:
            return pd.DataFrame()
            
        # Total assigned
        assigned = tasks_df.groupby(cert_col).size().rename('total_assigned')
        
        # Completed
        state_col = 'state' if 'state' in tasks_df.columns else ('status' if 'status' in tasks_df.columns else None)
        completed_mask = tasks_df[state_col].isin(["Closed Complete", "Closed Incomplete"]) if state_col else pd.Series(False, index=tasks_df.index)
        completed = tasks_df[completed_mask].groupby(cert_col).size().rename('total_completed')
        
        # Combine
        prod_df = pd.concat([assigned, completed], axis=1).fillna(0)
        
        # Daily rate
        if working_days > 0:
            prod_df['daily_completion_rate'] = prod_df['total_completed'] / working_days
        else:
            prod_df['daily_completion_rate'] = 0.0
            
        return prod_df.reset_index()
