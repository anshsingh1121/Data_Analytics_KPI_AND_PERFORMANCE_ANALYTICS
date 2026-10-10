import logging
import pandas as pd
from typing import Dict, Any, List
import yaml
import os

logger = logging.getLogger(__name__)

class SchemaDiscovery:
    """Discovers schema, samples records, and generates mapping suggestions."""

    def __init__(self, api_client: Any, config: Dict[str, Any]):
        self.api_client = api_client
        self.config = config
        self.task_table = self.config.get('task_table', 'cert_task')
        self.disc_table = self.config.get('discrepancy_table', 'u_failed_data_certifications')

    def get_field_metadata(self, table_name: str) -> List[Dict[str, Any]]:
        """Retrieves field metadata from ServiceNow sys_dictionary."""
        try:
            return self.api_client.get_table_schema(table_name)
        except Exception as e:
            logger.error(f"Failed to get metadata for {table_name}: {e}")
            return []

    def sample_records(self, table_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Samples records to detect data types and values."""
        try:
            return self.api_client.extract_table(table_name, limit=limit)
        except Exception as e:
            logger.error(f"Failed to sample records for {table_name}: {e}")
            return []

    def generate_mapping_suggestions(self, metadata: List[Dict[str, Any]], sample_data: List[Dict[str, Any]], table_type: str) -> Dict[str, str]:
        """Generates suggestions based on common field names."""
        suggestions = {}
        
        # Simple heuristic mapping based on common names
        common_mappings = {
            'sys_id': 'sys_id',
            'state': 'state',
            'assigned_to': 'assigned_to',
            'due_date': 'due_date',
            'sys_created_on': 'sys_created_on',
            'closed_at': 'closed_at'
        }
        
        fields = set(m.get('element') for m in metadata if m.get('element'))
        if not fields and sample_data:
            fields = set(sample_data[0].keys())
            
        for f in fields:
            if f in common_mappings:
                suggestions[f] = common_mappings[f]
                
        return suggestions

    def update_field_mapping_yaml(self, new_suggestions: Dict[str, str], filepath: str):
        """Creates or updates field_mapping.yaml without overwriting confirmed mappings."""
        existing_mappings = {}
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                existing_mappings = yaml.safe_load(f) or {}
                
        # Merge, keeping existing mappings
        updated = existing_mappings.copy()
        for k, v in new_suggestions.items():
            if k not in updated:
                updated[k] = v
                
        with open(filepath, 'w') as f:
            yaml.dump(updated, f, default_flow_style=False)
            
        logger.info(f"Updated field mapping at {filepath}")

    def generate_report(self) -> Dict[str, Any]:
        """Generates a full schema discovery report."""
        task_meta = self.get_field_metadata(self.task_table)
        disc_meta = self.get_field_metadata(self.disc_table)
        
        task_sample = self.sample_records(self.task_table)
        disc_sample = self.sample_records(self.disc_table)
        
        task_suggestions = self.generate_mapping_suggestions(task_meta, task_sample, "task")
        disc_suggestions = self.generate_mapping_suggestions(disc_meta, disc_sample, "discrepancy")
        
        return {
            "task_table": {
                "field_count": len(task_meta) if task_meta else len(task_sample[0].keys()) if task_sample else 0,
                "suggestions": task_suggestions
            },
            "discrepancy_table": {
                "field_count": len(disc_meta) if disc_meta else len(disc_sample[0].keys()) if disc_sample else 0,
                "suggestions": disc_suggestions
            }
        }
