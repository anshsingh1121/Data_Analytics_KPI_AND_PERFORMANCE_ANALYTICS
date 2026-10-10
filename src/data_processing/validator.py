import logging
import pandas as pd
from typing import Dict, Any, Tuple, List

logger = logging.getLogger(__name__)

class DataValidator:
    """Validates normalized data."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def check_required_fields(self, df: pd.DataFrame, required_fields: List[str]) -> pd.Series:
        """Checks if required fields are present and not null."""
        missing = pd.Series(False, index=df.index)
        for field in required_fields:
            if field not in df.columns:
                logger.error(f"Required field {field} missing from dataframe.")
                missing = True
                break
            missing = missing | df[field].isna()
        return missing

    def check_duplicates(self, df: pd.DataFrame, id_col: str) -> pd.Series:
        """Detects duplicate IDs."""
        if id_col not in df.columns:
            return pd.Series(False, index=df.index)
        return df.duplicated(subset=[id_col], keep=False)

    def check_date_sequences(self, df: pd.DataFrame, start_col: str, end_col: str) -> pd.Series:
        """Validates that start date <= end date."""
        if start_col in df.columns and end_col in df.columns:
            start = pd.to_datetime(df[start_col])
            end = pd.to_datetime(df[end_col])
            return start > end
        return pd.Series(False, index=df.index)

    def validate(self, df: pd.DataFrame, id_col: str, required_fields: List[str], date_seq_cols: List[Tuple[str, str]]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Runs all validations and returns valid, invalid, and excluded records."""
        if df.empty:
            return df, pd.DataFrame(), pd.DataFrame()
            
        is_missing = self.check_required_fields(df, required_fields)
        is_duplicate = self.check_duplicates(df, id_col)
        
        is_bad_seq = pd.Series(False, index=df.index)
        for start, end in date_seq_cols:
            is_bad_seq = is_bad_seq | self.check_date_sequences(df, start, end)
            
        invalid_mask = is_missing | is_duplicate | is_bad_seq
        
        valid_df = df[~invalid_mask].copy()
        invalid_df = df[invalid_mask].copy()
        
        # Excluded records logic could depend on specific status or config (e.g. cancelled)
        exclude_statuses = self.config.get("exclude_statuses", ["Cancelled"])
        status_col = self.config.get("status_col", "state")
        
        if status_col in valid_df.columns:
            excluded_mask = valid_df[status_col].isin(exclude_statuses)
            excluded_df = valid_df[excluded_mask].copy()
            valid_df = valid_df[~excluded_mask].copy()
        else:
            excluded_df = pd.DataFrame(columns=valid_df.columns)
            
        return valid_df, invalid_df, excluded_df
