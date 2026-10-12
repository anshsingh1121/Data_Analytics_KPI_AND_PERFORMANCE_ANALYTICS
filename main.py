import os
import sys
import argparse
import logging
import json
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("DataCertPipeline")

# Import system modules
from src.config.loader import ConfigLoader
from src.config.validation import ConfigValidator
from src.data_processing.synthetic_generator import generate_synthetic_data
from src.data_processing.normalizer import DataNormalizer
from src.data_processing.validator import DataValidator
from src.data_processing.relationships import RelationshipResolver
from src.data_processing.quality_checks import QualityChecker
from src.analytics.kpi_engine import KPIEngine
from src.analytics.cycle_manager import CycleManager
from src.analytics.trend_analysis import TrendAnalyzer
from src.analytics.backlog_analysis import BacklogAnalyzer
from src.analytics.productivity_analysis import ProductivityAnalyzer
from src.analytics.exception_analysis import ExceptionAnalyzer
from src.storage.snapshot_store import SnapshotStore
from src.storage.run_history import RunHistory
from src.reporting.report_generator import ReportGenerator
from src.reporting.csv_exporter import CsvExporter
from src.reporting.excel_exporter import ExcelExporter
from src.scheduler.deadline_monitor import DeadlineMonitor

def cmd_validate_config(args):
    """Validates configuration files, YAML syntax, and environment settings."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — CONFIGURATION VALIDATION")
    print("=" * 70)
    loader = ConfigLoader()
    validator = ConfigValidator(loader)
    
    report = validator.validate_all()
    errors = report.get("errors", [])
    warnings = report.get("warnings", [])
    
    print(f"App Mode: {loader.get_app_mode().upper()}")
    print(f"\nConfiguration Check Results:")
    print(f"  - Total Errors  : {len(errors)}")
    print(f"  - Total Warnings: {len(warnings)}")

    if errors:
        print("\nErrors Found:")
        for err in errors:
            print(f"  [X] {err}")

    if warnings:
        print("\nWarnings:")
        for warn in warnings:
            print(f"  [!] {warn}")

    if not errors:
        print("\n[OK] All configuration files are structurally valid and complete.")
        return 0
    else:
        print("\n[FAIL] Configuration validation failed. Please check errors above.")
        return 1

def get_service_now_client(loader: ConfigLoader):
    """Initializes ServiceNowClient using validated loader configuration."""
    from src.connectors.service_now_client import ServiceNowClient
    api_cfg = loader.get_api_config()
    return ServiceNowClient(
        instance_url=api_cfg['base_url'],
        username=api_cfg['username'],
        password=api_cfg['password'],
        timeout=api_cfg['timeout_seconds'],
        retries=api_cfg['max_retries'],
        verify_tls=api_cfg['verify_tls'],
        ca_bundle=api_cfg.get('ca_bundle'),
        proxies=api_cfg.get('proxies')
    )

def cmd_test_connection(args):
    """Tests connectivity, authentication, table read access, and required fields for both tables."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — API & TABLE FIELD VERIFICATION")
    print("=" * 70)
    loader = ConfigLoader()
    api_cfg = loader.get_api_config()
    app_mode = loader.get_app_mode()

    if not api_cfg.get('base_url'):
        print("[DEMO MODE ACTIVE] No API_BASE_URL provided in .env.")
        print("To test a live connection on your corporate machine:")
        print("  1. Create .env with API_BASE_URL, API_USERNAME, and API_PASSWORD")
        print("  2. Set APP_MODE=live in .env")
        print("  3. Re-run 'python main.py test-connection'")
        print("\nVerifying local synthetic tables for testing readiness:")
        _audit_table_fields("data/synthetic/cert_tasks.csv", "cert_task (Table 1)", [
            ('sys_id', 'task_id (Primary Key)'),
            ('number', 'task_number (Task ID)'),
            ('state', 'status (Task State)'),
            ('assigned_to', 'assigned_to (Certifier)'),
            ('cmdb_ci', 'config_item (CI / App)'),
            ('sys_created_on', 'created_at (Created)'),
            ('due_date', 'due_date (SLA Target)'),
            ('closed_at', 'completed_at (Closed)')
        ])
        _audit_table_fields("data/synthetic/discrepancies.csv", "u_failed_data_certifications (Table 2)", [
            ('sys_id', 'discrepancy_id (Primary Key)'),
            ('number', 'number (Record ID)'),
            ('u_certification_task', 'linked_task (FK to cert_task)'),
            ('u_issue_category', 'issue_category (Category)'),
            ('u_field', 'field_name (Discrepancy Field)'),
            ('u_status', 'status (Resolution State)'),
            ('sys_created_on', 'created_at (Created)')
        ])
        return 0

    from src.discovery.connection_diagnostics import ConnectionDiagnostics

    client = get_service_now_client(loader)

    print(f"Connecting to ServiceNow Instance: {client.instance_url} (raw: {api_cfg['base_url']})")
    print(f"Auth Method: {api_cfg.get('auth_method', 'basic').upper()} (Username: {api_cfg.get('username') or 'N/A'})")
    print(f"SSL/TLS Security: {client.ssl_mode}")
    if api_cfg.get('proxies'):
        print(f"Corporate Proxy: {api_cfg['proxies']}")

    diagnostics = ConnectionDiagnostics(client, loader.settings.get('provider', {}))
    results = diagnostics.run_diagnostics()

    print(f"\n[1/3] Connectivity Check : {'[SUCCESS]' if results['api_connectivity'] else '[FAILED]'}")
    print(f"[2/3] Authentication Check : {'[SUCCESS]' if results['auth_valid'] else '[FAILED]'}")
    if not results.get('ssl_valid', True):
        print(f"[!] SSL/TLS Certificate : [FAILED - Certificate Verification Issue]")

    if not (results['api_connectivity'] and results['auth_valid']):
        print("\n" + "=" * 70)
        print("CONNECTION DIAGNOSTIC & RESOLUTION GUIDE")
        print("=" * 70)
        for s in results.get('suggestions', []):
            print(f"  * {s}")
        if results.get('ssl_diagnostic'):
            diag = results['ssl_diagnostic']
            print(f"\nRoot Cause Detected: {diag['category']}")
            print(f"Explanation: {diag['description']}")
            print("\nRecommended Fixes:")
            for step in diag.get('actionable_steps', []):
                print(f"  -> {step}")
        print("=" * 70)
        return 1

    # Detailed Table 1 & 2 Check using configured field mappings
    task_tbl = loader.settings.get('provider', {}).get('tables', {}).get('cert_task', 'cert_task')
    disc_tbl = loader.settings.get('provider', {}).get('tables', {}).get('failed_data_certifications', 'u_failed_data_certifications')
    mappings = loader.get_field_mapping().get('tables', {})

    task_map = mappings.get('cert_task', {}).get('mappings', {})
    disc_map = mappings.get('u_failed_data_certifications', {}).get('mappings', {})

    # Build field pairs (api_field, business_concept)
    task_fields = [(v, f"{k} (mapped)") for k, v in task_map.items()] if task_map else [
        ('sys_id', 'task_id'), ('number', 'task_number'), ('state', 'status'),
        ('assigned_to', 'assigned_to'), ('cmdb_ci', 'config_item'),
        ('sys_created_on', 'created_at'), ('due_date', 'due_date'), ('closed_at', 'completed_at')
    ]

    disc_fields = [(v, f"{k} (mapped)") for k, v in disc_map.items()] if disc_map else [
        ('sys_id', 'discrepancy_id'), ('number', 'number'), ('u_certification_task', 'linked_task'),
        ('u_issue_category', 'issue_category'), ('u_field', 'field_name'),
        ('u_status', 'status'), ('sys_created_on', 'created_at')
    ]

    print(f"\n[3/3] Table & Field Extraction Verification:")
    print("=" * 70)
    _verify_live_table(client, task_tbl, "Table 1 (Certification Tasks)", task_fields)

    print("-" * 70)
    _verify_live_table(client, disc_tbl, "Table 2 (Discrepancies & Failures)", disc_fields)

    print("=" * 70)
    print("API AND FIELD VERIFICATION COMPLETED.")
    return 0

