import logging
import pandas as pd
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

class DiscrepancyExtractor:
    """Extracts discrepancy data via API or loads from demo data."""

    def __init__(self, api_client: Any, config: Dict[str, Any], field_mapping: Dict[str, str]):
        self.api_client = api_client
        self.config = config
        self.field_mapping = field_mapping
        self.table_name = self.config.get('discrepancy_table', 'u_failed_data_certifications')

    def extract(self, start_date: Optional[str] = None, end_date: Optional[str] = None, full_refresh: bool = False) -> pd.DataFrame:
        """Extracts discrepancy records."""
        logger.info(f"Starting discrepancy extraction. Full refresh: {full_refresh}")
        
        query_parts = []
        if not full_refresh:
            if start_date:
                query_parts.append(f"sys_created_on>={start_date}")
            if end_date:
                query_parts.append(f"sys_created_on<={end_date}")
                
        query = "^".join(query_parts) if query_parts else None
        
        try:
            records = self.api_client.extract_table(
                table_name=self.table_name,
                query=query,
                display_value="all"
            )
            df = pd.DataFrame(records)
            if not df.empty:
                logger.info(f"Extracted {len(df)} raw discrepancy records.")
                df = self._apply_mappings(df)
            else:
                logger.warning("No discrepancy records found.")
            return df
        except Exception as e:
            logger.error(f"Error during discrepancy extraction: {e}")
            return pd.DataFrame()

    def _apply_mappings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies basic structural mappings before full normalization."""
        mapped = df.rename(columns=self.field_mapping)
        return mapped
