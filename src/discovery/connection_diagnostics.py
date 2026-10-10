import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class ConnectionDiagnostics:
    """Tool for diagnosing API connections and permissions."""

    def __init__(self, api_client: Any, config: Dict[str, Any]):
        self.api_client = api_client
        self.config = config
        self.task_table = self.config.get('task_table', 'cert_task')
        self.disc_table = self.config.get('discrepancy_table', 'u_failed_data_certifications')

    def run_diagnostics(self) -> Dict[str, Any]:
        """Runs full suite of connection diagnostics."""
        results = {
            "api_connectivity": False,
            "auth_valid": False,
            "task_table_access": False,
            "disc_table_access": False,
            "suggestions": []
        }
        
        try:
            # Test connectivity and auth
            if hasattr(self.api_client, 'test_connection') and self.api_client.test_connection():
                results["api_connectivity"] = True
                results["auth_valid"] = True
            else:
                results["suggestions"].append("Check API URL, VPN, or credentials.")
                return results

            # Test table access
            if hasattr(self.api_client, 'test_table_access'):
                if self.api_client.test_table_access(self.task_table):
                    results["task_table_access"] = True
                else:
                    results["suggestions"].append(f"User lacks read access to {self.task_table}.")
                    
                if self.api_client.test_table_access(self.disc_table):
                    results["disc_table_access"] = True
                else:
                    results["suggestions"].append(f"User lacks read access to {self.disc_table}.")
                    
        except Exception as e:
            logger.error(f"Diagnostics failed: {e}")
            results["suggestions"].append(f"Unexpected error: {str(e)}")
            
        return results
