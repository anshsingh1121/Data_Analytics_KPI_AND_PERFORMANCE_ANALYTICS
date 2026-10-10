import pytest
import pandas as pd
import numpy as np
from datetime import datetime
from src.analytics.kpi_engine import KPIEngine
from src.analytics.cycle_manager import CycleManager

def test_all_12_kpis(mock_tasks_df, mock_discrepancies_df):
    """Verifies that all 12 KPIs calculate correctly on test data."""
    engine = KPIEngine()
    
    # KPI 1
    kpi_1 = engine.kpi_1_certification_completion(mock_tasks_df)
    assert kpi_1['available'] is True
    assert kpi_1['value'] > 0
    # 70 closed complete out of 95 eligible (100 - 5 cancelled) = ~73.68%
    assert kpi_1['denominator'] == 95
    assert kpi_1['excluded_count'] == 5

    # KPI 2
    kpi_2 = engine.kpi_2_daily_closure_rate(mock_tasks_df, working_days_elapsed=10)
    assert kpi_2['available'] is True
    # 80 completed tasks / 10 days = 8.0
    assert kpi_2['value'] == 8.0

    # KPI 3
    kpi_3 = engine.kpi_3_on_time_completion(mock_tasks_df)
    assert kpi_3['available'] is True
    # 70 on-time out of 80 valid completed = 87.5%
    assert kpi_3['value'] == 87.5

    # KPI 4
    kpi_4 = engine.kpi_4_avg_completion_time(mock_tasks_df)
    assert kpi_4['available'] is True
    assert kpi_4['value'] is not None
    assert kpi_4['details']['count_tasks'] == 80

    # KPI 5
    kpi_5 = engine.kpi_5_discrepancy_rate(mock_tasks_df, mock_discrepancies_df)
    assert kpi_5['available'] is True
    # 20 distinct tasks linked out of 100 in scope = 20.0%
    assert kpi_5['value'] == 20.0

    # KPI 6
    kpi_6 = engine.kpi_6_data_accuracy(mock_tasks_df, mock_discrepancies_df)
    assert kpi_6['available'] is True
    assert kpi_6['value'] == 80.0 # 100 - 20

    # KPI 7
    kpi_7 = engine.kpi_7_rejection_rate(mock_tasks_df)
    assert kpi_7['available'] is True
    # 5 tasks with rework count > 0 out of 100 = 5.0%
    assert kpi_7['value'] == 5.0

    # KPI 8
    kpi_8 = engine.kpi_8_backlog_aging(mock_tasks_df, as_of_date='2026-10-23')
    assert kpi_8['available'] is True
    assert 'buckets' in kpi_8['details']

    # KPI 9
    kpi_9 = engine.kpi_9_productivity(mock_tasks_df, working_days=5)
    assert kpi_9['available'] is True
    assert kpi_9['value'] > 0

    # KPI 10
    kpi_10 = engine.kpi_10_last_minute_closure(mock_tasks_df, window_days=5)
    assert kpi_10['available'] is True

    # KPI 11
    kpi_11 = engine.kpi_11_exception_resolution(mock_discrepancies_df)
    assert kpi_11['available'] is True
    # 15 resolved with 3 days duration = 3.0 days
    assert kpi_11['value'] == 3.0

    # KPI 12
    kpi_12 = engine.kpi_12_sla_achievement(mock_tasks_df, final_deadline='2026-12-23')
    assert kpi_12['available'] is True
    assert kpi_12['denominator'] == 95

def test_zero_denominator_and_empty():
    """Verifies that empty datasets or zero denominators do not cause division by zero."""
    engine = KPIEngine()
    empty_df = pd.DataFrame()
    
    kpi_1 = engine.kpi_1_certification_completion(empty_df)
    assert kpi_1['available'] is False or kpi_1['value'] is None

    kpi_2 = engine.kpi_2_daily_closure_rate(empty_df, working_days_elapsed=0)
    assert kpi_2['available'] is False or kpi_2['value'] is None

    kpi_3 = engine.kpi_3_on_time_completion(empty_df)
    assert kpi_3['available'] is False or kpi_3['value'] is None

def test_illustrative_test_fixture_comparisons(illustrative_test_data):
    """
    Verifies Section 13 arithmetic expectations:
    - Total task volume increased by 4%
    - Completion increased by 2 percentage points
    - On-time completion increased by 5 percentage points
    - Discrepancy rate decreased by 4 percentage points
    - Rework rate decreased by 3 percentage points
    - Average completion time improved by two days
    - Relative closure rate increase is (310-260)/260 ~ 19.23% (not 24%)
    """
    prev = illustrative_test_data["previous"]
    curr = illustrative_test_data["current"]

    # Volume change
    vol_change = ((curr["total_tasks"] - prev["total_tasks"]) / prev["total_tasks"]) * 100
    assert round(vol_change, 1) == 4.0

    # Completion pp change
    comp_pp = curr["completion"] - prev["completion"]
    assert round(comp_pp, 1) == 2.0

    # On-time pp change
    ontime_pp = curr["on_time"] - prev["on_time"]
    assert round(ontime_pp, 1) == 5.0

    # Discrepancy pp change
    disc_pp = curr["discrepancy_rate"] - prev["discrepancy_rate"]
    assert round(disc_pp, 1) == -4.0

    # Rework pp change
    rework_pp = curr["rework_rate"] - prev["rework_rate"]
    assert round(rework_pp, 1) == -3.0

    # Completion time improvement
    time_imp = prev["avg_completion_time"] - curr["avg_completion_time"]
    assert round(time_imp, 1) == 2.0

    # Daily closure relative increase
    daily_rel_inc = ((curr["daily_closure"] - prev["daily_closure"]) / prev["daily_closure"]) * 100
    assert round(daily_rel_inc, 1) == 19.2

def test_daily_closure_day_fixtures(illustrative_test_data):
    """Verifies day 1-5 closure difference fixtures from Section 13."""
    days = illustrative_test_data["daily_closure_days"]
    assert days[0]["current"] - days[0]["previous"] == 50
    assert days[1]["current"] - days[1]["previous"] == 60
    assert days[2]["current"] - days[2]["previous"] == 60
    assert days[3]["current"] - days[3]["previous"] == 60
    assert days[4]["current"] - days[4]["previous"] == 50

def test_working_days_calculation():
    """Verifies working day counts exclude weekends and specified holidays."""
    cm = CycleManager(cycle_config={}, holidays=['2026-10-02']) # Friday holiday
    # Monday Oct 5 to Friday Oct 9: 5 working days
    days = cm.calculate_working_days('2026-10-05', '2026-10-09')
    assert days == 5
    # Thursday Oct 1 to Friday Oct 2 (holiday): 1 working day (Oct 1 only)
    days_hol = cm.calculate_working_days('2026-10-01', '2026-10-02')
    assert days_hol == 1
