import logging
import pandas as pd
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ExceptionAnalyzer:
    """Analyzes discrepancy patterns and exception resolution."""

    def analyze(self, disc_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyzes discrepancies."""
        if disc_df.empty:
            return {}
            
        result = {
            "total_discrepancies": len(disc_df)
        }
        
        # Breakdown by field if available
        if 'element' in disc_df.columns:
            result['by_field'] = disc_df['element'].value_counts().to_dict()
            
        # Breakdown by category if available
        if 'category' in disc_df.columns:
            result['by_category'] = disc_df['category'].value_counts().to_dict()
            
        # Unresolved
        if 'state' in disc_df.columns:
            unresolved = disc_df[disc_df['state'] != 'Resolved']
            result['unresolved_count'] = len(unresolved)
            
        return result
