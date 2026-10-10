import logging
import pandas as pd
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DataNormalizer:
    """Normalizes raw data according to mappings and expected formats."""
    
    def __init__(self, field_mapping: Dict[str, str], tz_config: str = "UTC"):
        self.field_mapping = field_mapping
        self.tz_config = tz_config

    def apply_mapping(self, df: pd.DataFrame) -> pd.DataFrame:
        """Renames dataframe columns based on field_mapping."""
        return df.rename(columns=self.field_mapping)

    def standardize_timestamps(self, df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
        """Parses and standardizes timestamp formats, converting to configured timezone."""
        for col in date_cols:
            if col in df.columns:
                try:
                    df[col] = pd.to_datetime(df[col], errors='coerce', utc=True)
                    if self.tz_config != "UTC":
                        df[col] = df[col].dt.tz_convert(self.tz_config)
                    df[col] = df[col].dt.tz_localize(None)
                except Exception as e:
                    logger.error(f"Error converting column {col} to datetime: {e}")
        return df

    def standardize_status(self, df: pd.DataFrame, status_col: str, status_map: Dict[str, str]) -> pd.DataFrame:
        """Standardizes status values using a mapping dictionary."""
        if status_col in df.columns:
            df[status_col] = df[status_col].map(status_map).fillna(df[status_col])
        return df

    def clean_strings(self, df: pd.DataFrame, string_cols: List[str]) -> pd.DataFrame:
        """Trims whitespace and handles nulls for string columns."""
        for col in string_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().replace({'nan': None, 'None': None, '': None})
        return df

    def normalize(self, df: pd.DataFrame, date_cols: List[str], string_cols: List[str], status_col: str = None, status_map: Dict[str, str] = None) -> pd.DataFrame:
        """Applies all normalization steps."""
        if df.empty:
            return df
            
        df = self.apply_mapping(df)
        df = self.standardize_timestamps(df, date_cols)
        df = self.clean_strings(df, string_cols)
        
        if status_col and status_map:
            df = self.standardize_status(df, status_col, status_map)
            
        return df
