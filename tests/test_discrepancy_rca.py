"""
UNIT TESTS — DISCREPANCY ROOT CAUSE ANALYSIS & SCENARIO ENGINE
=============================================================
Verifies keyword-based text classification, multi-column description extraction,
dynamic keyword discovery, and scenario aggregation.
"""

import pytest
import pandas as pd
from src.analytics.discrepancy_rca import DiscrepancyRCAEngine, SCENARIOS_TAXONOMY

@pytest.fixture
def rca_engine():
    return DiscrepancyRCAEngine()

def test_scenario_classification_keywords(rca_engine):
    # Test Missing Data
    res = rca_engine.classify_text("Primary Application Owner is empty and unassigned in CMDB record.")
    assert res["scenario_id"] == "SCN_MISSING_DATA"
    assert "empty" in res["matched_keywords"] or "unassigned" in res["matched_keywords"]
    assert res["risk_level"] == "High"

    # Test Stale / Decommissioned
    res = rca_engine.classify_text("Server was decommissioned 6 months ago but still marked operational.")
    assert res["scenario_id"] == "SCN_STALE_RECORD"
    assert "decommissioned" in res["matched_keywords"]

    # Test Value Mismatch
    res = rca_engine.classify_text("Cost center value mismatch: CMDB shows 4001, SAP shows 5002.")
    assert res["scenario_id"] == "SCN_VALUE_MISMATCH"
    assert "mismatch" in res["matched_keywords"]

    # Test Format / Syntax
    res = rca_engine.classify_text("Hostname syntax error: does not follow enterprise naming convention.")
    assert res["scenario_id"] == "SCN_FORMAT_SYNTAX"
    assert "syntax" in res["matched_keywords"] or "naming" in res["matched_keywords"]

    # Test Orphan Record
    res = rca_engine.classify_text("Orphan CI: No parent business service or upstream relationship mapped.")
    assert res["scenario_id"] == "SCN_ORPHAN_RELATION"
    assert "orphan" in res["matched_keywords"]

    # Test Unauthorized Change
    res = rca_engine.classify_text("Unauthorized change detected without approved Change Request RFC ticket.")
    assert res["scenario_id"] == "SCN_UNAUTHORIZED_CHANGE"
    assert "unauthorized change" in res["matched_keywords"] or "unauthorized" in res["matched_keywords"]

    # Test Duplicate Entry
    res = rca_engine.classify_text("Duplicate CI detected: duplicate serial number already exists.")
    assert res["scenario_id"] == "SCN_DUPLICATE_ENTRY"
    assert "duplicate" in res["matched_keywords"] or "already exists" in res["matched_keywords"]

    # Test Access / Role
    res = rca_engine.classify_text("Certifier unable to verify: role vacant and permission revoked.")
    assert res["scenario_id"] == "SCN_ACCESS_ROLE"
    assert "certifier unable" in res["matched_keywords"] or "role vacant" in res["matched_keywords"]

    # Test Unclassified Fallback
    res = rca_engine.classify_text("Random non-matching text 12345.")
    assert res["scenario_id"] == "SCN_UNCLASSIFIED"
    assert len(res["matched_keywords"]) == 0

def test_empty_and_none_text_handling(rca_engine):
    res_none = rca_engine.classify_text(None)
    assert res_none["scenario_id"] == "SCN_UNCLASSIFIED"

    res_empty = rca_engine.classify_text("   ")
    assert res_empty["scenario_id"] == "SCN_UNCLASSIFIED"

def test_categorize_dataframe(rca_engine):
    df = pd.DataFrame([
        {"sys_id": "D1", "number": "DISC01", "u_application": "App-Finance", "description": "Required field owner is missing in CMDB."},
        {"sys_id": "D2", "number": "DISC02", "u_application": "App-HR", "description": "Host was retired last year."},
        {"sys_id": "D3", "number": "DISC03", "u_application": "App-CRM", "description": "Something strange happened."}
    ])

    enriched = rca_engine.categorize_dataframe(df)
    assert len(enriched) == 3
    assert "rca_scenario" in enriched.columns
    assert "rca_category" in enriched.columns
    assert "rca_risk_level" in enriched.columns
    assert "rca_matched_keywords" in enriched.columns
    assert "rca_recommended_action" in enriched.columns

    assert enriched.loc[0, "rca_scenario"] == "Missing / Unassigned Mandatory Data"
    assert enriched.loc[1, "rca_scenario"] == "Stale / Obsolete / Decommissioning Gaps"
    assert enriched.loc[2, "rca_scenario"] == "Unclassified / Custom Discrepancy"

def test_top_keyword_extraction(rca_engine):
    df = pd.DataFrame([
        {"description": "Missing owner and missing cost center"},
        {"description": "Missing manager and retired server"},
        {"description": "Server was retired and decommissioned"}
    ])
    kw_df = rca_engine.extract_top_keywords(df, text_col="description", top_n=5)
    assert not kw_df.empty
    keywords = kw_df["Keyword"].tolist()
    assert "missing" in keywords
    assert "retired" in keywords
    # Stopwords like 'and', 'was' should not be in the top keywords
    assert "and" not in keywords
    assert "was" not in keywords

def test_scenario_summary_and_application_matrix(rca_engine):
    df = pd.DataFrame([
        {"sys_id": "D1", "u_application": "App-Finance", "description": "Required owner is missing"},
        {"sys_id": "D2", "u_application": "App-Finance", "description": "Blank cost center value"},
        {"sys_id": "D3", "u_application": "App-HR", "description": "Decommissioned asset still operational"}
    ])
    enriched = rca_engine.categorize_dataframe(df)
    summary = rca_engine.get_scenario_summary(enriched)
    assert len(summary) >= 2
    assert "Missing / Unassigned Mandatory Data" in summary["rca_scenario"].values

    matrix = rca_engine.get_application_scenario_matrix(enriched)
    assert not matrix.empty
    assert "App-Finance" in matrix.index

def test_compare_campaign_scenarios(rca_engine):
    df_curr = pd.DataFrame([
        {"description": "Missing owner"},
        {"description": "Missing manager"}
    ])
    df_prev = pd.DataFrame([
        {"description": "Retired server"},
        {"description": "Missing owner"}
    ])
    curr_enc = rca_engine.categorize_dataframe(df_curr)
    prev_enc = rca_engine.categorize_dataframe(df_prev)

    comp = rca_engine.compare_campaign_scenarios(curr_enc, prev_enc)
    assert not comp.empty
    assert "Failure Scenario" in comp.columns
    assert "Share Shift (% Points)" in comp.columns