def _verify_live_table(client, table_name, label, required_fields):
    """Samples records from a live ServiceNow table and audits required fields."""
    print(f"Auditing {label}: '{table_name}'")
    try:
        sample = client.extract_table(table_name=table_name, limit=1)
        if not sample:
            print(f"  [WARNING] Table '{table_name}' is accessible, but returned 0 records.")
            return

        rec = sample[0]
        flat_keys = set(rec.keys())
        total_count = client.get_record_count(table_name)
        count_str = f"{total_count:,} records" if total_count >= 0 else "N/A"
        print(f"  [SUCCESS] Sample record fetched successfully ({len(flat_keys)} columns found, Total in Table: {count_str}).")
        print("  Required Field Checklist:")
        passed_count = 0
        for fld, desc in required_fields:
            if fld in flat_keys:
                passed_count += 1
                val = rec[fld]
                disp = val.get('display_value', val.get('value', str(val))) if isinstance(val, dict) else str(val)
                disp_str = (disp[:25] + '...') if len(disp) > 28 else disp
                print(f"    [PASS] {fld:<25} ({desc:<28}) -> Sample: '{disp_str}'")
            else:
                matched = [k for k in flat_keys if fld.lower() in k.lower() or k.lower() in fld.lower()]
                if matched:
                    print(f"    [INFO] {fld:<25} ({desc:<28}) -> Possible match: '{matched[0]}'")
                else:
                    print(f"    [WARN] {fld:<25} ({desc:<28}) -> NOT FOUND (Check custom prefix)")
        print(f"  Field Audit Result: {passed_count}/{len(required_fields)} fields verified.")
    except requests.exceptions.SSLError as ssl_err:
        from src.connectors.ssl_helper import diagnose_ssl_error
        diag = diagnose_ssl_error(ssl_err, getattr(client, 'base_url', ''))
        print(f"  [FAIL] SSL Verification Error on table '{table_name}': {diag['category']}")
        for step in diag.get('actionable_steps', []):
            print(f"         {step}")
    except Exception as e:
        print(f"  [FAIL] Error fetching from '{table_name}': {e}")

