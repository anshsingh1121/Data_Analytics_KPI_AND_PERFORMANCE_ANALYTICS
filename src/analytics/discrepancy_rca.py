"""
DISCREPANCY ROOT CAUSE ANALYSIS (RCA) & AUDITED CATEGORY ENGINE
===============================================================
Analyzes ServiceNow Data Certification discrepancies and failure reasons
across all 23 audited configuration attributes and governance categories:
- u_access_reviewer
- incorrect access reviewer
- u_business_delegate
- u_license_financial_owner
- owned_by
- managed_by
- business_criticality
- u_customer_money_mover
- u_change_control
- u_dr_strategy
- u_hosting_strategy
- u_hardware_platform
- support_group
- assignment_group
- install_status
- u_end_of_life_date
- u_version
- application_type
- u_asl_type
- u_user_interface
- u_source_code_location
- manufacturer
- short_description
"""

import re
import logging
from collections import Counter
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# Complete Taxonomy of 23 Audited Discrepancy Categories
DISCREPANCY_CATEGORIES: Dict[str, Dict[str, Any]] = {
    "u_access_reviewer": {
        "id": "u_access_reviewer",
        "name": "u_access_reviewer",
        "label": "Access Reviewer (u_access_reviewer)",
        "field": "u_access_reviewer",
        "domain": "Ownership & Custodianship",
        "risk_level": "High",
        "color": "#4F46E5",
        "keywords": [
            "u_access_reviewer", "access reviewer", "access_reviewer",
            "reviewer missing", "reviewer unassigned", "no reviewer",
            "vacant reviewer", "missing access reviewer", "unassigned reviewer",
            "reviewer not specified", "access certifier"
        ],
        "recommended_action": "Designate and assign an active, certified employee custodian as the primary Access Reviewer."
    },
    "incorrect_access_reviewer": {
        "id": "incorrect access reviewer",
        "name": "incorrect access reviewer",
        "label": "Incorrect Access Reviewer",
        "field": "u_access_reviewer",
        "domain": "Ownership & Custodianship",
        "risk_level": "Critical",
        "color": "#DC2626",
        "keywords": [
            "incorrect access reviewer", "invalid access reviewer", "wrong access reviewer",
            "reviewer left company", "ineligible reviewer", "certifier not access reviewer",
            "unauthorized reviewer", "reviewer inactive", "reviewer resigned",
            "incorrect reviewer", "wrong reviewer assigned", "reviewer obsolete",
            "invalid certifier", "reviewer mismatch"
        ],
        "recommended_action": "Urgent IAM & Custodianship review: reassign access certification authority from departing/ineligible personnel to valid active reviewer."
    },
    "u_business_delegate": {
        "id": "u_business_delegate",
        "name": "u_business_delegate",
        "label": "Business Delegate (u_business_delegate)",
        "field": "u_business_delegate",
        "domain": "Ownership & Custodianship",
        "risk_level": "Medium",
        "color": "#6366F1",
        "keywords": [
            "u_business_delegate", "business delegate", "business_delegate",
            "secondary business owner", "backup delegate", "delegate missing",
            "unassigned delegate", "business backup", "alternate delegate"
        ],
        "recommended_action": "Register a designated secondary business delegate to ensure business continuity during sign-offs."
    },
    "u_license_financial_owner": {
        "id": "u_license_financial_owner",
        "name": "u_license_financial_owner",
        "label": "License Financial Owner (u_license_financial_owner)",
        "field": "u_license_financial_owner",
        "domain": "Ownership & Custodianship",
        "risk_level": "Medium",
        "color": "#0284C7",
        "keywords": [
            "u_license_financial_owner", "license financial owner", "license_financial_owner",
            "financial owner", "license owner", "cost owner", "budget owner",
            "fin owner", "license financial", "software budget owner"
        ],
        "recommended_action": "Reconcile software license allocation and attach cost center financial owner for budget accountability."
    },
    "owned_by": {
        "id": "owned_by",
        "name": "owned_by",
        "label": "Application Owner (owned_by)",
        "field": "owned_by",
        "domain": "Ownership & Custodianship",
        "risk_level": "High",
        "color": "#7C3AED",
        "keywords": [
            "owned_by", "owned by", "system owner", "application owner",
            "primary owner", "asset owner", "vacant owner", "missing owner", "no owner",
            "ci owner", "unassigned owner"
        ],
        "recommended_action": "Confirm executive ownership sponsorship and register active VP/Director custodian in owned_by field."
    },
    "managed_by": {
        "id": "managed_by",
        "name": "managed_by",
        "label": "Managed By / Engineering Manager (managed_by)",
        "field": "managed_by",
        "domain": "Ownership & Custodianship",
        "risk_level": "High",
        "color": "#8B5CF6",
        "keywords": [
            "managed_by", "managed by", "application manager", "delivery manager",
            "technical manager", "operational manager", "engineering lead", "no manager",
            "unassigned manager", "custodian manager"
        ],
        "recommended_action": "Align technical service management hierarchy and assign responsible engineering delivery manager."
    },
    "business_criticality": {
        "id": "business_criticality",
        "name": "business_criticality",
        "label": "Business Criticality (business_criticality)",
        "field": "business_criticality",
        "domain": "Risk, Governance & Compliance",
        "risk_level": "Critical",
        "color": "#E11D48",
        "keywords": [
            "business_criticality", "business criticality", "criticality tier",
            "mission critical", "tier 1", "tier 2", "criticality rating", "wrong criticality",
            "unassigned criticality", "missing criticality", "criticality mismatch", "criticality"
        ],
        "recommended_action": "Conduct formal Business Impact Analysis (BIA) and certify enterprise tiering classification."
    },
    "u_customer_money_mover": {
        "id": "u_customer_money_mover",
        "name": "u_customer_money_mover",
        "label": "Customer Money Mover (u_customer_money_mover)",
        "field": "u_customer_money_mover",
        "domain": "Risk, Governance & Compliance",
        "risk_level": "Critical",
        "color": "#B91C1C",
        "keywords": [
            "u_customer_money_mover", "customer money mover", "money mover",
            "money_mover", "funds transfer", "financial movement", "payment gateway",
            "cash movement", "monetary movement", "sox cash", "money transfer", "money movement"
        ],
        "recommended_action": "Urgent SOX & Risk compliance verification: certify whether application initiates or routes customer monetary transfers."
    },
    "u_change_control": {
        "id": "u_change_control",
        "name": "u_change_control",
        "label": "Change Control (u_change_control)",
        "field": "u_change_control",
        "domain": "Risk, Governance & Compliance",
        "risk_level": "High",
        "color": "#EA580C",
        "keywords": [
            "u_change_control", "change control", "cab required", "rfc required",
            "change advisory", "emergency change flag", "change governance", "unapproved change",
            "change control missing", "no change control"
        ],
        "recommended_action": "Enforce Change Advisory Board (CAB) governance profile and mandate formal change request linkage."
    },
    "u_dr_strategy": {
        "id": "u_dr_strategy",
        "name": "u_dr_strategy",
        "label": "DR Strategy (u_dr_strategy)",
        "field": "u_dr_strategy",
        "domain": "Architecture & Hosting",
        "risk_level": "High",
        "color": "#D97706",
        "keywords": [
            "u_dr_strategy", "dr strategy", "disaster recovery", "dr_strategy",
            "failover", "rpo", "rto", "hot standby", "cold standby", "active-active", "active-passive",
            "dr tier", "dr gap"
        ],
        "recommended_action": "Validate disaster recovery tiering architecture and schedule annual technical failover test drill."
    },
    "u_hosting_strategy": {
        "id": "u_hosting_strategy",
        "name": "u_hosting_strategy",
        "label": "Hosting Strategy (u_hosting_strategy)",
        "field": "u_hosting_strategy",
        "domain": "Architecture & Hosting",
        "risk_level": "Medium",
        "color": "#059669",
        "keywords": [
            "u_hosting_strategy", "hosting strategy", "hosting_strategy",
            "on-prem", "cloud hosting", "aws", "azure", "hybrid hosting", "colocation",
            "data center location", "hosting type"
        ],
        "recommended_action": "Align hosting architecture deployment with enterprise cloud and data center hosting taxonomy."
    },
    "u_hardware_platform": {
        "id": "u_hardware_platform",
        "name": "u_hardware_platform",
        "label": "Hardware Platform (u_hardware_platform)",
        "field": "u_hardware_platform",
        "domain": "Architecture & Hosting",
        "risk_level": "Medium",
        "color": "#10B981",
        "keywords": [
            "u_hardware_platform", "hardware platform", "hardware_platform",
            "server architecture", "x86", "mainframe", "virtual appliance", "esxi", "hypervisor",
            "compute platform"
        ],
        "recommended_action": "Verify compute platform architecture and synchronize server specification attributes."
    },
    "support_group": {
        "id": "support_group",
        "name": "support_group",
        "label": "Support Group (support_group)",
        "field": "support_group",
        "domain": "Support & Operations",
        "risk_level": "Medium",
        "color": "#2563EB",
        "keywords": [
            "support_group", "support group", "l2 support", "l3 support",
            "tier 2 support", "incident support group", "operational support team",
            "support team unassigned", "invalid support group"
        ],
        "recommended_action": "Update ServiceNow support group routing to an active operational ITSM support team."
    },
    "assignment_group": {
        "id": "assignment_group",
        "name": "assignment_group",
        "label": "Assignment Group (assignment_group)",
        "field": "assignment_group",
        "domain": "Support & Operations",
        "risk_level": "Medium",
        "color": "#3B82F6",
        "keywords": [
            "assignment_group", "assignment group", "task assignment",
            "routing group", "resolver group", "tier 1 group", "dispatch group",
            "unassigned assignment group"
        ],
        "recommended_action": "Re-link default task assignment group to active organizational resolver group."
    },
    "install_status": {
        "id": "install_status",
        "name": "install_status",
        "label": "Install Status (install_status)",
        "field": "install_status",
        "domain": "Lifecycle & Release",
        "risk_level": "High",
        "color": "#C026D3",
        "keywords": [
            "install_status", "install status", "operational status",
            "retired status", "decommissioned status", "in maintenance", "installed",
            "pipeline status", "decommission gap", "stale status"
        ],
        "recommended_action": "Synchronize CMDB operational status with verified physical and logical lifecycle state."
    },
    "u_end_of_life_date": {
        "id": "u_end_of_life_date",
        "name": "u_end_of_life_date",
        "label": "End of Life Date (u_end_of_life_date)",
        "field": "u_end_of_life_date",
        "domain": "Lifecycle & Release",
        "risk_level": "High",
        "color": "#9333EA",
        "keywords": [
            "u_end_of_life_date", "end of life", "eol date", "sunset date",
            "retirement date", "decommission date", "end_of_life_date", "eol",
            "expired eol", "missing eol"
        ],
        "recommended_action": "Record verified software/hardware sunset date and initiate scheduled migration roadmap."
    },
    "u_version": {
        "id": "u_version",
        "name": "u_version",
        "label": "Version (u_version)",
        "field": "u_version",
        "domain": "Lifecycle & Release",
        "risk_level": "Medium",
        "color": "#84CC16",
        "keywords": [
            "u_version", "software version", "release version",
            "build number", "patch version", "version mismatch", "outdated version",
            "build tag", "app version"
        ],
        "recommended_action": "Update deployed software release tag from build pipeline or discovery sensor."
    },
    "application_type": {
        "id": "application_type",
        "name": "application_type",
        "label": "Application Type (application_type)",
        "field": "application_type",
        "domain": "Application Baseline",
        "risk_level": "Low",
        "color": "#14B8A6",
        "keywords": [
            "application_type", "application type", "cots", "saas",
            "custom app", "in-house", "commercial package", "app archetype",
            "software type"
        ],
        "recommended_action": "Standardize application classification (COTS, Custom, SaaS, Hybrid) in service catalog."
    },
    "u_asl_type": {
        "id": "u_asl_type",
        "name": "u_asl_type",
        "label": "ASL Type (u_asl_type)",
        "field": "u_asl_type",
        "domain": "Application Baseline",
        "risk_level": "Medium",
        "color": "#06B6D4",
        "keywords": [
            "u_asl_type", "asl type", "asl_type", "application service level",
            "service level tier", "sla tier", "gold tier", "silver tier", "bronze tier", "asl"
        ],
        "recommended_action": "Confirm Application Service Level tiering agreement with Enterprise Architecture."
    },
    "u_user_interface": {
        "id": "u_user_interface",
        "name": "u_user_interface",
        "label": "User Interface (u_user_interface)",
        "field": "u_user_interface",
        "domain": "Application Baseline",
        "risk_level": "Low",
        "color": "#64748B",
        "keywords": [
            "u_user_interface", "user interface", "ui type", "web ui",
            "mobile ui", "api only", "desktop client", "cli", "terminal", "ui architecture"
        ],
        "recommended_action": "Document presentation layer architecture in application metadata catalog."
    },
    "u_source_code_location": {
        "id": "u_source_code_location",
        "name": "u_source_code_location",
        "label": "Source Code Location (u_source_code_location)",
        "field": "u_source_code_location",
        "domain": "Application Baseline",
        "risk_level": "Low",
        "color": "#475569",
        "keywords": [
            "u_source_code_location", "source code location", "repo url",
            "git repo", "github", "gitlab", "bitbucket", "repository link",
            "source_code_location", "source code"
        ],
        "recommended_action": "Link authoritative version control repository URL for audit traceability and security scans."
    },
    "manufacturer": {
        "id": "manufacturer",
        "name": "manufacturer",
        "label": "Manufacturer (manufacturer)",
        "field": "manufacturer",
        "domain": "Application Baseline",
        "risk_level": "Low",
        "color": "#78716C",
        "keywords": [
            "manufacturer", "vendor name", "oem", "software vendor",
            "third party supplier", "product manufacturer", "vendor mismatch", "vendor"
        ],
        "recommended_action": "Reconcile third-party vendor name with approved enterprise vendor master catalog."
    },
    "short_description": {
        "id": "short_description",
        "name": "short_description",
        "label": "Short Description (short_description)",
        "field": "short_description",
        "domain": "Application Baseline",
        "risk_level": "Low",
        "color": "#94A3B8",
        "keywords": [
            "short_description", "short description", "brief description",
            "application summary", "purpose description", "ci title", "missing summary",
            "description missing"
        ],
        "recommended_action": "Provide concise, business-relevant application functional overview and scope."
    }
}

