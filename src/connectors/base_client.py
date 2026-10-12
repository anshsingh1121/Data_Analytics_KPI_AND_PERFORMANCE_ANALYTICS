import logging
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Dict, Any, Optional
from src.connectors.ssl_helper import configure_session_ssl, diagnose_ssl_error

logger = logging.getLogger(__name__)

class BaseClient:
    """A reusable REST client base class with enterprise security and SSL resilience."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 30,
        retries: int = 3,
        backoff_factor: float = 0.3,
        verify_tls: bool = True,
        ca_bundle: Optional[str] = None,
        proxies: Optional[Dict[str, str]] = None
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.ca_bundle = ca_bundle
        self.session = requests.Session()
        
        # Configure SSL/TLS verification (Enterprise Windows CA Store + certifi auto-integration)
        self.ssl_mode = configure_session_ssl(self.session, verify_tls=self.verify_tls, ca_bundle=self.ca_bundle)
        logger.debug(f"BaseClient initialized with SSL Mode: {self.ssl_mode}")

        # Configure corporate proxies if provided
        if proxies:
            self.session.proxies.update(proxies)

        retry_strategy = Retry(
            total=retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=backoff_factor
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def set_headers(self, headers: Dict[str, str]):
        self.session.headers.update(headers)

    def _handle_response(self, response: requests.Response) -> Dict[str, Any]:
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP Error: {response.status_code} for URL: {response.url}")
            if response.status_code == 401:
                logger.error("Authentication failed (401 Unauthorized). Please check API_USERNAME and API_PASSWORD.")
            elif response.status_code == 403:
                logger.error("Access denied (403 Forbidden). User lacks permissions for requested resource/table.")
            elif response.status_code == 404:
                logger.error("Resource not found (404). Check endpoint or table name.")
            elif response.status_code == 429:
                logger.error("Rate limit exceeded (429).")
            elif response.status_code >= 500:
                logger.error(f"Server error ({response.status_code}).")
            
            try:
                error_details = response.json()
                logger.error(f"Error details: {error_details}")
            except ValueError:
                pass
            raise e

        try:
            return response.json()
        except ValueError:
            logger.error("Failed to parse JSON response.")
            return {"text": response.text}

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"GET request to {url}")
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            return self._handle_response(response)
        except requests.exceptions.SSLError as ssl_err:
            diag = diagnose_ssl_error(ssl_err, url)
            logger.error(f"SSL Verification Error when contacting {url}: {diag['category']}")
            for step in diag.get('actionable_steps', []):
                logger.info(f"  Fix: {step}")
            raise ssl_err

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"POST request to {url}")
        try:
            response = self.session.post(url, data=data, json=json, timeout=self.timeout)
            return self._handle_response(response)
        except requests.exceptions.SSLError as ssl_err:
            diag = diagnose_ssl_error(ssl_err, url)
            logger.error(f"SSL Verification Error when contacting {url}: {diag['category']}")
            for step in diag.get('actionable_steps', []):
                logger.info(f"  Fix: {step}")
            raise ssl_err