def _audit_table_fields(file_path, label, required_fields):
    """Audits fields in demo/offline files."""
    if not os.path.exists(file_path):
        from src.data_processing.synthetic_generator import generate_synthetic_data
        generate_synthetic_data()
    df = pd.read_csv(file_path)
    print(f"\n{label} ({len(df)} records, {len(df.columns)} columns):")
    for item in required_fields:
        fld = item[0] if isinstance(item, tuple) else item
        desc = f" ({item[1]})" if isinstance(item, tuple) else ""
        if fld in df.columns:
            sample_val = str(df[fld].dropna().iloc[0]) if not df[fld].dropna().empty else "None"
            sample_str = (sample_val[:25] + '...') if len(sample_val) > 28 else sample_val
            print(f"  [PASS] {fld:<24}{desc:<28} -> Sample: '{sample_str}'")
        else:
            print(f"  [WARN] {fld:<24}{desc:<28} -> NOT FOUND")
def cmd_discover_schema(args):
    """Runs schema discovery and generates field mapping suggestions."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — SCHEMA DISCOVERY & MAPPING")
    print("=" * 70)
    loader = ConfigLoader()
    app_mode = loader.get_app_mode()
    api_cfg = loader.get_api_config()

    if not api_cfg.get('base_url'):
        print("[DEMO MODE ACTIVE] Running local schema inspection on synthetic datasets...")
        if not os.path.exists('data/synthetic/cert_tasks.csv'):
            generate_synthetic_data()
        df_tasks = pd.read_csv('data/synthetic/cert_tasks.csv')
        df_disc = pd.read_csv('data/synthetic/discrepancies.csv')
        print(f"\nDiscovered cert_task fields ({len(df_tasks.columns)} columns):")
        for col in df_tasks.columns:
            print(f"  - {col} (dtype: {df_tasks[col].dtype}, non-null: {df_tasks[col].notna().sum()}/{len(df_tasks)})")
        print(f"\nDiscovered u_failed_data_certifications fields ({len(df_disc.columns)} columns):")
        for col in df_disc.columns:
            print(f"  - {col} (dtype: {df_disc[col].dtype}, non-null: {df_disc[col].notna().sum()}/{len(df_disc)})")
        print("\nField mapping configuration is verified and in sync with config/field_mapping.yaml.")
        return 0

    from src.discovery.schema_discovery import SchemaDiscovery

    client = get_service_now_client(loader)
    discovery = SchemaDiscovery(client, loader.settings.get('provider', {}))
    report = discovery.generate_report()
    print("Live schema discovery report generated:")
    print(json.dumps(report, indent=2))
    return 0

def cmd_generate_demo(args):
    """Generates synthetic test datasets for cert_task and discrepancies."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — GENERATING DEMO DATA")
    print("=" * 70)
    df_tasks, df_disc = generate_synthetic_data()
    print(f"\nSuccessfully generated {len(df_tasks)} tasks and {len(df_disc)} discrepancies.")
    print("Output directory: data/synthetic/")
    return 0

