"""
DISCREPANCY ROOT CAUSE ANALYSIS (RCA) & SCENARIO CATEGORIZATION ENGINE
=====================================================================
Analyzes free-form and semi-structured text in ServiceNow Data Certification
task and discrepancy description fields using keyword matching, pattern
clustering, and NLP tokenization to identify systematic failure reasons.
"""

import re
import logging
from collections import Counter
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# Standard Taxonomy of ServiceNow Data Certification Failure Scenarios
SCENARIOS_TAXONOMY: Dict[str, Dict[str, Any]] = {
    "SCN_MISSING_DATA": {
        "name": "Missing / Unassigned Mandatory Data",
        "category": "Data Completeness",
        "risk_level": "High",
        "color": "#DC2626",  # Red
        "keywords": [
            "missing", "empty", "blank", "null", "unassigned", "not populated",
            "not specified", "no owner", "no manager", "no cost center",
            "no department", "unallocated", "missing value", "absent",
            "undefined", "not provided", "no support group", "vacant owner",
            "mandatory field", "required field missing"
        ],
        "recommended_action": "Enforce mandatory field validation rules at CI creation and trigger automated custodian re-assignment."
    },
    "SCN_STALE_RECORD": {
        "name": "Stale / Obsolete / Decommissioning Gaps",
        "category": "Lifecycle & Hygiene",
        "risk_level": "High",
        "color": "#EA580C",  # Orange-Red
        "keywords": [
            "stale", "retired", "decommission", "decommissioned", "inactive",
            "obsolete", "dormant", "legacy", "sunset", "expired", "terminated",
            "no longer in use", "not in service", "shut down", "disposed",
            "turned off", "archived", "no discovery update", "ghost asset",
            "old record", "last discovered >90 days"
        ],
        "recommended_action": "Initiate automated decommissioning verification workflow and update CI operational status to Retired."
    },
    "SCN_VALUE_MISMATCH": {
        "name": "Attribute Value Mismatch & Inaccuracy",
        "category": "Accuracy & Synchronization",
        "risk_level": "Medium",
        "color": "#D97706",  # Amber
        "keywords": [
            "mismatch", "incorrect", "wrong", "inconsistent", "differs",
            "does not match", "discrepancy", "out of sync", "deviates",
            "conflicting", "inaccurate", "discrepant", "divergent", "wrong tier",
            "incorrect environment", "wrong classification", "mismatched",
            "differs from source", "audit discrepancy", "does not agree"
        ],
        "recommended_action": "Reconcile against authoritative system of record (e.g. HR, SAP, Discovery) and update CMDB attribute."
    },
    "SCN_FORMAT_SYNTAX": {
        "name": "Naming & Format Standard Violations",
        "category": "Data Standards",
        "risk_level": "Low",
        "color": "#2563EB",  # Blue
        "keywords": [
            "format", "syntax", "naming", "convention", "pattern",
            "invalid characters", "invalid ip", "hostname syntax", "casing",
            "malformed", "standard violation", "non-standard", "invalid format",
            "bad syntax", "regex failed", "special characters", "ip format"
        ],
        "recommended_action": "Apply automated regex input masks and normalize naming conventions via Data Quality policies."
    },
    "SCN_ORPHAN_RELATION": {
        "name": "Orphaned Records & Broken Relationships",
        "category": "Integrations & Relationships",
        "risk_level": "High",
        "color": "#7C3AED",  # Purple
        "keywords": [
            "orphan", "unlinked", "no parent", "no relation", "missing dependency",
            "isolated", "broken link", "no upstream", "no downstream",
            "unattached", "missing relationship", "dangling reference",
            "unmapped service", "disconnected ci"
        ],
        "recommended_action": "Map CI into application service modeling hierarchy and establish upstream business service dependency."
    },
    "SCN_UNAUTHORIZED_CHANGE": {
        "name": "Unauthorized Changes & Configuration Drift",
        "category": "Governance & Compliance",
        "risk_level": "Critical",
        "color": "#991B1B",  # Dark Red
        "keywords": [
            "unauthorized", "out of band", "unapproved", "no change ticket",
            "unauthorized change", "drift", "untracked modification",
            "unexpected change", "unapproved software", "security violation",
            "no rfc", "unauthorized modification"
        ],
        "recommended_action": "Raise urgent Incident / Security Audit ticket to investigate unauthorized drift and enforce Change Control."
    },
    "SCN_DUPLICATE_ENTRY": {
        "name": "Duplicate / Redundant Configuration Items",
        "category": "Accuracy & Synchronization",
        "risk_level": "Medium",
        "color": "#0D9488",  # Teal
        "keywords": [
            "duplicate", "repeated", "redundant", "collision", "already exists",
            "twin", "cloned", "multiple entries", "duplicate serial",
            "duplicate name", "duplicate asset"
        ],
        "recommended_action": "Execute CMDB de-duplication wizard to merge child references and archive redundant record."
    },
    "SCN_ACCESS_ROLE": {
        "name": "Access, Role & Custodian Governance",
        "category": "Governance & Compliance",
        "risk_level": "Medium",
        "color": "#4F46E5",  # Indigo
        "keywords": [
            "access", "permission", "unauthorized user", "role vacant",
            "certifier unable", "privilege", "left company", "inactive certifier",
            "no access", "resigned", "reassigned certifier", "permission denied",
            "custodian unavailable", "certifier missing"
        ],
        "recommended_action": "Update Active Directory / IAM certifier hierarchy and reassign certification task to active custodian."
    }
}

