"""
UNIT TESTS — DISCREPANCY AUDITED CATEGORIES & RCA ENGINE
========================================================
Verifies classification across all 23 ServiceNow certified CMDB attributes
and governance categories, including:
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

import pytest
import pandas as pd
from src.analytics.discrepancy_rca import DiscrepancyRCAEngine, DISCREPANCY_CATEGORIES

@pytest.fixture
def rca_engine():
    return DiscrepancyRCAEngine()

def test_scenario_classification_keywords(rca_engine):
    # Test u_access_reviewer
    res = rca_engine.classify_text("Required field 'u_access_reviewer' is blank or unassigned in CMDB record.", field_hint="u_access_reviewer")
    assert res["scenario_name"] == "u_access_reviewer"
    assert res["risk_level"] == "High"
    assert res["domain"] == "Ownership & Custodianship"

    # Test incorrect access reviewer
    res = rca_engine.classify_text("Discrepancy: incorrect access reviewer assigned for App-HR; certifier is not authorized access reviewer.", field_hint="u_access_reviewer")
    assert res["scenario_name"] == "incorrect access reviewer"
    assert res["risk_level"] == "Critical"

    # Test business_criticality
    res = rca_engine.classify_text("Criticality mismatch: business_criticality in CMDB differs from Business Impact Analysis (BIA) tier.", field_hint="business_criticality")
    assert res["scenario_name"] == "business_criticality"
    assert res["risk_level"] == "Critical"
    assert res["domain"] == "Risk, Governance & Compliance"

    # Test u_customer_money_mover
    res = rca_engine.classify_text("Urgent SOX compliance gap: u_customer_money_mover flag uncertified or inconsistent with payment gateway audit.", field_hint="u_customer_money_mover")
    assert res["scenario_name"] == "u_customer_money_mover"
    assert res["risk_level"] == "Critical"

    # Test u_dr_strategy
    res = rca_engine.classify_text("DR strategy discrepancy: u_dr_strategy specifies active-active but secondary site is decommissioned.", field_hint="u_dr_strategy")
    assert res["scenario_name"] == "u_dr_strategy"
    assert res["domain"] == "Architecture & Hosting"

    # Test owned_by
    res = rca_engine.classify_text("Application owner gap: owned_by attribute is blank or assigned to inactive personnel.", field_hint="owned_by")
    assert res["scenario_name"] == "owned_by"

    # Test u_hosting_strategy
    res = rca_engine.classify_text("Hosting strategy mismatch: u_hosting_strategy indicates on-prem but workloads migrated to AWS.", field_hint="u_hosting_strategy")
    assert res["scenario_name"] == "u_hosting_strategy"

    # Test install_status
    res = rca_engine.classify_text("Install status gap: install_status marked operational but CI has been sunset / decommissioned.", field_hint="install_status")
    assert res["scenario_name"] == "install_status"

    # Test u_end_of_life_date
    res = rca_engine.classify_text("End of life date discrepancy: u_end_of_life_date is past due but no retirement roadmap recorded.", field_hint="u_end_of_life_date")
    assert res["scenario_name"] == "u_end_of_life_date"

    # Test u_version
    res = rca_engine.classify_text("Software version mismatch: u_version in CMDB differs from discovery build tag.", field_hint="u_version")
    assert res["scenario_name"] == "u_version"

    # Test application_type
    res = rca_engine.classify_text("Application type classification error: application_type marked COTS instead of in-house custom app.", field_hint="application_type")
    assert res["scenario_name"] == "application_type"

    # Test support_group
    res = rca_engine.classify_text("Support routing discrepancy: support_group points to disbanded L2 operations queue.", field_hint="support_group")
    assert res["scenario_name"] == "support_group"

    # Test assignment_group
    res = rca_engine.classify_text("Assignment group error: assignment_group not configured for primary incident routing.", field_hint="assignment_group")
    assert res["scenario_name"] == "assignment_group"

    # Test u_business_delegate
    res = rca_engine.classify_text("Business delegate missing: u_business_delegate is empty; alternate sign-off contact required.", field_hint="u_business_delegate")
    assert res["scenario_name"] == "u_business_delegate"

    # Test u_license_financial_owner
    res = rca_engine.classify_text("License financial owner gap: u_license_financial_owner cost center budget owner not identified.", field_hint="u_license_financial_owner")
    assert res["scenario_name"] == "u_license_financial_owner"

    # Test managed_by
    res = rca_engine.classify_text("Technical manager discrepancy: managed_by engineering delivery lead not populated.", field_hint="managed_by")
    assert res["scenario_name"] == "managed_by"

    # Test u_change_control
    res = rca_engine.classify_text("Change control governance discrepancy: u_change_control is unassigned; CAB review required.", field_hint="u_change_control")
    assert res["scenario_name"] == "u_change_control"

    # Test u_hardware_platform
    res = rca_engine.classify_text("Hardware platform discrepancy: u_hardware_platform specifies legacy x86 architecture.", field_hint="u_hardware_platform")
    assert res["scenario_name"] == "u_hardware_platform"

    # Test u_asl_type
    res = rca_engine.classify_text("ASL tier discrepancy: u_asl_type service level agreement not aligned with EA tiering.", field_hint="u_asl_type")
    assert res["scenario_name"] == "u_asl_type"

    # Test u_user_interface
    res = rca_engine.classify_text("User interface architecture gap: u_user_interface metadata missing from application catalog.", field_hint="u_user_interface")
    assert res["scenario_name"] == "u_user_interface"

    # Test u_source_code_location
    res = rca_engine.classify_text("Source code location gap: u_source_code_location Git repository link is invalid or empty.", field_hint="u_source_code_location")
    assert res["scenario_name"] == "u_source_code_location"

    # Test manufacturer
    res = rca_engine.classify_text("Vendor reconciliation gap: manufacturer does not match approved enterprise vendor master.", field_hint="manufacturer")
    assert res["scenario_name"] == "manufacturer"

    # Test short_description
    res = rca_engine.classify_text("Missing summary description: short_description is blank or non-compliant with CMDB standards.", field_hint="short_description")
    assert res["scenario_name"] == "short_description"

    # Test Unclassified Fallback
    res = rca_engine.classify_text("Random non-matching text 12345.")
    assert res["scenario_name"] == "Unclassified / Other Discrepancy"

def test_empty_and_none_text_handling(rca_engine):
    res_none = rca_engine.classify_text(None)
    assert res_none["scenario_name"] == "Unclassified / Other Discrepancy"

    res_empty = rca_engine.classify_text("   ")
    assert res_empty["scenario_name"] == "Unclassified / Other Discrepancy"

def test_categorize_dataframe(rca_engine):
    df = pd.DataFrame([
        {"sys_id": "D1", "number": "DISC01", "u_application": "App-Finance", "u_field": "u_access_reviewer", "description": "Required field 'u_access_reviewer' is blank."},
        {"sys_id": "D2", "number": "DISC02", "u_application": "App-HR", "u_field": "u_access_reviewer", "description": "Incorrect access reviewer: reviewer left company."},
        {"sys_id": "D3", "number": "DISC03", "u_application": "App-CRM", "u_field": "business_criticality", "description": "Criticality mismatch on business_criticality."},
        {"sys_id": "D4", "number": "DISC04", "u_application": "App-ERP", "u_field": "u_customer_money_mover", "description": "u_customer_money_mover is uncertified."}
    ])

    enriched = rca_engine.categorize_dataframe(df)
    assert len(enriched) == 4
    assert "rca_scenario" in enriched.columns
    assert "rca_category" in enriched.columns
    assert "rca_domain" in enriched.columns
    assert "rca_risk_level" in enriched.columns
    assert "rca_recommended_action" in enriched.columns

    assert enriched.loc[0, "rca_scenario"] == "u_access_reviewer"
    assert enriched.loc[1, "rca_scenario"] == "incorrect access reviewer"
    assert enriched.loc[2, "rca_scenario"] == "business_criticality"
    assert enriched.loc[3, "rca_scenario"] == "u_customer_money_mover"

def test_top_keyword_extraction(rca_engine):
    df = pd.DataFrame([
        {"description": "u_access_reviewer unassigned for App-Finance"},
        {"description": "business_criticality and u_customer_money_mover gap"},
        {"description": "u_dr_strategy failover missing"}
    ])
    kw_df = rca_engine.extract_top_keywords(df, text_col="description", top_n=5)
    assert not kw_df.empty
    keywords = kw_df["Keyword"].tolist()
    assert "business_criticality" in keywords or "u_access_reviewer" in keywords

def test_scenario_summary_and_application_matrix(rca_engine):
    df = pd.DataFrame([
        {"sys_id": "D1", "u_application": "App-Finance", "u_field": "u_access_reviewer", "description": "Missing reviewer"},
        {"sys_id": "D2", "u_application": "App-Finance", "u_field": "business_criticality", "description": "Missing criticality"},
        {"sys_id": "D3", "u_application": "App-HR", "u_field": "u_dr_strategy", "description": "DR strategy missing"}
    ])
    enriched = rca_engine.categorize_dataframe(df)
    summary = rca_engine.get_scenario_summary(enriched)
    assert len(summary) >= 2
    assert "u_access_reviewer" in summary["rca_scenario"].values

    matrix = rca_engine.get_application_scenario_matrix(enriched)
    assert not matrix.empty
    assert "App-Finance" in matrix.index

def test_compare_campaign_scenarios(rca_engine):
    df_curr = pd.DataFrame([
        {"u_field": "u_access_reviewer", "description": "Missing reviewer"},
        {"u_field": "business_criticality", "description": "Missing criticality"}
    ])
    df_prev = pd.DataFrame([
        {"u_field": "u_dr_strategy", "description": "DR missing"},
        {"u_field": "u_access_reviewer", "description": "Missing reviewer"}
    ])
    curr_enc = rca_engine.categorize_dataframe(df_curr)
    prev_enc = rca_engine.categorize_dataframe(df_prev)

    comp = rca_engine.compare_campaign_scenarios(curr_enc, prev_enc)
    assert not comp.empty
    assert "Audited Category" in comp.columns
    assert "Share Shift (% Points)" in comp.columns
