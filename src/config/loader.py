import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

class ConfigError(Exception):
    pass

class ConfigLoader:
    def __init__(self):
        self._load_env()
        self.settings = self._load_yaml("settings.yaml")
        self.field_mappings = self._load_yaml("field_mapping.yaml")
        self.kpi_definitions = self._load_yaml("kpi_definitions.yaml")
        self.certification_cycles = self._load_yaml("certification_cycles.yaml")
        
    def _load_env(self):
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
            
    def _load_yaml(self, filename: str) -> dict:
        file_path = CONFIG_DIR / filename
        if not file_path.exists():
            raise ConfigError(f"Configuration file not found: {file_path}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                raise ConfigError(f"Error parsing {filename}: {e}")
                
    def get_app_mode(self) -> str:
        demo_enabled = self.settings.get("demo_mode", {}).get("enabled", False)
        return os.getenv("APP_MODE", "demo" if demo_enabled else "live")
        
    def get_api_config(self) -> dict:
        api_config = self.settings.get("api", {})
        provider = self.settings.get("provider", {})
        
        return {
            "base_url": os.getenv("API_BASE_URL", ""),
            "provider": os.getenv("API_PROVIDER", provider.get("name", "servicenow")),
            "auth_method": os.getenv("API_AUTH_METHOD", "basic"),
            "username": os.getenv("API_USERNAME", ""),
            "password": os.getenv("API_PASSWORD", ""),
            "client_id": os.getenv("API_CLIENT_ID", ""),
            "client_secret": os.getenv("API_CLIENT_SECRET", ""),
            "token_url": os.getenv("API_TOKEN_URL", ""),
            "access_token": os.getenv("API_ACCESS_TOKEN", ""),
            "timeout_seconds": int(os.getenv("API_TIMEOUT_SECONDS", api_config.get("timeout_seconds", 30))),
            "page_size": int(os.getenv("API_PAGE_SIZE", api_config.get("pagination_size", 500))),
            "max_retries": int(os.getenv("API_MAX_RETRIES", api_config.get("max_retries", 3))),
            "verify_tls": str(os.getenv("API_VERIFY_TLS", "true")).lower() == "true",
        }
        
    def get_field_mapping(self) -> dict:
        return self.field_mappings
        
    def get_kpi_config(self) -> dict:
        return self.kpi_definitions
        
    def get_cycle_config(self) -> dict:
        return self.certification_cycles

    def get_setting(self, key: str, default=None):
        return self.settings.get(key, default)
