import logging
import os
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CsvExporter:
    """Exports individual analytical outputs and reports to CSV format."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export(self, df: pd.DataFrame, filename: str) -> str:
        """Exports a single dataframe to CSV."""
        if not filename.endswith('.csv'):
            filename = f"{filename}.csv"
        filepath = os.path.join(self.output_dir, filename)
        try:
            df.to_csv(filepath, index=False)
            logger.info(f"Exported CSV: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to write CSV {filename}: {e}")
            return ""

    def export_all(self, df_dict: Dict[str, pd.DataFrame], timestamp_prefix: bool = True) -> List[str]:
        """Exports multiple dataframes to cycle- and timestamp-aware CSVs."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepaths = []
        
        for name, df in df_dict.items():
            if df is not None and not df.empty:
                filename = f"{name}_{timestamp}.csv" if timestamp_prefix else f"{name}.csv"
                filepath = os.path.join(self.output_dir, filename)
                try:
                    df.to_csv(filepath, index=False)
                    filepaths.append(filepath)
                    # Also save a canonical copy without timestamp for easy loading
                    canonical_path = os.path.join(self.output_dir, f"{name}.csv")
                    df.to_csv(canonical_path, index=False)
                except Exception as e:
                    logger.error(f"Failed to write CSV {filename}: {e}")
                    
        return filepaths