DEFAULT_UNCLASSIFIED = {
    "name": "Unclassified / Custom Discrepancy",
    "category": "Other / Uncategorized",
    "risk_level": "Low",
    "color": "#6B7280",  # Gray
    "recommended_action": "Review individual task notes and add emerging keywords to the taxonomy."
}

# Stopwords to filter out during dynamic keyword discovery
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
    Categorizes ServiceNow Data Certification discrepancies by analyzing
    free-form text from task/discrepancy description fields.
    """

    def __init__(self, taxonomy: Optional[Dict[str, Dict[str, Any]]] = None):
        self.taxonomy = taxonomy or SCENARIOS_TAXONOMY
        self._compiled_patterns = self._compile_keywords()

    def _compile_keywords(self) -> Dict[str, List[Tuple[str, re.Pattern]]]:
        """Pre-compiles regex patterns for fast keyword searching."""
        compiled = {}
        for scn_id, data in self.taxonomy.items():
            patterns = []
            for kw in data.get("keywords", []):
                # Word-boundary matching with whitespace tolerance
                pattern_str = r'\b' + re.escape(kw.lower()) + r'\b'
                patterns.append((kw, re.compile(pattern_str, re.IGNORECASE)))
            compiled[scn_id] = patterns
        return compiled

    def classify_text(self, text: Optional[str]) -> Dict[str, Any]:
        """
        Classifies a single description string into a root-cause scenario.
        Returns scenario details and matched keywords.
        """
        if not text or not isinstance(text, str) or not text.strip():
            return {
                "scenario_id": "SCN_UNCLASSIFIED",
                "scenario_name": DEFAULT_UNCLASSIFIED["name"],
                "category": DEFAULT_UNCLASSIFIED["category"],
                "risk_level": DEFAULT_UNCLASSIFIED["risk_level"],
                "color": DEFAULT_UNCLASSIFIED["color"],
                "matched_keywords": [],
                "recommended_action": DEFAULT_UNCLASSIFIED["recommended_action"],
                "confidence": 0.0
            }

        cleaned_text = text.strip()
        matched_scenarios: Dict[str, List[str]] = {}

        for scn_id, pattern_list in self._compiled_patterns.items():
            for kw, regex in pattern_list:
                if regex.search(cleaned_text):
                    matched_scenarios.setdefault(scn_id, []).append(kw)

        if not matched_scenarios:
            return {
                "scenario_id": "SCN_UNCLASSIFIED",
                "scenario_name": DEFAULT_UNCLASSIFIED["name"],
                "category": DEFAULT_UNCLASSIFIED["category"],
                "risk_level": DEFAULT_UNCLASSIFIED["risk_level"],
                "color": DEFAULT_UNCLASSIFIED["color"],
                "matched_keywords": [],
                "recommended_action": DEFAULT_UNCLASSIFIED["recommended_action"],
                "confidence": 0.0
            }

        # Select scenario with the highest number of matched keywords (or earliest defined)
        best_scn_id = max(matched_scenarios.keys(), key=lambda k: len(matched_scenarios[k]))
        best_keywords = matched_scenarios[best_scn_id]
        meta = self.taxonomy[best_scn_id]

        confidence = min(1.0, 0.5 + (len(best_keywords) * 0.25))

        return {
            "scenario_id": best_scn_id,
            "scenario_name": meta["name"],
            "category": meta["category"],
            "risk_level": meta["risk_level"],
            "color": meta["color"],
            "matched_keywords": best_keywords,
            "recommended_action": meta["recommended_action"],
            "confidence": round(confidence, 2)
        }

    def find_description_column(self, df: pd.DataFrame) -> Optional[str]:
        """Intelligently detects which column holds failure descriptions or reasons."""
        candidates = [
            'description', 'short_description', 'issue_description',
            'u_issue_description', 'u_resolution_notes', 'close_notes',
            'resolution_notes', 'u_issue_category', 'u_field'
        ]
        for col in candidates:
            if col in df.columns:
                # Check that it actually has non-empty text
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
        Enriches the discrepancy dataframe with RCA categorization columns:
        - `rca_scenario`: Clean Scenario Name
        - `rca_category`: High-level group
        - `rca_risk_level`: Critical / High / Medium / Low
        - `rca_color`: Hex color
        - `rca_matched_keywords`: Comma-separated list of keywords matched
        - `rca_recommended_action`: Actionable next step
        - `rca_confidence`: Score 0.0 - 1.0
        - `rca_analyzed_text`: Exact text string evaluated
        """
        if disc_df is None or disc_df.empty:
            return pd.DataFrame()

        df = disc_df.copy()

        # If task description is available and discrepancies don't have descriptions, merge task description
        if tasks_df is not None and not tasks_df.empty:
            task_text_col = self.find_description_column(tasks_df)
            disc_text_col = self.find_description_column(df)
            
            # If discrepancy doesn't have an informative description but tasks do:
            if (not disc_text_col or disc_text_col in ['u_field', 'u_issue_category']) and task_text_col:
                link_col = 'u_certification_task' if 'u_certification_task' in df.columns else 'task_id'
                t_id_col = 'sys_id' if 'sys_id' in tasks_df.columns else 'task_id'
                if link_col in df.columns and t_id_col in tasks_df.columns:
                    task_map = tasks_df.set_index(t_id_col)[task_text_col].to_dict()
                    df['task_description'] = df[link_col].map(task_map)

        # Resolve primary text column
        if not text_col:
            text_col = self.find_description_column(df)

        scenarios = []
        categories = []
        risk_levels = []
        colors = []
        matched_kws = []
        actions = []
        confidences = []
        analyzed_texts = []

        for _, row in df.iterrows():
            # Build combined text context if multiple columns exist
            parts = []
            if text_col and text_col in row and pd.notna(row[text_col]):
                parts.append(str(row[text_col]))
            
            # Contextual fallback: include u_field and u_issue_category if available
            if 'u_field' in row and pd.notna(row['u_field']):
                parts.append(f"Field: {row['u_field']}")
            if 'u_issue_category' in row and pd.notna(row['u_issue_category']):
                parts.append(f"Category: {row['u_issue_category']}")
            if 'u_resolution_notes' in row and pd.notna(row['u_resolution_notes']) and text_col != 'u_resolution_notes':
                parts.append(str(row['u_resolution_notes']))

            combined_text = " | ".join(parts) if parts else ""
            analyzed_texts.append(combined_text)

            res = self.classify_text(combined_text)
            scenarios.append(res["scenario_name"])
            categories.append(res["category"])
            risk_levels.append(res["risk_level"])
            colors.append(res["color"])
            matched_kws.append(", ".join(res["matched_keywords"]) if res["matched_keywords"] else "None")
            actions.append(res["recommended_action"])
            confidences.append(res["confidence"])

        df['rca_scenario'] = scenarios
        df['rca_category'] = categories
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
        """
        Extracts the most frequent informative words/tokens appearing in the failure text.
        Useful for uncovering emerging failure patterns that may not yet be in the taxonomy.
        """
        if df is None or df.empty:
            return pd.DataFrame(columns=["Keyword", "Frequency", "Percentage"])

        col = text_col or 'rca_analyzed_text'
        if col not in df.columns:
            col = self.find_description_column(df)
            if not col:
                return pd.DataFrame(columns=["Keyword", "Frequency", "Percentage"])

        tokens = []
        for text in df[col].dropna():
            # Clean words: letters and hyphens only, min length 3
            words = re.findall(r'[a-zA-Z]{3,}', str(text).lower())
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
        """Generates summary statistics grouped by failure scenario."""
        if df is None or df.empty or 'rca_scenario' not in df.columns:
            return pd.DataFrame()

        total = len(df)
        grouped = df.groupby('rca_scenario').agg(
            Count=('rca_scenario', 'count'),
            Category=('rca_category', 'first'),
            Risk_Level=('rca_risk_level', 'first'),
            Action=('rca_recommended_action', 'first')
        ).reset_index()

        grouped['Percentage'] = (grouped['Count'] / total * 100).round(1)
        grouped = grouped.sort_values(by='Count', ascending=False)
        return grouped

    def get_application_scenario_matrix(self, df: pd.DataFrame) -> pd.DataFrame:
        """Builds a cross-tabulation of Application / CI vs Failure Scenario."""
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
        """Compares scenario volume and percentage share between two campaigns."""
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
            rows.append({
                "Failure Scenario": scn,
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
