import os
import pytest
import pandas as pd
try:
    from src.data_processing.synthetic_generator import generate_synthetic_data
except ImportError:
    generate_synthetic_data = None
from src.storage.snapshot_store import SnapshotStore
from src.storage.run_history import RunHistory
from src.reporting.csv_exporter import CsvExporter
from src.reporting.excel_exporter import ExcelExporter
from src.scheduler.deadline_monitor import DeadlineMonitor

@pytest.mark.skipif(generate_synthetic_data is None, reason="Synthetic data generator is decoupled")
def test_synthetic_data_generation(tmp_path):
    out_dir = str(tmp_path / "synthetic")
    tasks, disc = generate_synthetic_data(output_dir=out_dir)
    assert len(tasks) >= 10200 # All annual quarters generated
    assert len(disc) > 0
    assert os.path.exists(os.path.join(out_dir, "cert_tasks.csv"))
    assert os.path.exists(os.path.join(out_dir, "discrepancies.csv"))

def test_snapshot_store_and_run_history(tmp_path):
    store_dir = str(tmp_path / "snapshots")
    store = SnapshotStore(data_dir=store_dir)
    df = pd.DataFrame({"id": ["A1", "A2"], "val": [10, 20]})
    snap_id = store.save_snapshot(df, datatype="test_data", is_demo=True)
    assert snap_id is not None
    loaded = store.load_snapshot(snap_id)
    assert loaded is not None
    assert len(loaded) == 2

    hist = RunHistory(data_dir=store_dir)
    run_id = hist.start_run()
    assert run_id.startswith("run_")
    hist.end_run(run_id, status="SUCCESS", tasks=100, disc=10)
    runs = hist.get_runs(limit=5)
    assert len(runs) >= 1
    assert runs[0]['status'] == "SUCCESS"

def test_exporters(tmp_path):
    report_dir = str(tmp_path / "reports")
    csv_exp = CsvExporter(output_dir=report_dir)
    excel_exp = ExcelExporter(output_dir=report_dir)

    df = pd.DataFrame({"Metric": ["Completion"], "Value": [97.5]})
    csv_files = csv_exp.export_all({"summary": df})
    assert len(csv_files) >= 1

    excel_file = excel_exp.export({"Summary": df}, metadata={"mode": "demo"})
    assert excel_file != ""
    assert os.path.exists(excel_file)

def test_deadline_monitor():
    monitor = DeadlineMonitor(warning_window_days=5)
    df = pd.DataFrame({
        "number": ["T1", "T2", "T3"],
        "state": ["Open", "Open", "Closed Complete"],
        "due_date": ["2026-10-20", "2026-10-26", "2026-10-20"],
        "assigned_to": ["Certifier_01", "Certifier_02", "Certifier_01"]
    })
    alerts = monitor.monitor(df, as_of_date="2026-10-23")
    # T1 is open and due 2026-10-20 -> Overdue
    # T2 is open and due 2026-10-26 -> Near deadline (3 days away, <= 5)
    # T3 is closed complete -> Ignored
    assert alerts['summary']['overdue'] == 1
    assert alerts['summary']['near_deadline'] == 1

def test_snapshot_store_duplicate_columns(tmp_path):
    store_dir = str(tmp_path / "snapshots_dup")
    store = SnapshotStore(data_dir=store_dir)
    # Construct DataFrame with duplicate column names
    df = pd.DataFrame([[1, 2, 3]], columns=["col_a", "short_description", "short_description"])
    assert list(df.columns) == ["col_a", "short_description", "short_description"]
    
    # Saving must succeed and automatically deduplicate columns
    snap_id = store.save_snapshot(df, datatype="cert_tasks", is_demo=True)
    assert snap_id is not None
    loaded = store.load_snapshot(snap_id)
    assert loaded is not None
    assert len(loaded.columns) == 2
    assert list(loaded.columns) == ["col_a", "short_description"]

def test_report_generator_slice_no_warning():
    import warnings
    from src.reporting.report_generator import ReportGenerator
    
    rep_gen = ReportGenerator(app_mode="live")
    full_df = pd.DataFrame({
        "u_certification_task": ["TASK1", "TASK2"],
        "category": ["A", "B"],
        "status": ["Open", "Closed"],
        "certification_cycle": ["Q4-2026", "Q2-2026"]
    })
    # Create a slice from DataFrame
    sliced_df = full_df[full_df["certification_cycle"] == "Q4-2026"]
    
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        res = rep_gen.build_discrepancy_analysis_df(sliced_df)
        setting_with_copy = [item for item in w if issubclass(item.category, pd.errors.SettingWithCopyWarning)]
        assert len(setting_with_copy) == 0
        assert not res.empty

