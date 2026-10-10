import logging
import pandas as pd
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class RelationshipResolver:
    """Resolves and validates relationships between tasks and discrepancies."""

    def resolve(self, tasks_df: pd.DataFrame, disc_df: pd.DataFrame, task_id_col: str = 'sys_id', disc_link_col: str = 'linked_task') -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
        """
        Links discrepancies to tasks using verified identifiers.
        Do NOT join on application name alone.
        """
        if tasks_df.empty or disc_df.empty:
            return tasks_df, disc_df, {"orphaned_discrepancies": 0, "tasks_without_discrepancies": len(tasks_df)}
            
        # Ensure task sys_id is used to link
        valid_tasks = set(tasks_df[task_id_col].dropna().unique())
        
        # Check orphaned discrepancies (discrepancies that point to a non-existent task)
        has_valid_link = disc_df[disc_link_col].isin(valid_tasks)
        orphaned = disc_df[~has_valid_link]
        
        # Count discrepancies per task
        disc_counts = disc_df[has_valid_link].groupby(disc_link_col).size().reset_index(name='discrepancy_count')
        
        # Merge back to tasks
        tasks_with_counts = tasks_df.merge(disc_counts, left_on=task_id_col, right_on=disc_link_col, how='left')
        tasks_with_counts['discrepancy_count'] = tasks_with_counts['discrepancy_count'].fillna(0).astype(int)
        
        tasks_without_disc = tasks_with_counts[tasks_with_counts['discrepancy_count'] == 0]
        
        stats = {
            "orphaned_discrepancies": len(orphaned),
            "tasks_without_discrepancies": len(tasks_without_disc),
            "total_linked": len(disc_df[has_valid_link])
        }
        
        logger.info(f"Relationship stats: {stats}")
        return tasks_with_counts, disc_df, stats
