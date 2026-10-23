import logging
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TaskExtractor:
    """Extracts certification tasks via API or loads from demo data."""

    def __init__(self, api_client: Any, config: Dict[str, Any], field_mapping: Dict[str, str]):
        self.api_client = api_client
        self.config = config or {}
        self.field_mapping = field_mapping or {}
        self.table_name = (
            self.config.get('tables', {}).get('cert_task')
            or self.config.get('task_table')
            or 'cert_task'
        )

    def extract(self, start_date: Optional[str] = None, end_date: Optional[str] = None, full_refresh: bool = False, custom_query: Optional[str] = None) -> pd.DataFrame:
        """Extracts task records from ServiceNow."""
        logger.info(f"Starting task extraction from table '{self.table_name}'. Full refresh: {full_refresh}")
        
        query_parts = []
        configured_query = self.config.get('query', {}).get('cert_task') if isinstance(self.config.get('query'), dict) else None
        if custom_query:
            query_parts.append(custom_query)
        elif configured_query:
            query_parts.append(configured_query)
        elif not full_refresh:
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
                logger.info(f"Extracted {len(df)} raw task records from '{self.table_name}'.")
                df = self._apply_mappings(df)
            else:
                logger.warning(f"No task records returned from table '{self.table_name}'.")
            return df
        except Exception as e:
            logger.error(f"Error during task extraction from '{self.table_name}': {e}")
            raise e

    def _apply_mappings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Applies basic structural mappings before full normalization, preventing column collisions."""
        safe_map = {k: v for k, v in self.field_mapping.items() if k in df.columns and v not in df.columns}
        mapped = df.rename(columns=safe_map)
        if mapped.columns.duplicated().any():
            mapped = mapped.loc[:, ~mapped.columns.duplicated()].copy()
        return mapped