# Backward compatibility alias
SCENARIOS_TAXONOMY = DISCREPANCY_CATEGORIES

DEFAULT_UNCLASSIFIED = {
    "id": "unclassified",
    "name": "Unclassified / Other Discrepancy",
    "label": "Unclassified / Other Discrepancy",
    "field": "general",
    "domain": "General / Uncategorized",
    "risk_level": "Low",
    "color": "#94A3B8",
    "recommended_action": "Review individual discrepancy log notes and register specific attribute in CMDB catalog."
}

STOPWORDS = {
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of',
    'with', 'by', 'from', 'up', 'about', 'into', 'over', 'after', 'is', 'are',
    'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does',
    'did', 'will', 'would', 'should', 'could', 'can', 'this', 'that', 'these',
    'those', 'it', 'its', 'as', 'if', 'not', 'no', 'than', 'so', 'then',
    'task', 'ci', 'cmdb', 'data', 'certification', 'cert', 'record', 'system',
    'please', 'check', 'found', 'user', 'value', 'nan', 'none', 'null'
}


class DiscrepancyRCAEngine:
    """
    Categorizes ServiceNow Data Certification discrepancies into the
    official 23 audited configuration attributes and governance categories.
    """

    def __init__(self, taxonomy: Optional[Dict[str, Dict[str, Any]]] = None):
        self.taxonomy = taxonomy or DISCREPANCY_CATEGORIES
        self._field_lookup = self._build_field_lookup()
        self._compiled_patterns = self._compile_keywords()

    def _build_field_lookup(self) -> Dict[str, str]:
        """Maps exact field names to taxonomy category keys."""
        lookup = {}
        for cat_key, meta in self.taxonomy.items():
            name = meta.get("name", "").lower().strip()
            field = meta.get("field", "").lower().strip()
            if name:
                lookup[name] = cat_key
            if field and field not in lookup:
                lookup[field] = cat_key
        # Explicit priority overrides
        lookup["u_access_reviewer"] = "u_access_reviewer"
        lookup["incorrect access reviewer"] = "incorrect_access_reviewer"
        return lookup

    def _compile_keywords(self) -> Dict[str, List[Tuple[str, re.Pattern]]]:
        """Pre-compiles regex patterns for fast keyword searching."""
        compiled = {}
        for cat_key, data in self.taxonomy.items():
            patterns = []
            for kw in data.get("keywords", []):
                pattern_str = r'(?:\b|_)' + re.escape(kw.lower().strip(': ')) + r'(?:\b|_)'
                patterns.append((kw, re.compile(pattern_str, re.IGNORECASE)))
            compiled[cat_key] = patterns
        return compiled

    def classify_text(self, text: Optional[str], field_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Classifies discrepancy context and/or free-form text into one of the 23 categories.
        Intelligently resolves ambiguous cases (e.g. incorrect access reviewer vs access reviewer).
        """
        cleaned_text = (text or "").strip().lower()
        hint_clean = (field_hint or "").strip().lower().replace(":", "").strip()

        # Specific Priority: Detect "incorrect access reviewer"
        incorrect_reviewer_cues = [
            "incorrect access reviewer", "invalid access reviewer", "wrong access reviewer",
            "reviewer left company", "ineligible reviewer", "unauthorized reviewer",
            "reviewer inactive", "certifier not access reviewer"
        ]
        is_incorrect_reviewer = any(cue in cleaned_text for cue in incorrect_reviewer_cues)
        if is_incorrect_reviewer:
            meta = self.taxonomy["incorrect_access_reviewer"]
            return {
                "category_id": meta["id"],
                "category_name": meta["name"],
                "category_label": meta["label"],
                "scenario_name": meta["name"],
                "domain": meta["domain"],
                "category": meta["domain"],
                "risk_level": meta["risk_level"],
                "color": meta["color"],
                "target_field": meta["field"],
                "matched_keywords": ["incorrect access reviewer"],
                "recommended_action": meta["recommended_action"],
                "confidence": 0.95
            }

        # 1. Direct Field Name matching if field_hint provided
        if hint_clean in self._field_lookup:
            cat_key = self._field_lookup[hint_clean]
            meta = self.taxonomy[cat_key]
            return {
                "category_id": meta["id"],
                "category_name": meta["name"],
                "category_label": meta["label"],
                "scenario_name": meta["name"],
                "domain": meta["domain"],
                "category": meta["domain"],
                "risk_level": meta["risk_level"],
                "color": meta["color"],
                "target_field": meta["field"],
                "matched_keywords": [hint_clean],
                "recommended_action": meta["recommended_action"],
                "confidence": 1.0
            }

        # 2. Text Keyword Matching
        if not cleaned_text:
            return {
                "category_id": DEFAULT_UNCLASSIFIED["id"],
                "category_name": DEFAULT_UNCLASSIFIED["name"],
                "category_label": DEFAULT_UNCLASSIFIED["label"],
                "scenario_name": DEFAULT_UNCLASSIFIED["name"],
                "domain": DEFAULT_UNCLASSIFIED["domain"],
                "category": DEFAULT_UNCLASSIFIED["domain"],
                "risk_level": DEFAULT_UNCLASSIFIED["risk_level"],
                "color": DEFAULT_UNCLASSIFIED["color"],
                "target_field": DEFAULT_UNCLASSIFIED["field"],
                "matched_keywords": [],
                "recommended_action": DEFAULT_UNCLASSIFIED["recommended_action"],
                "confidence": 0.0
            }

        matched_cats: Dict[str, List[str]] = {}
        for cat_key, pattern_list in self._compiled_patterns.items():
            for kw, regex in pattern_list:
                if regex.search(cleaned_text):
                    matched_cats.setdefault(cat_key, []).append(kw)

        if not matched_cats:
            return {
                "category_id": DEFAULT_UNCLASSIFIED["id"],
                "category_name": DEFAULT_UNCLASSIFIED["name"],
                "category_label": DEFAULT_UNCLASSIFIED["label"],
                "scenario_name": DEFAULT_UNCLASSIFIED["name"],
                "domain": DEFAULT_UNCLASSIFIED["domain"],
                "category": DEFAULT_UNCLASSIFIED["domain"],
                "risk_level": DEFAULT_UNCLASSIFIED["risk_level"],
                "color": DEFAULT_UNCLASSIFIED["color"],
                "target_field": DEFAULT_UNCLASSIFIED["field"],
                "matched_keywords": [],
                "recommended_action": DEFAULT_UNCLASSIFIED["recommended_action"],
                "confidence": 0.0
            }

        # Select category with highest keyword matches
        best_cat_key = max(matched_cats.keys(), key=lambda k: len(matched_cats[k]))
        best_keywords = matched_cats[best_cat_key]
        meta = self.taxonomy[best_cat_key]

        confidence = min(1.0, 0.5 + (len(best_keywords) * 0.25))

        return {
            "category_id": meta["id"],
            "category_name": meta["name"],
            "category_label": meta["label"],
            "scenario_name": meta["name"],
            "domain": meta["domain"],
            "category": meta["domain"],
            "risk_level": meta["risk_level"],
            "color": meta["color"],
            "target_field": meta["field"],
            "matched_keywords": best_keywords,
            "recommended_action": meta["recommended_action"],
            "confidence": round(confidence, 2)
        }

    def find_description_column(self, df: pd.DataFrame) -> Optional[str]:
        """Detects column with text descriptions."""
        candidates = [
            'description', 'short_description', 'issue_description',
            'u_issue_description', 'u_resolution_notes', 'close_notes',
            'resolution_notes', 'u_issue_category', 'u_field'
        ]
        for col in candidates:
            if col in df.columns:
                valid_count = df[col].dropna().astype(str).str.strip().str.len()
                if (valid_count > 0).any():
                    return col
        return None

    def categorize_dataframe(
        self,
        disc_df: pd.DataFrame,
        tasks_df: Optional[pd.DataFrame] = None,
        text_col: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Enriches discrepancy dataframe with classification columns based on the 23 categories:
        - `rca_scenario`: Category Name (e.g. u_access_reviewer, business_criticality)
        - `rca_category_display`: Formatted display label
        - `rca_category`: Governance Domain Group
        - `rca_domain`: Governance Domain Group
        - `rca_target_field`: Audited field name
        - `rca_risk_level`: Critical / High / Medium / Low
        - `rca_color`: Modern Hex Color
        - `rca_matched_keywords`: Matched keyword string
        - `rca_recommended_action`: Remediation action
        - `rca_confidence`: 0.0 - 1.0
        - `rca_analyzed_text`: Evaluated text
        """
        if disc_df is None or disc_df.empty:
            return pd.DataFrame()

        df = disc_df.copy()

        # Link task descriptions if available
        if tasks_df is not None and not tasks_df.empty:
            task_text_col = self.find_description_column(tasks_df)
            disc_text_col = self.find_description_column(df)
            if (not disc_text_col or disc_text_col in ['u_field', 'u_issue_category']) and task_text_col:
                link_col = 'u_certification_task' if 'u_certification_task' in df.columns else 'task_id'
                t_id_col = 'sys_id' if 'sys_id' in tasks_df.columns else 'task_id'
                if link_col in df.columns and t_id_col in tasks_df.columns:
                    task_map = tasks_df.set_index(t_id_col)[task_text_col].to_dict()
                    df['task_description'] = df[link_col].map(task_map)

        if not text_col:
            text_col = self.find_description_column(df)

        scenarios = []
        labels = []
        domains = []
        risk_levels = []
        colors = []
        target_fields = []
        matched_kws = []
        actions = []
        confidences = []
        analyzed_texts = []

        for _, row in df.iterrows():
            parts = []
            if text_col and text_col in row and pd.notna(row[text_col]):
                parts.append(str(row[text_col]))
            if 'short_description' in row and pd.notna(row['short_description']) and text_col != 'short_description':
                parts.append(str(row['short_description']))
            if 'u_issue_category' in row and pd.notna(row['u_issue_category']):
                parts.append(f"Category: {row['u_issue_category']}")
            if 'u_resolution_notes' in row and pd.notna(row['u_resolution_notes']):
                parts.append(str(row['u_resolution_notes']))

            field_val = str(row['u_field']).strip() if 'u_field' in row and pd.notna(row['u_field']) else ""
            if field_val:
                parts.append(f"Field: {field_val}")

            combined_text = " | ".join(parts) if parts else ""
            analyzed_texts.append(combined_text)

            res = self.classify_text(combined_text, field_hint=field_val)
            scenarios.append(res["scenario_name"])
            labels.append(res["category_label"])
            domains.append(res["domain"])
            risk_levels.append(res["risk_level"])
            colors.append(res["color"])
            target_fields.append(res["target_field"])
            matched_kws.append(", ".join(res["matched_keywords"]) if res["matched_keywords"] else "None")
            actions.append(res["recommended_action"])
            confidences.append(res["confidence"])

        df['rca_scenario'] = scenarios
        df['rca_category_display'] = labels
        df['rca_category'] = domains
        df['rca_domain'] = domains
        df['rca_target_field'] = target_fields
        df['rca_risk_level'] = risk_levels
        df['rca_color'] = colors
        df['rca_matched_keywords'] = matched_kws
        df['rca_recommended_action'] = actions
        df['rca_confidence'] = confidences
        df['rca_analyzed_text'] = analyzed_texts

        return df

    def extract_top_keywords(
        self,
        df: pd.DataFrame,
        text_col: Optional[str] = None,
        top_n: int = 25
    ) -> pd.DataFrame:
        """Extracts top failure tokens."""
        if df is None or df.empty:
            return pd.DataFrame(columns=["Keyword", "Frequency", "Percentage"])

        col = text_col or 'rca_analyzed_text'
        if col not in df.columns:
            col = self.find_description_column(df)
            if not col:
                return pd.DataFrame(columns=["Keyword", "Frequency", "Percentage"])

        tokens = []
        for text in df[col].dropna():
            words = re.findall(r'[a-zA-Z_]{3,}', str(text).lower())
            tokens.extend([w for w in words if w not in STOPWORDS])

        total_tokens = len(tokens)
        if total_tokens == 0:
            return pd.DataFrame(columns=["Keyword", "Frequency", "Percentage"])

        counts = Counter(tokens).most_common(top_n)
        return pd.DataFrame([
            {
                "Keyword": word,
                "Frequency": count,
                "Percentage": round((count / len(df)) * 100, 1)
            }
            for word, count in counts
        ])

    def get_scenario_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generates summary statistics grouped by audited category."""
        if df is None or df.empty or 'rca_scenario' not in df.columns:
            return pd.DataFrame()

        total = len(df)
        grouped = df.groupby('rca_scenario').agg(
            Count=('rca_scenario', 'count'),
            Category_Display=('rca_category_display', 'first'),
            Domain=('rca_domain', 'first'),
            Category=('rca_category', 'first'),
            Risk_Level=('rca_risk_level', 'first'),
            Target_Field=('rca_target_field', 'first'),
            Action=('rca_recommended_action', 'first')
        ).reset_index()

        grouped['Percentage'] = (grouped['Count'] / total * 100).round(1)
        grouped = grouped.sort_values(by='Count', ascending=False)
        return grouped

    def get_domain_summary(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generates summary statistics grouped by Governance Domain."""
        if df is None or df.empty or 'rca_domain' not in df.columns:
            return pd.DataFrame()

        total = len(df)
        grouped = df.groupby('rca_domain').agg(
            Count=('rca_domain', 'count'),
            Unique_Categories=('rca_scenario', 'nunique'),
            Critical_Risks=('rca_risk_level', lambda s: (s == 'Critical').sum()),
            High_Risks=('rca_risk_level', lambda s: (s == 'High').sum())
        ).reset_index()

        grouped['Share_Pct'] = (grouped['Count'] / total * 100).round(1)
        grouped = grouped.sort_values(by='Count', ascending=False)
        return grouped

    def get_application_scenario_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """Builds cross-tabulation of Application vs Audited Discrepancy Category."""
        if df is None or df.empty or 'rca_scenario' not in df.columns:
            return pd.DataFrame()

        app_col = 'u_application' if 'u_application' in df.columns else (
            'cmdb_ci' if 'cmdb_ci' in df.columns else (
                'u_cmdb_ci' if 'u_cmdb_ci' in df.columns else None
            )
        )
        if not app_col:
            return pd.DataFrame()

        ct = pd.crosstab(df[app_col], df['rca_scenario'], margins=True, margins_name="Total")
        return ct.sort_values(by="Total", ascending=False)

    def compare_campaign_scenarios(
        self,
        df_curr: pd.DataFrame,
        df_prev: pd.DataFrame
    ) -> pd.DataFrame:
        """Compares category volume and percentage share shift between campaigns."""
        curr_summary = self.get_scenario_summary(df_curr)
        prev_summary = self.get_scenario_summary(df_prev)

        if curr_summary.empty and prev_summary.empty:
            return pd.DataFrame()

        c_map = dict(zip(curr_summary['rca_scenario'], curr_summary['Percentage'])) if not curr_summary.empty else {}
        p_map = dict(zip(prev_summary['rca_scenario'], prev_summary['Percentage'])) if not prev_summary.empty else {}
        c_cnt = dict(zip(curr_summary['rca_scenario'], curr_summary['Count'])) if not curr_summary.empty else {}
        p_cnt = dict(zip(prev_summary['rca_scenario'], prev_summary['Count'])) if not prev_summary.empty else {}

        all_scenarios = list(set(list(c_map.keys()) + list(p_map.keys())))
        rows = []
        for scn in all_scenarios:
            c_pct = c_map.get(scn, 0.0)
            p_pct = p_map.get(scn, 0.0)
            diff = round(c_pct - p_pct, 1)
            
            # Lookup domain & risk
            meta = self.taxonomy.get(scn, self.taxonomy.get(scn.replace(" ", "_"), DEFAULT_UNCLASSIFIED))
            rows.append({
                "Audited Category": scn,
                "Governance Domain": meta.get("domain", "General"),
                "Risk Level": meta.get("risk_level", "Medium"),
                "Active Campaign Volume": c_cnt.get(scn, 0),
                "Active Share (%)": f"{c_pct:.1f}%",
                "Prior Campaign Volume": p_cnt.get(scn, 0),
                "Prior Share (%)": f"{p_pct:.1f}%",
                "Share Shift (% Points)": f"{diff:+0.1f}%"
            })

        res_df = pd.DataFrame(rows)
        if not res_df.empty:
            res_df = res_df.sort_values(by="Active Campaign Volume", ascending=False)
        return res_df
