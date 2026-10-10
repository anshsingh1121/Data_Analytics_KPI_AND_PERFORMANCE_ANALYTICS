import logging
import pandas as pd
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class QualityChecker:
    """Framework for running quality checks on extracted data."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def check_completeness(self, df: pd.DataFrame, expected_fields: List[str]) -> Dict[str, Any]:
        """Calculates completeness scores based on presence of expected fields."""
        if df.empty:
            return {"overall_score": 0.0, "field_scores": {}}
            
        field_scores = {}
        for field in expected_fields:
            if field in df.columns:
                valid_count = df[field].notna().sum()
                field_scores[field] = (valid_count / len(df)) * 100
            else:
                field_scores[field] = 0.0
                
        overall = sum(field_scores.values()) / len(expected_fields) if expected_fields else 0.0
        
        return {
            "overall_score": overall,
            "field_scores": field_scores
        }

    def run_checks(self, tasks_df: pd.DataFrame, disc_df: pd.DataFrame) -> Dict[str, Any]:
        """Runs all quality checks on both tables and aggregates results."""
        task_fields = self.config.get("task_required_fields", ["sys_id", "state", "assigned_to"])
        disc_fields = self.config.get("disc_required_fields", ["sys_id", "linked_task", "state"])
        
        task_qa = self.check_completeness(tasks_df, task_fields)
        disc_qa = self.check_completeness(disc_df, disc_fields)
        
        report = {
            "task_data_completeness": task_qa,
            "discrepancy_data_completeness": disc_qa,
            "total_tasks": len(tasks_df),
            "total_discrepancies": len(disc_df)
        }
        
        return report
