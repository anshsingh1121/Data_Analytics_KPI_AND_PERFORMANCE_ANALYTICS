import logging
import urllib.parse
from typing import Dict, Any, Optional, List
import requests
from src.connectors.api_client import ApiClient

logger = logging.getLogger(__name__)

def normalize_instance_url(url: str) -> str:
    """
    Normalizes a ServiceNow instance URL to scheme + hostname.
    Strips subpaths (/navpage.do, /now/nav/ui/home, etc.), trailing slashes, quotes, and whitespace.
    Ensures https:// scheme.
    """
    url = (url or "").strip().strip('"').strip("'")
    if not url:
        return ""
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip('/')

class ServiceNowClient(ApiClient):
    """ServiceNow-specific client extending ApiClient with enterprise security and URL sanitization."""

    def __init__(self, instance_url: str, username: str, password: str, **kwargs):
        clean_url = normalize_instance_url(instance_url)
        self.raw_instance_url = instance_url
        self.instance_url = clean_url
        base_url = f"{clean_url}/api/now"
        super().__init__(base_url=base_url, auth_type='basic', username=username, password=password, **kwargs)

    def test_connection(self, test_endpoint: Optional[str] = None) -> bool:
        """
        Tests connection and authentication against ServiceNow using a lightweight Table API query.
        Defaults to checking table/cert_task (or table/sys_user if not accessible).
        """
        candidates = [test_endpoint] if test_endpoint else ["table/cert_task", "table/sys_user", "table/sys_properties"]
        for ep in candidates:
            if not ep:
                continue
            try:
                self.get(ep, params={"sysparm_limit": 1})
                logger.info(f"ServiceNow connection test successful using endpoint: {ep}.")
                return True
            except requests.exceptions.SSLError as ssl_err:
                # SSL error must be propagated to diagnostic handler
                raise ssl_err
            except Exception as e:
                logger.debug(f"Connection test query to '{ep}' returned: {e}")
        return False

    def test_table_access(self, table_name: str) -> bool:
        """Tests if the user has access to a specific table."""
        endpoint = f"table/{table_name}"
        params = {"sysparm_limit": 1}
        try:
            self.get(endpoint, params=params)
            logger.info(f"Table access test successful for {table_name}.")
            return True
        except requests.exceptions.SSLError as ssl_err:
            raise ssl_err
        except Exception as e:
            logger.error(f"Table access test failed for {table_name}: {e}")
            return False

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Inspects the schema of a table using sys_dictionary."""
        endpoint = "table/sys_dictionary"
        params = {
            "sysparm_query": f"name={table_name}",
            "sysparm_fields": "element,internal_type,column_label,reference",
            "sysparm_display_value": "false"
        }
        response = self.get_paginated(endpoint, params=params, limit_param="sysparm_limit", offset_param="sysparm_offset")
        return response

    def extract_table(self, table_name: str, query: Optional[str] = None, fields: Optional[List[str]] = None, display_value: str = "all", limit: int = 1000) -> List[Dict[str, Any]]:
        """Extracts records from a ServiceNow table."""
        endpoint = f"table/{table_name}"
        params = {
            "sysparm_display_value": display_value,
            "sysparm_limit": limit
        }
        if query:
            params["sysparm_query"] = query
        if fields:
            params["sysparm_fields"] = ",".join(fields)
            
        return self.get_paginated(endpoint, params=params, limit_param="sysparm_limit", offset_param="sysparm_offset")

    def get_record_count(self, table_name: str, query: Optional[str] = None) -> int:
        """Gets record count using stats API."""
        endpoint = f"stats/{table_name}"
        params = {
            "sysparm_count": "true"
        }
        if query:
            params["sysparm_query"] = query
            
        try:
            response = self.get(endpoint, params=params)
            return int(response.get('result', {}).get('stats', {}).get('count', 0))
        except Exception as e:
            logger.debug(f"Stats API unavailable for {table_name}: {e}")
            return -1
