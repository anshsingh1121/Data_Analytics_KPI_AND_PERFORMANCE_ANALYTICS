import logging
from typing import Dict, Any, List
import pandas as pd

logger = logging.getLogger(__name__)

class FieldMapper:
    """Utilities for field mapping and validation."""

    def __init__(self, mapping: Dict[str, str]):
        self.mapping = mapping

    def apply_mapping(self, df: pd.DataFrame) -> pd.DataFrame:
        """Maps DataFrame columns based on internal mapping."""
        return df.rename(columns=self.mapping)

    def validate_completeness(self, available_fields: List[str], required_fields: List[str]) -> Dict[str, Any]:
        """Validates that all required business fields are mapped."""
        mapped_values = set(self.mapping.values())
        
        missing = [f for f in required_fields if f not in mapped_values]
        unmapped_available = [f for f in available_fields if f not in self.mapping]
        
        is_complete = len(missing) == 0
        
        if missing:
            logger.warning(f"Missing required fields in mapping: {missing}")
            
        return {
            "is_complete": is_complete,
            "missing_required_fields": missing,
            "unmapped_available_fields": unmapped_available
        }