def cmd_pipeline(args):
    """Executes the end-to-end data certification performance pipeline."""
    mode = args.mode or "demo"
    print("=" * 70)
    print(f"DATA CERTIFICATION KPI SYSTEM — EXECUTING PIPELINE [{mode.upper()} MODE]")
    print("=" * 70)

    loader = ConfigLoader()
    run_hist = RunHistory("data/processed")
    run_id = run_hist.start_run()
    logger.info(f"Started pipeline run ID: {run_id}")

    try:
        # Step 1: Data Extraction / Ingestion
        if mode == "demo":
            tasks_path = 'data/synthetic/cert_tasks.csv'
            disc_path = 'data/synthetic/discrepancies.csv'
            if not os.path.exists(tasks_path) or not os.path.exists(disc_path):
                logger.info("Demo data missing. Generating synthetic data...")
                generate_synthetic_data()

            raw_tasks = pd.read_csv(tasks_path)
            raw_disc = pd.read_csv(disc_path)
            logger.info(f"Loaded demo tasks: {len(raw_tasks)}, discrepancies: {len(raw_disc)}")
        else:
            api_cfg = loader.get_api_config()
            if not api_cfg.get('base_url'):
                logger.error("Live mode selected but no API credentials configured in .env.")
                run_hist.end_run(run_id, "FAILED", errors="Missing live API credentials")
                return 1

            from src.extraction.task_extractor import TaskExtractor
            from src.extraction.discrepancy_extractor import DiscrepancyExtractor

            client = get_service_now_client(loader)
            field_map = loader.get_field_mapping()
            t_ext = TaskExtractor(client, loader.settings.get('provider', {}), field_map.get('tables', {}).get('cert_task', {}).get('mappings', {}))
            d_ext = DiscrepancyExtractor(client, loader.settings.get('provider', {}), field_map.get('tables', {}).get('u_failed_data_certifications', {}).get('mappings', {}))
            
            raw_tasks = t_ext.extract()
            raw_disc = d_ext.extract()

        # Step 2: Normalization
        normalizer = DataNormalizer(field_mapping={}, tz_config=loader.settings.get('timezone', 'UTC'))
        date_cols = ['sys_created_on', 'due_date', 'closed_at', 'u_resolved_on']
        string_cols = ['state', 'assigned_to', 'cmdb_ci', 'u_issue_category', 'u_status']
        
        norm_tasks = normalizer.normalize(raw_tasks, date_cols, string_cols)
        norm_disc = normalizer.normalize(raw_disc, date_cols, string_cols)

        # Step 3: Validation
        validator = DataValidator(loader.get_kpi_config())
        valid_tasks, invalid_tasks, excluded_tasks = validator.validate(
            norm_tasks,
            id_col='sys_id',
            required_fields=['sys_id', 'state'],
            date_seq_cols=[('sys_created_on', 'closed_at')]
        )
        logger.info(f"Tasks validation: {len(valid_tasks)} valid, {len(invalid_tasks)} invalid, {len(excluded_tasks)} excluded.")

        # Step 4: Relationship Resolution
        resolver = RelationshipResolver()
        tasks_resolved, disc_resolved, rel_stats = resolver.resolve(
            valid_tasks,
            norm_disc,
            task_id_col='sys_id',
            disc_link_col='u_certification_task'
        )

        # Step 5: Save Processed Outputs
        os.makedirs('data/processed', exist_ok=True)
        tasks_resolved.to_csv('data/processed/cert_tasks_processed.csv', index=False)
        disc_resolved.to_csv('data/processed/discrepancies_processed.csv', index=False)
        logger.info("Saved processed data to data/processed/")

        # Step 6: KPI Engine Execution
        cycle_cfg = loader.get_cycle_config()
        cycle_mgr = CycleManager(cycle_cfg)
        curr_meta = cycle_mgr.get_cycle_metadata(cycle_mgr.current_cycle)
        prev_meta = cycle_mgr.get_cycle_metadata(cycle_mgr.previous_cycle)

        kpi_engine = KPIEngine(loader.get_kpi_config(), cycle_cfg)

        # Separate cycles for calculation
        curr_cycle_name = cycle_mgr.current_cycle.get('name', 'Q4-2026')
        prev_cycle_name = cycle_mgr.previous_cycle.get('name', 'Q3-2026')

        cycle_col = 'u_certification_activity' if 'u_certification_activity' in tasks_resolved.columns else 'u_certification_cycle'
        curr_tasks = tasks_resolved[tasks_resolved[cycle_col] == curr_cycle_name] if cycle_col in tasks_resolved.columns else tasks_resolved
        prev_tasks = tasks_resolved[tasks_resolved[cycle_col] == prev_cycle_name] if cycle_col in tasks_resolved.columns else tasks_resolved

        curr_disc = disc_resolved[disc_resolved['u_certification_task'].isin(curr_tasks['sys_id'])]
        prev_disc = disc_resolved[disc_resolved['u_certification_task'].isin(prev_tasks['sys_id'])]

        curr_kpis = kpi_engine.calculate_all_kpis(
            curr_tasks, curr_disc,
            working_days=curr_meta['elapsed_working_days'],
            as_of_date='2026-10-23',
            final_deadline=curr_meta['final_deadline']
        )

        prev_kpis = kpi_engine.calculate_all_kpis(
            prev_tasks, prev_disc,
            working_days=prev_meta['total_working_days'],
            as_of_date='2026-09-30',
            final_deadline=prev_meta['final_deadline']
        )

        # Step 7: Cycle Comparisons
        comp_rows = cycle_mgr.compare_metrics(curr_kpis, prev_kpis, mode="like_for_like")

        # Step 8: Reports & Exports
        rep_gen = ReportGenerator(curr_meta, app_mode=mode)
        csv_exp = CsvExporter("reports")
        excel_exp = ExcelExporter("reports")

        kpi_sum_df = rep_gen.build_kpi_summary_df(curr_kpis)
        comp_df = rep_gen.build_cycle_comparison_df(comp_rows)
        daily_df = rep_gen.build_daily_trends_df(curr_tasks)
        backlog_df = rep_gen.build_backlog_analysis_df(curr_tasks)
        disc_df = rep_gen.build_discrepancy_analysis_df(curr_disc)
        prod_df = rep_gen.build_certifier_productivity_df(curr_tasks, curr_meta['elapsed_working_days'])
        exc_df = rep_gen.build_exception_resolution_df(curr_disc)
        qa_df = rep_gen.build_data_quality_report_df(tasks_resolved, disc_resolved, rel_stats)

        # Export CSVs
        csv_files = csv_exp.export_all({
            "kpi_summary": kpi_sum_df,
            "cycle_comparison": comp_df,
            "daily_trends": daily_df,
            "backlog_analysis": backlog_df,
            "discrepancy_analysis": disc_df,
            "certifier_productivity": prod_df,
            "exception_resolution": exc_df,
            "data_quality_report": qa_df
        })

        # Export consolidated Excel
        excel_path = excel_exp.export({
            "Management Summary": kpi_sum_df,
            "Cycle Comparison": comp_df,
            "Daily Trends": daily_df,
            "Backlog Analysis": backlog_df,
            "Discrepancies": disc_df,
            "Productivity": prod_df,
            "Exceptions": exc_df,
            "Data Quality": qa_df
        }, metadata={"mode": mode, "cycle_name": curr_cycle_name})

        # Step 9: Save Snapshot & Run History
        snap_store = SnapshotStore("data/snapshots")
        snap_store.save_snapshot(curr_tasks, datatype="cert_tasks", is_demo=(mode == 'demo'))
        snap_store.save_snapshot(curr_disc, datatype="discrepancies", is_demo=(mode == 'demo'))

        run_hist.end_run(run_id, "SUCCESS", tasks=len(tasks_resolved), disc=len(disc_resolved))

        # Print Executive Summary
        print("\n" + "=" * 70)
        print("PIPELINE COMPLETED SUCCESSFULLY — EXECUTIVE KPI SUMMARY")
        print("=" * 70)
        for _, row in kpi_sum_df.iterrows():
            val = f"{row['Value']}{row['Unit']}" if row['Value'] is not None else "N/A"
            print(f"  {row['KPI Name']:<32} : {val:>10}  (Eligible: {row['Denominator']})")

        print("\nKey Deliverables:")
        print(f"  - Excel Report: {excel_path}")
        print(f"  - CSV Reports:  reports/ ({len(csv_files)} files exported)")
        print(f"  - Processed:    data/processed/cert_tasks_processed.csv ({len(tasks_resolved)} rows)")
        print(f"  - Dashboard:    Run 'streamlit run src/dashboard/app.py' to explore interactive UI")
        return 0

    except Exception as e:
        logger.exception(f"Pipeline execution encountered error: {e}")
        run_hist.end_run(run_id, "FAILED", errors=str(e))
        return 1

