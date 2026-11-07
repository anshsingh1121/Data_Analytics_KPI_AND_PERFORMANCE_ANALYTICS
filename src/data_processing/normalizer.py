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

    @staticmethod
    def parse_datetime_safely(series: pd.Series) -> pd.Series:
        """
        Parses a date series ensuring day and month are NEVER interchanged.
        1. If already datetime dtype, strips tz if present and returns.
        2. If strings start with 4-digit year (YYYY-MM-DD or YYYY/MM/DD), parses as pure ISO (unambiguous).
        3. If strings are slash/dash separated (DD/MM/YYYY vs MM/DD/YYYY), inspects column tokens:
           - If any token 1 > 12: day is first (DD/MM/YYYY).
           - If any token 2 > 12: month is first (MM/DD/YYYY).
        4. Strips timezone to return timezone-naive datetimes for consistent comparisons.
        """
        if series is None or series.empty:
            return pd.to_datetime(series, errors='coerce')

        if pd.api.types.is_datetime64_any_dtype(series):
            if hasattr(series.dt, 'tz') and series.dt.tz is not None:
                return series.dt.tz_localize(None)
            return series

        clean_s = series.astype(str).str.strip()
        sample = clean_s[~clean_s.isin(['nan', 'None', '', 'NaT', 'null', 'NULL'])].dropna()
        if sample.empty:
            return pd.to_datetime(series, errors='coerce')

        # Pure ISO format: YYYY-MM-DD or YYYY/MM/DD
        if sample.str.match(r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}').all():
            res = pd.to_datetime(series, errors='coerce', format='mixed')
            if hasattr(res.dt, 'tz') and res.dt.tz is not None:
                res = res.dt.tz_localize(None)
            return res

        # Check for DD/MM/YYYY vs MM/DD/YYYY using token boundary inspection
        tokens = sample.str.extract(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})')
        if not tokens.dropna().empty:
            t1_max = pd.to_numeric(tokens[0], errors='coerce').max()
            t2_max = pd.to_numeric(tokens[1], errors='coerce').max()
            if t1_max > 12 and t2_max <= 12:
                # Definitely DD/MM/YYYY
                res = pd.to_datetime(series, errors='coerce', dayfirst=True)
                if hasattr(res.dt, 'tz') and res.dt.tz is not None:
                    res = res.dt.tz_localize(None)
                return res
            elif t2_max > 12 and t1_max <= 12:
                # Definitely MM/DD/YYYY
                res = pd.to_datetime(series, errors='coerce', dayfirst=False)
                if hasattr(res.dt, 'tz') and res.dt.tz is not None:
                    res = res.dt.tz_localize(None)
                return res

        res = pd.to_datetime(series, errors='coerce', format='mixed')
        if hasattr(res.dt, 'tz') and res.dt.tz is not None:
            res = res.dt.tz_localize(None)
        return res

    def standardize_timestamps(self, df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
        """Parses and standardizes timestamp formats, converting to configured timezone."""
        for col in date_cols:
            if col in df.columns:
                try:
                    parsed = self.parse_datetime_safely(df[col])
                    if self.tz_config != "UTC":
                        df[col] = parsed.dt.tz_localize('UTC').dt.tz_convert(self.tz_config).dt.tz_localize(None)
                    else:
                        df[col] = parsed
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
