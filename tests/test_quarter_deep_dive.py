import pytest
import pandas as pd
import pyarrow as pa
from src.config.loader import ConfigLoader
from src.analytics.kpi_engine import KPIEngine
from src.analytics.cycle_manager import CycleManager
from src.reporting.report_generator import ReportGenerator

def test_build_cycle_comparison_df_unique_columns():
    """Verify that build_cycle_comparison_df produces strictly unique column names."""
    rep_gen = ReportGenerator(app_mode="live")
    sample_rows = [
        {
            "metric_name": "Completion Rate",
            "metric_key": "kpi_1_certification_completion",
            "current_value": 98.5,
            "previous_value": 92.0,
            "unit": "%",
            "abs_change": 6.5,
            "pct_change": 7.07,
            "pp_change": 6.5,
            "desired_trend": "Higher is better",
            "is_favorable": True
        }
    ]
    df = rep_gen.build_cycle_comparison_df(sample_rows)
    assert not df.empty
    cols = list(df.columns)
    assert len(cols) == len(set(cols)), f"Duplicate columns found in build_cycle_comparison_df: {cols}"
    assert "Variance" in cols
    assert "Absolute Change" not in cols

def test_quarter_deep_dive_matrix_pyarrow_compatibility():
    """Verify Quarter Deep Dive renamed table generates unique columns and passes PyArrow table conversion."""
    loader = ConfigLoader()
    cycle_cfg = loader.get_cycle_config()
    cycle_mgr = CycleManager(cycle_cfg)
    kpi_engine = KPIEngine()

    tasks_df = pd.read_csv("data/processed/cert_tasks_processed.csv")
    disc_df = pd.read_csv("data/processed/discrepancies_processed.csv")

    for comp_year in [2026, 2025]:
        cfg_s = cycle_cfg.get("cycles", {}).get(f"Q2-{comp_year}", {})
        cfg_a = cycle_cfg.get("cycles", {}).get(f"Q4-{comp_year}", {})

        s_start, s_end = cfg_s.get("start_date"), cfg_s.get("end_date")
        a_start, a_end = cfg_a.get("start_date"), cfg_a.get("end_date")

        t_dates = pd.to_datetime(tasks_df["sys_created_on"], errors="coerce").dt.date
        t_spring = tasks_df[(t_dates >= pd.to_datetime(s_start).date()) & (t_dates <= pd.to_datetime(s_end).date())]
        t_autumn = tasks_df[(t_dates >= pd.to_datetime(a_start).date()) & (t_dates <= pd.to_datetime(a_end).date())]

        d_spring = disc_df[disc_df["u_certification_task"].isin(t_spring["sys_id"])]
        d_autumn = disc_df[disc_df["u_certification_task"].isin(t_autumn["sys_id"])]

        kpis_spring = kpi_engine.calculate_all_kpis(t_spring, d_spring)
        kpis_autumn = kpi_engine.calculate_all_kpis(t_autumn, d_autumn)

        comp_rows = cycle_mgr.compare_metrics(kpis_autumn, kpis_spring, mode="intra_year")
        rep_gen = ReportGenerator(cfg_a, app_mode="live")
        comp_df = rep_gen.build_cycle_comparison_df(comp_rows)

        # Apply exact dashboard logic
        comp_df = comp_df.fillna("-")
        for col_name in comp_df.columns:
            comp_df[col_name] = comp_df[col_name].replace({"None": "-", "None %": "-", "nan": "-", "NaN": "-"})
            if comp_df[col_name].dtype == "object":
                comp_df[col_name] = comp_df[col_name].astype(str)

        if "Absolute Change" in comp_df.columns and "Variance" in comp_df.columns:
            comp_df = comp_df.drop(columns=["Absolute Change"])

        comp_df = comp_df.rename(columns={
            "Current Value": f"Autumn Q4-{comp_year}",
            "Previous Value": f"Spring Q2-{comp_year}",
            "Variance": f"Variance (Q4 - Q2)",
            "Absolute Change": f"Variance (Q4 - Q2)"
        })
        comp_df = comp_df.loc[:, ~comp_df.columns.duplicated()]

        cols = list(comp_df.columns)
        assert len(cols) == len(set(cols)), f"Duplicate columns found in year {comp_year}: {cols}"
        assert f"Autumn Q4-{comp_year}" in cols
        assert f"Spring Q2-{comp_year}" in cols
        assert "Variance (Q4 - Q2)" in cols

        # Guarantee PyArrow conversion succeeds without ValueError or ArrowInvalid
        arrow_table = pa.Table.from_pandas(comp_df)
        assert arrow_table.num_columns == len(cols)

def test_defensive_column_deduplication():
    """Verify that even with intentional duplicate column names, deduplication protects PyArrow conversion."""
    df_with_dups = pd.DataFrame(
        [[1, 2, 3]],
        columns=["Metric", "Variance (Q4 - Q2)", "Variance (Q4 - Q2)"]
    )
    with pytest.raises(ValueError, match="Duplicate column names found"):
        pa.Table.from_pandas(df_with_dups)

    # Apply defensive de-duplication
    cleaned_df = df_with_dups.loc[:, ~df_with_dups.columns.duplicated()]
    table = pa.Table.from_pandas(cleaned_df)
    assert table.num_columns == 2