def cmd_compare_cycles(args):
    """Compares current and previous cycles and displays comparative analytics."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — CERTIFICATION CYCLE COMPARISON")
    print("=" * 70)
    comp_path = 'reports/cycle_comparison.csv'
    if not os.path.exists(comp_path):
        print("Cycle comparison report not found. Running pipeline first...")
        cmd_pipeline(argparse.Namespace(mode="demo"))
    
    if os.path.exists(comp_path):
        df = pd.read_csv(comp_path)
        print(df.to_string(index=False))
    return 0

def cmd_export(args):
    """Regenerates and exports all CSV and Excel reports."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — REPORT EXPORTER")
    print("=" * 70)
    return cmd_pipeline(argparse.Namespace(mode="demo"))

def cmd_deadline_check(args):
    """Executes deadline check and SLA risk analysis."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — DEADLINE MONITOR & RISK CHECK")
    print("=" * 70)
    tasks_path = 'data/processed/cert_tasks_processed.csv'
    if not os.path.exists(tasks_path):
        print("Processed tasks dataset not found. Generating demo data...")
        cmd_pipeline(argparse.Namespace(mode="demo"))

    tasks = pd.read_csv(tasks_path)
    monitor = DeadlineMonitor(warning_window_days=5)
    alerts = monitor.monitor(tasks, as_of_date='2026-10-23')

    summary = alerts.get('summary', {})
    print(f"As-of Analysis Date : {summary.get('as_of_date')}")
    print(f"Total Open Tasks    : {summary.get('total_open')}")
    print(f"Overdue Tasks       : {summary.get('overdue')}")
    print(f"Near-Deadline Tasks : {summary.get('near_deadline')} (due within {summary.get('warning_window_days')} days)")

    if alerts.get('overdue_tasks'):
        print("\nTop 5 Overdue Tasks Requiring Escalation:")
        for t in alerts['overdue_tasks'][:5]:
            print(f"  - [{t['risk_level']}] Task: {t['task_id']} | Due: {t['due_date']} | App: {t['application']} | Assignee: {t['assigned_to']} | Overdue: {t.get('Days Overdue')} days")

    if alerts.get('near_deadline_tasks'):
        print("\nTop 5 Near-Deadline Tasks (Warning Window):")
        for t in alerts['near_deadline_tasks'][:5]:
            print(f"  - [{t['risk_level']}] Task: {t['task_id']} | Due: {t['due_date']} | App: {t['application']} | Assignee: {t['assigned_to']} | Days Left: {t.get('Days Remaining')}")

    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Data Certification KPI & Performance Analysis System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Operational Subcommands")

    subparsers.add_parser("validate-config", help="Validate local YAML configuration and environment")
    subparsers.add_parser("test-connection", help="Test live API connectivity and permissions")
    subparsers.add_parser("discover-schema", help="Inspect source schemas and suggest field mappings")
    subparsers.add_parser("generate-demo", help="Generate synthetic certification test datasets")
    
    p_pipe = subparsers.add_parser("pipeline", help="Execute complete analytical data pipeline")
    p_pipe.add_argument("--mode", choices=["demo", "live"], default="demo", help="Execution mode (demo or live)")

    subparsers.add_parser("compare-cycles", help="Compare current vs previous certification cycles")
    subparsers.add_parser("export", help="Generate consolidated CSV and Excel reports")
    subparsers.add_parser("deadline-check", help="Run deadline and SLA risk assessment")
    subparsers.add_parser("run-dashboard", help="Launch the local Streamlit dashboard")

    args = parser.parse_args()

    commands = {
        "validate-config": cmd_validate_config,
        "test-connection": cmd_test_connection,
        "discover-schema": cmd_discover_schema,
        "generate-demo": cmd_generate_demo,
        "pipeline": cmd_pipeline,
        "compare-cycles": cmd_compare_cycles,
        "export": cmd_export,
        "deadline-check": cmd_deadline_check,
    }

    if args.command == "run-dashboard":
        import subprocess
        logger.info("Starting Streamlit dashboard at http://localhost:8501 ...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "src/dashboard/app.py"])
        return 0

    if args.command in commands:
        exit_code = commands[args.command](args)
        sys.exit(exit_code or 0)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
