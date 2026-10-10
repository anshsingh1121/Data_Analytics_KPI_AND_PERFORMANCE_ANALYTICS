import logging
from typing import Dict, Any, Optional, List, Generator
from src.connectors.base_client import BaseClient

logger = logging.getLogger(__name__)

class ApiClient(BaseClient):
    """Generic API client extending BaseClient with auth and pagination."""

    def __init__(self, base_url: str, auth_type: str = 'basic', username: Optional[str] = None, password: Optional[str] = None, token: Optional[str] = None, **kwargs):
        super().__init__(base_url, **kwargs)
        self.auth_type = auth_type
        
        if self.auth_type == 'basic' and username and password:
            self.session.auth = (username, password)
        elif self.auth_type == 'oauth' and token:
            self.set_headers({"Authorization": f"Bearer {token}"})
        else:
            logger.warning("No valid authentication provided for ApiClient.")

    def test_connection(self, test_endpoint: str = "") -> bool:
        """Tests the API connection and authentication."""
        try:
            self.get(test_endpoint)
            logger.info("Connection test successful.")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_paginated(self, endpoint: str, params: Optional[Dict[str, Any]] = None, limit_param: str = 'limit', offset_param: str = 'offset', result_key: str = 'result', max_records: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetches all records using offset-based pagination."""
        if params is None:
            params = {}
            
        all_records = []
        offset = 0
        limit = params.get(limit_param, 100)
        
        while True:
            params[offset_param] = offset
            params[limit_param] = limit
            
            response = self.get(endpoint, params=params)
            records = response.get(result_key, [])
            
            if not records:
                break
                
            all_records.extend(records)
            logger.info(f"Fetched {len(records)} records. Total: {len(all_records)}")
            
            if len(records) < limit:
                break
                
            if max_records and len(all_records) >= max_records:
                all_records = all_records[:max_records]
                break
                
            offset += limit
            
        return all_records

    def get_record_count(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Returns the total number of records matching the filters."""
        # Typically handled via a specific endpoint or headers in some APIs
        # As a fallback, this might issue a request with limit=1 to get headers
        raise NotImplementedError("Record count depends on the specific API implementation.")
