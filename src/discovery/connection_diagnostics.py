import requests
from src.connectors.ssl_helper import diagnose_ssl_error

logger = logging.getLogger(__name__)

class ConnectionDiagnostics:
    """Tool for diagnosing API connections, SSL/TLS certificates, authentication, and table permissions."""

    def __init__(self, api_client: Any, config: Dict[str, Any]):
        self.api_client = api_client
        self.config = config
        self.task_table = self.config.get('task_table', 'cert_task')
        self.disc_table = self.config.get('discrepancy_table', 'u_failed_data_certifications')

    def run_diagnostics(self) -> Dict[str, Any]:
        """Runs full suite of connection diagnostics with detailed root cause analysis."""
        results = {
            "api_connectivity": False,
            "auth_valid": False,
            "ssl_valid": True,
            "ssl_diagnostic": None,
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
                results["suggestions"].append("Could not verify ServiceNow connection. Verify your instance URL and that your credentials are valid.")
                return results

            # Test table access
            if hasattr(self.api_client, 'test_table_access'):
                if self.api_client.test_table_access(self.task_table):
                    results["task_table_access"] = True
                else:
                    results["suggestions"].append(f"User lacks read access to '{self.task_table}'. Check role permissions in ServiceNow.")
                    
                if self.api_client.test_table_access(self.disc_table):
                    results["disc_table_access"] = True
                else:
                    results["suggestions"].append(f"User lacks read access to '{self.disc_table}'. Check role permissions in ServiceNow.")

        except requests.exceptions.SSLError as ssl_err:
            results["ssl_valid"] = False
            base_url = getattr(self.api_client, 'base_url', '')
            diag = diagnose_ssl_error(ssl_err, base_url)
            results["ssl_diagnostic"] = diag
            logger.error(f"SSL diagnostic triggered: {diag['category']}")
            for step in diag.get('actionable_steps', []):
                results["suggestions"].append(f"[SSL Fix] {step}")

        except requests.exceptions.HTTPError as http_err:
            code = http_err.response.status_code if http_err.response else 0
            if code == 401:
                results["auth_valid"] = False
                results["suggestions"].append("[Auth Error] 401 Unauthorized. Check your API_USERNAME and API_PASSWORD in .env.")
            elif code == 403:
                results["suggestions"].append(f"[Permission Error] 403 Forbidden. Your account does not have Table API read access.")
            elif code == 404:
                results["suggestions"].append(f"[URL Error] 404 Not Found. Ensure API_BASE_URL is 'https://<instance>.service-now.com' without extra paths.")
            else:
                results["suggestions"].append(f"HTTP Error {code}: {http_err}")

        except requests.exceptions.ConnectionError as conn_err:
            results["api_connectivity"] = False
            results["suggestions"].append(
                "[Network Error] Connection failed. Verify you are connected to corporate VPN or that the instance URL is correct."
            )

        except Exception as e:
            logger.error(f"Diagnostics failed: {e}")
            results["suggestions"].append(f"Unexpected error: {str(e)}")
            
        return results
