from datetime import datetime
from typing import Dict, List, Tuple
from .loader import ConfigLoader

class ConfigValidator:
    def __init__(self, loader: ConfigLoader):
        self.loader = loader
        
    def validate_all(self) -> Dict[str, List[str]]:
        results = {
            "errors": [],
            "warnings": []
        }
        
        api_res = self.validate_api_config()
        results["errors"].extend(api_res["errors"])
        results["warnings"].extend(api_res["warnings"])
        
        field_res = self.validate_field_mapping()
        results["errors"].extend(field_res["errors"])
        results["warnings"].extend(field_res["warnings"])
        
        kpi_res = self.validate_kpi_config()
        results["errors"].extend(kpi_res["errors"])
        results["warnings"].extend(kpi_res["warnings"])
        
        cycle_res = self.validate_cycle_config()
        results["errors"].extend(cycle_res["errors"])
        results["warnings"].extend(cycle_res["warnings"])
        
        return results
        
    def validate_api_config(self) -> Dict[str, List[str]]:
        errors = []
        warnings = []
        
        if self.loader.get_app_mode() != "demo":
            api_config = self.loader.get_api_config()
            if not api_config.get("base_url"):
                errors.append("API_BASE_URL is required in live mode.")
            
            auth_method = api_config.get("auth_method")
            if auth_method == "basic":
                if not api_config.get("username") or not api_config.get("password"):
                    errors.append("API_USERNAME and API_PASSWORD are required for basic auth.")
            elif auth_method == "oauth":
                if not api_config.get("client_id") or not api_config.get("client_secret") or not api_config.get("token_url"):
                    errors.append("OAuth credentials are required for oauth auth_method.")
            else:
                warnings.append(f"Unknown auth method: {auth_method}")
                
        return {"errors": errors, "warnings": warnings}
        
    def validate_field_mapping(self) -> Dict[str, List[str]]:
        errors = []
        warnings = []
        
        mappings = self.loader.get_field_mapping()
        if "tables" not in mappings:
            errors.append("Missing 'tables' key in field_mapping.yaml")
            return {"errors": errors, "warnings": warnings}
            
        tables = mappings.get("tables", {})
        if "cert_task" not in tables:
            errors.append("Missing 'cert_task' mapping.")
        if "u_failed_data_certifications" not in tables:
            warnings.append("Missing 'u_failed_data_certifications' mapping.")
            
        return {"errors": errors, "warnings": warnings}
        
    def validate_kpi_config(self) -> Dict[str, List[str]]:
        errors = []
        warnings = []
        
        kpis = self.loader.get_kpi_config().get("kpis", {})
        for kpi_id, kpi_data in kpis.items():
            thresholds = kpi_data.get("thresholds", {})
            if not thresholds:
                errors.append(f"KPI {kpi_id} missing thresholds.")
                continue
                
            target = thresholds.get("target")
            warning = thresholds.get("warning")
            critical = thresholds.get("critical")
            
            if None in (target, warning, critical):
                errors.append(f"KPI {kpi_id} missing one or more threshold values.")
            
            trend = kpi_data.get("desired_trend", "up")
            if trend == "up":
                if target is not None and warning is not None and target < warning:
                    warnings.append(f"KPI {kpi_id} has upward trend but target < warning.")
            elif trend == "down":
                if target is not None and warning is not None and target > warning:
                    warnings.append(f"KPI {kpi_id} has downward trend but target > warning.")
                    
        return {"errors": errors, "warnings": warnings}
        
    def validate_cycle_config(self) -> Dict[str, List[str]]:
        errors = []
        warnings = []
        
        cycles = self.loader.get_cycle_config()
        
        def parse_date(date_str):
            try:
                return datetime.strptime(str(date_str), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return None
        
        current_cycle = cycles.get("current_cycle", {})
        prev_cycle = cycles.get("previous_cycle", {})
        
        for cycle_name, cycle_data in [("current_cycle", current_cycle), ("previous_cycle", prev_cycle)]:
            if not cycle_data:
                errors.append(f"Missing {cycle_name} configuration.")
                continue
                
            start = parse_date(cycle_data.get("start_date"))
            end = parse_date(cycle_data.get("end_date"))
            final = parse_date(cycle_data.get("final_deadline"))
            
            if not all([start, end, final]):
                errors.append(f"Invalid or missing dates in {cycle_name}.")
            elif start and end and start > end:
                errors.append(f"Start date > end date in {cycle_name}.")
            elif end and final and end > final:
                warnings.append(f"End date > final deadline in {cycle_name}.")
                
        c_start = parse_date(current_cycle.get("start_date"))
        p_end = parse_date(prev_cycle.get("end_date"))
        
        if c_start and p_end and c_start <= p_end:
            warnings.append("Current cycle start date overlaps with or is before previous cycle end date.")
            
        return {"errors": errors, "warnings": warnings}
