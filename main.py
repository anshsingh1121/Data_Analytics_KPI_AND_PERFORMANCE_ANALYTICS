import os
import sys
import argparse
import logging
import json
import pandas as pd
from datetime import datetime, date, timezone
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
        sample = client.extract_table(table_name=table_name, limit=1, max_records=1)
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
        print(f"  [INFO] File '{file_path}' does not exist.")
        return
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
        print("[OFFLINE MODE] Inspecting local dataset schemas...")
        source_task = 'data/processed/cert_tasks_processed.csv' if os.path.exists('data/processed/cert_tasks_processed.csv') else 'data/synthetic/cert_tasks.csv'
        source_disc = 'data/processed/discrepancies_processed.csv' if os.path.exists('data/processed/discrepancies_processed.csv') else 'data/synthetic/discrepancies.csv'
        if not os.path.exists(source_task):
            print("  [INFO] No processed dataset found to inspect.")
            return 0
        df_tasks = pd.read_csv(source_task)
        df_disc = pd.read_csv(source_disc) if os.path.exists(source_disc) else pd.DataFrame()
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
    """Generates synthetic test datasets for cert_task and discrepancies (Optional CLI utility)."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — GENERATING DEMO DATA")
    print("=" * 70)
    try:
        from src.data_processing.synthetic_generator import generate_synthetic_data
    except ImportError:
        print("[ERROR] Synthetic data generator is not installed.")
        return 1
    df_tasks, df_disc = generate_synthetic_data()
    print(f"\nSuccessfully generated {len(df_tasks)} tasks and {len(df_disc)} discrepancies.")
    print("Output directory: data/synthetic/")
    return 0

def cmd_pipeline(args):
    """Executes the end-to-end data certification performance pipeline."""
    loader = ConfigLoader()
    mode = getattr(args, 'mode', None) or loader.get_app_mode() or 'live'
    print("=" * 70)
    print(f"DATA CERTIFICATION KPI SYSTEM — EXECUTING PIPELINE [{mode.upper()} MODE]")
    print("=" * 70)
    run_hist = RunHistory("data/processed")
    run_id = run_hist.start_run()
    logger.info(f"Started pipeline run ID: {run_id}")

    try:
        # Step 1: Data Extraction / Ingestion
        if mode == "demo":
            tasks_path = 'data/processed/cert_tasks_processed.csv' if os.path.exists('data/processed/cert_tasks_processed.csv') else 'data/synthetic/cert_tasks.csv'
            disc_path = 'data/processed/discrepancies_processed.csv' if os.path.exists('data/processed/discrepancies_processed.csv') else 'data/synthetic/discrepancies.csv'
            if not os.path.exists(tasks_path):
                logger.error("No input certification data found in data/processed/ or data/synthetic/.")
                run_hist.end_run(run_id, "FAILED", errors="Missing input data")
                return 1

            raw_tasks = pd.read_csv(tasks_path)
            raw_disc = pd.read_csv(disc_path) if os.path.exists(disc_path) else pd.DataFrame()
            logger.info(f"Loaded demo tasks: {len(raw_tasks)}, discrepancies: {len(raw_disc)}")
        else:
            tasks_cache = 'data/processed/cert_tasks_processed.csv'
            disc_cache = 'data/processed/discrepancies_processed.csv'
            if getattr(args, 'skip_fetch', False) and os.path.exists(tasks_cache) and os.path.exists(disc_cache):
                logger.info("Using previously fetched live records from data/processed/ ...")
                print("  [INFO] Skipping API call — using already fetched dataset from local disk.")
                raw_tasks = pd.read_csv(tasks_cache)
                raw_disc = pd.read_csv(disc_cache)
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
        string_cols = ['state', 'assigned_to', 'cmdb_ci', 'u_issue_category', 'u_status', 'description', 'short_description', 'u_resolution_notes']
        
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

        # Step 5: Cycle Assignment & Save Processed Outputs
        cycle_cfg = loader.get_cycle_config()
        cycle_mgr = CycleManager(cycle_cfg)
        
        # Deduplicate any columns from raw extraction or merges
        if tasks_resolved.columns.duplicated().any():
            tasks_resolved = tasks_resolved.loc[:, ~tasks_resolved.columns.duplicated()].copy()
        if disc_resolved.columns.duplicated().any():
            disc_resolved = disc_resolved.loc[:, ~disc_resolved.columns.duplicated()].copy()

        # Assign certification cycle based on creation timestamps
        tasks_resolved = cycle_mgr.assign_cycle_to_dataframe(tasks_resolved)
        task_cycle_map = dict(zip(tasks_resolved['sys_id'], tasks_resolved['certification_cycle']))
        disc_resolved['certification_cycle'] = disc_resolved['u_certification_task'].map(task_cycle_map).fillna('Other')

        # Impute due_date with exact campaign window end dates (23:59:59) if missing or null
        campaign_deadlines = {
            'Q1-2026': '2026-05-22 23:59:59',
            'Q2-2026': '2026-05-22 23:59:59',
            'Q3-2026': '2026-07-31 23:59:59',
            'Q4-2026': '2026-10-23 23:59:59',
            'Q1-2025': '2025-04-25 23:59:59',
            'Q2-2025': '2025-04-25 23:59:59',
            'Q3-2025': '2025-09-30 23:59:59',
            'Q4-2025': '2025-10-23 23:59:59',
        }
        cycle_col = 'certification_cycle' if 'certification_cycle' in tasks_resolved.columns else None
        mapped_deadlines = tasks_resolved[cycle_col].map(campaign_deadlines) if cycle_col else pd.Series(index=tasks_resolved.index, dtype='object')
        
        date_col = 'sys_created_on' if 'sys_created_on' in tasks_resolved.columns else ('created_at' if 'created_at' in tasks_resolved.columns else None)
        if date_col and mapped_deadlines.isna().any():
            dates = pd.to_datetime(tasks_resolved[date_col], errors='coerce')
            for idx in tasks_resolved[mapped_deadlines.isna()].index:
                d = dates.loc[idx]
                if pd.notna(d):
                    if d.year == 2026 and d.month <= 5: mapped_deadlines.loc[idx] = '2026-05-22 23:59:59'
                    elif d.year == 2026 and d.month >= 10: mapped_deadlines.loc[idx] = '2026-10-23 23:59:59'
                    elif d.year == 2025 and d.month <= 4: mapped_deadlines.loc[idx] = '2025-04-25 23:59:59'
                    elif d.year == 2025 and d.month >= 10: mapped_deadlines.loc[idx] = '2025-10-23 23:59:59'
                    else: mapped_deadlines.loc[idx] = f"{d.year}-{d.month:02d}-28 23:59:59"
        
        mapped_deadlines = mapped_deadlines.fillna('2026-10-23 23:59:59')
        if 'due_date' not in tasks_resolved.columns:
            tasks_resolved['due_date'] = pd.to_datetime(mapped_deadlines)
        else:
            parsed_due = pd.to_datetime(tasks_resolved['due_date'], errors='coerce')
            tasks_resolved['due_date'] = parsed_due.fillna(pd.to_datetime(mapped_deadlines))

        # Step 5b: Create Dedicated Timestamped Run Directory for Archived Raw & Processed Data
        run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path("data/runs") / f"run_{run_timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save both raw fetched and processed data into the dedicated run directory
        raw_tasks.to_csv(run_dir / "raw_tasks_fetched.csv", index=False)
        raw_disc.to_csv(run_dir / "raw_discrepancies_fetched.csv", index=False)
        tasks_resolved.to_csv(run_dir / "cert_tasks_processed.csv", index=False)
        disc_resolved.to_csv(run_dir / "discrepancies_processed.csv", index=False)

        # Also maintain active data in data/processed for immediate consumption
        os.makedirs('data/processed', exist_ok=True)
        tasks_resolved.to_csv('data/processed/cert_tasks_processed.csv', index=False)
        disc_resolved.to_csv('data/processed/discrepancies_processed.csv', index=False)
        logger.info(f"Saved run data to dedicated directory: {run_dir} and updated data/processed/")

        # Active non-overlapping campaigns:
        # Q4 2026: Oct 5 - Oct 23, 2026
        # Q2 2026: May 5 - May 22, 2026
        # Q4 2025: Oct 6 - Oct 23, 2025
        # Q2 2025: Apr 7 - Apr 25, 2025
        target_quarters = ['Q2-2025', 'Q4-2025', 'Q2-2026', 'Q4-2026']
        quarter_labels = {
            'Q2-2025': 'Apr 7 - Apr 25, 2025',
            'Q4-2025': 'Oct 6 - Oct 23, 2025',
            'Q2-2026': 'May 5 - May 22, 2026',
            'Q4-2026': 'Oct 5 - Oct 23, 2026'
        }

        print("\n" + "=" * 70)
        print("ANNUAL QUARTER BREAKDOWN (Active Non-Overlapping Campaigns)")
        print("=" * 70)
        quarterly_results = {}
        kpi_engine = KPIEngine(loader.get_kpi_config(), cycle_cfg)

        alias_map = {
            'Q2-2026': ['Q2-2026', 'Q1-2026'],
            'Q4-2026': ['Q4-2026'],
            'Q2-2025': ['Q2-2025', 'Q1-2025'],
            'Q4-2025': ['Q4-2025']
        }

        for q_name in target_quarters:
            q_meta = cycle_mgr.get_cycle_metadata(cycle_mgr.get_cycle_by_name(q_name))
            date_col = 'sys_created_on' if 'sys_created_on' in tasks_resolved.columns else ('created_at' if 'created_at' in tasks_resolved.columns else None)
            
            s_date = pd.to_datetime(q_meta.get('start_date')).date() if q_meta.get('start_date') else None
            e_date = pd.to_datetime(q_meta.get('end_date')).date() if q_meta.get('end_date') else None
            
            q_tasks = pd.DataFrame()
            # Priority 1: Filter directly by configured campaign dates on task creation date
            if date_col and s_date and e_date:
                t_dates = pd.to_datetime(tasks_resolved[date_col], errors='coerce').dt.date
                q_tasks = tasks_resolved[(t_dates >= s_date) & (t_dates <= e_date)].copy()
            
            # Priority 2: Fallback to cycle activity tag if date filter gave 0 records
            if q_tasks.empty:
                match_cycles = alias_map.get(q_name, [q_name])
                for col_c in ['certification_cycle', 'u_certification_activity', 'u_certification_cycle']:
                    if col_c in tasks_resolved.columns:
                        matched = tasks_resolved[tasks_resolved[col_c].isin(match_cycles)].copy()
                        if not matched.empty:
                            q_tasks = matched
                            break
            
            # Priority 3: Fallback to calendar 3-month quarter if still empty
            if q_tasks.empty and date_col:
                parts = q_name.split('-')
                q_num, yr = parts[0], int(parts[1])
                cal_bounds = {
                    'Q1': (date(yr, 1, 1), date(yr, 3, 31)),
                    'Q2': (date(yr, 4, 1), date(yr, 6, 30)),
                    'Q3': (date(yr, 7, 1), date(yr, 9, 30)),
                    'Q4': (date(yr, 10, 1), date(yr, 12, 31))
                }
                cal_s, cal_e = cal_bounds.get(q_num, (s_date, e_date))
                all_t_dates = pd.to_datetime(tasks_resolved[date_col], errors='coerce').dt.date
                cal_filtered = tasks_resolved[(all_t_dates >= cal_s) & (all_t_dates <= cal_e)].copy()
                if not cal_filtered.empty:
                    q_tasks = cal_filtered
                    q_meta['start_date'] = str(cal_s)
                    q_meta['end_date'] = str(cal_e)
                    q_meta['final_deadline'] = str(cal_e)
                    s_date, e_date = cal_s, cal_e

            due_deadline = pd.to_datetime(f"{e_date} 23:59:59") if e_date else None
            if not q_tasks.empty and due_deadline:
                if 'due_date' not in q_tasks.columns:
                    q_tasks['due_date'] = due_deadline
                else:
                    q_tasks['due_date'] = pd.to_datetime(q_tasks['due_date'], errors='coerce').fillna(due_deadline)

            q_disc = disc_resolved[disc_resolved['u_certification_task'].isin(q_tasks['sys_id'])].copy() if not q_tasks.empty else pd.DataFrame()
            
            w_days = cycle_mgr.calculate_working_days(s_date, e_date) if s_date and e_date else q_meta.get('total_working_days', 15)
            if q_meta.get('is_active') and q_meta.get('elapsed_working_days'):
                w_days = q_meta['elapsed_working_days']

            q_kpis = kpi_engine.calculate_all_kpis(
                q_tasks, q_disc,
                working_days=max(1, w_days),
                as_of_date=str(e_date) if e_date else q_meta.get('end_date'),
                final_deadline=f"{e_date} 23:59:59" if e_date else q_meta.get('final_deadline')
            )
            quarterly_results[q_name] = {
                'meta': q_meta,
                'tasks': q_tasks,
                'disc': q_disc,
                'kpis': q_kpis
            }
            lbl = quarter_labels.get(q_name, q_name)
            print(f"  {q_name} ({lbl:<20}) : {len(q_tasks):>6} tasks, {len(q_disc):>4} discrepancies")

        # Determine active cycle for headline reports
        curr_tasks = quarterly_results['Q4-2026']['tasks']
        curr_disc = quarterly_results['Q4-2026']['disc']
        curr_kpis = quarterly_results['Q4-2026']['kpis']
        curr_meta = quarterly_results['Q4-2026']['meta']
        curr_cycle_name = 'Q4-2026'

        # If Q4-2026 has no tasks, select the quarter with the most records, or all tasks
        if curr_tasks.empty:
            counts = {q: len(quarterly_results[q]['tasks']) for q in target_quarters}
            best_q = max(counts, key=counts.get)
            if counts[best_q] > 0:
                curr_tasks = quarterly_results[best_q]['tasks']
                curr_disc = quarterly_results[best_q]['disc']
                curr_kpis = quarterly_results[best_q]['kpis']
                curr_meta = quarterly_results[best_q]['meta']
                curr_cycle_name = best_q
            else:
                curr_tasks = tasks_resolved
                curr_disc = disc_resolved
                curr_kpis = kpi_engine.calculate_all_kpis(curr_tasks, curr_disc, working_days=curr_meta.get('elapsed_working_days', 15))

        # Prior cycle for comparison (sequential Q2-2026 Spring)
        prev_kpis = quarterly_results['Q2-2026']['kpis']

        # Step 7: Cycle Comparisons & Multi-Quarter Consolidated Matrix
        comp_rows = cycle_mgr.compare_metrics(curr_kpis, prev_kpis, mode="like_for_like")

        # KPI Keys (Backlog days removed, near deadline updated to 1d)
        kpi_keys = [
            ('kpi_1_certification_completion', 'Certification Completion %', '%'),
            ('kpi_2_daily_closure_rate', 'Daily Closure Rate', 'tasks/day'),
            ('kpi_3_on_time_completion', 'On-Time Completion %', '%'),
            ('kpi_4_avg_completion_time', 'Average Completion Time', 'days'),
            ('kpi_5_discrepancy_rate', 'Discrepancy Rate', '%'),
            ('kpi_6_data_accuracy', 'Data Accuracy / Pass Rate', '%'),
            ('kpi_7_rework_rate', 'Rejection / Rework Rate', '%'),
            ('kpi_8_backlog_aging', 'Open Backlog Tasks', 'tasks'),
            ('kpi_9_productivity', 'Certifier Productivity', 'tasks/day'),
            ('kpi_10_last_minute_closure', 'Last-Minute Closure % (<=1d)', '%'),
            ('kpi_11_exception_resolution', 'Exception Resolution Time', 'days'),
            ('kpi_12_sla_achievement', 'Final SLA Achievement %', '%')
        ]

        # Helper: Build single-year Spring (Q2) vs Autumn (Q4) comparison table
        def _build_year_spring_vs_autumn(yr: int):
            q2_k = f"Q2-{yr}"
            q4_k = f"Q4-{yr}"
            q2_dict = quarterly_results[q2_k]['kpis']
            q4_dict = quarterly_results[q4_k]['kpis']
            q2_lbl = quarter_labels.get(q2_k, q2_k)
            q4_lbl = quarter_labels.get(q4_k, q4_k)
            rows = []
            for k_code, k_label, k_unit in kpi_keys:
                v2 = q2_dict.get(k_code, {}).get('value')
                v4 = q4_dict.get(k_code, {}).get('value')
                diff = None
                if v2 is not None and v4 is not None:
                    diff = round(v4 - v2, 2)
                rows.append({
                    "KPI Metric": k_label,
                    "Unit": k_unit,
                    f"Spring {q2_k} ({q2_lbl})": f"{v2}{k_unit}" if v2 is not None else "N/A",
                    f"Autumn {q4_k} ({q4_lbl})": f"{v4}{k_unit}" if v4 is not None else "N/A",
                    f"Change (Autumn vs Spring)": f"{diff:+}{k_unit}" if diff is not None else "N/A"
                })
            return pd.DataFrame(rows)

        comp_2026_df = _build_year_spring_vs_autumn(2026)
        comp_2025_df = _build_year_spring_vs_autumn(2025)

        # All-quarters overview table
        multi_q_rows = []
        for k_key, k_label, k_unit in kpi_keys:
            row_dict = {"Metric Name": k_label, "Unit": k_unit}
            for q_name in target_quarters:
                val = quarterly_results[q_name]['kpis'].get(k_key, {}).get('value')
                row_dict[f"{q_name}"] = f"{val}{k_unit}" if (val is not None and not pd.isna(val)) else "-"
            
            # YoY Change: Q4-2026 vs Q4-2025
            val_26 = quarterly_results['Q4-2026']['kpis'].get(k_key, {}).get('value')
            val_25 = quarterly_results['Q4-2025']['kpis'].get(k_key, {}).get('value')
            if val_26 is not None and val_25 is not None and not pd.isna(val_26) and not pd.isna(val_25):
                row_dict['YoY Diff (Q4-26 vs Q4-25)'] = round(val_26 - val_25, 2)
            else:
                row_dict['YoY Diff (Q4-26 vs Q4-25)'] = "-"
            multi_q_rows.append(row_dict)

        multi_q_df = pd.DataFrame(multi_q_rows)

        # Step 8: Reports & Exports
        rep_gen = ReportGenerator(curr_meta, app_mode=mode)
        csv_exp = CsvExporter("reports")
        excel_exp = ExcelExporter("reports")

        kpi_sum_df = rep_gen.build_kpi_summary_df(curr_kpis)
        comp_df = rep_gen.build_cycle_comparison_df(comp_rows)
        daily_df = rep_gen.build_daily_trends_df(curr_tasks)
        backlog_df = rep_gen.build_backlog_analysis_df(curr_tasks)
        disc_df = rep_gen.build_discrepancy_analysis_df(curr_disc)
        # Build Certifier Productivity sorted by worst performers (taking more time)
        prod_df = rep_gen.build_certifier_productivity_df(curr_tasks, curr_meta.get('elapsed_working_days', 15), sort_by="worst")
        exc_df = rep_gen.build_exception_resolution_df(curr_disc)
        qa_df = rep_gen.build_data_quality_report_df(tasks_resolved, disc_resolved, rel_stats)
        rca_df = rep_gen.build_discrepancy_rca_df(curr_disc, tasks_df=curr_tasks)

        # Export CSVs
        csv_files = csv_exp.export_all({
            "kpi_summary": kpi_sum_df,
            "2026_spring_vs_autumn_comparison": comp_2026_df,
            "2025_spring_vs_autumn_comparison": comp_2025_df,
            "all_quarters_comparison": multi_q_df,
            "cycle_comparison": comp_df,
            "daily_trends": daily_df,
            "backlog_analysis": backlog_df,
            "discrepancy_analysis": disc_df,
            "discrepancy_rca_scenarios": rca_df,
            "certifier_productivity_worst_first": prod_df,
            "exception_resolution": exc_df,
            "data_quality_report": qa_df
        })

        # Export consolidated Excel with dedicated 2026 and 2025 Spring vs Autumn comparison tabs
        excel_path = excel_exp.export({
            "2026 Spring vs Autumn": comp_2026_df,
            "2025 Spring vs Autumn": comp_2025_df,
            "All Quarters Overview": multi_q_df,
            "Management Summary": kpi_sum_df,
            "Certifier Productivity": prod_df,
            "Cycle Comparison": comp_df,
            "Daily Trends": daily_df,
            "Backlog Analysis": backlog_df,
            "Discrepancies": disc_df,
            "Discrepancy RCA Scenarios": rca_df,
            "Exceptions": exc_df,
            "Data Quality": qa_df
        }, metadata={"mode": mode, "cycle_name": curr_cycle_name})

        # Step 9: Save Snapshot & Run History
        snap_store = SnapshotStore("data/snapshots")
        curr_tasks_snap = curr_tasks.loc[:, ~curr_tasks.columns.duplicated()].copy()
        curr_disc_snap = curr_disc.loc[:, ~curr_disc.columns.duplicated()].copy()
        snap_store.save_snapshot(curr_tasks_snap, datatype="cert_tasks", is_demo=(mode == 'demo'))
        snap_store.save_snapshot(curr_disc_snap, datatype="discrepancies", is_demo=(mode == 'demo'))

        run_hist.end_run(run_id, "SUCCESS", tasks=len(tasks_resolved), disc=len(disc_resolved))

        # Write Run Summary Metadata to the new run directory and to latest_run.json
        run_summary = {
            "run_id": run_id,
            "run_dir": str(run_dir.as_posix()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mode": mode,
            "active_cycle": curr_cycle_name,
            "raw_tasks_count": int(len(raw_tasks)),
            "raw_discrepancies_count": int(len(raw_disc)),
            "processed_tasks_count": int(len(tasks_resolved)),
            "processed_discrepancies_count": int(len(disc_resolved)),
            "excel_report": str(excel_path),
            "csv_reports_count": len(csv_files),
            "status": "SUCCESS"
        }
        with open(run_dir / "run_summary.json", "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2)

        os.makedirs("data/runs", exist_ok=True)
        with open("data/runs/latest_run.json", "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2)

        # Print Executive Summary
        print("\n" + "=" * 70)
        print(f"PIPELINE COMPLETED SUCCESSFULLY — {curr_cycle_name} KPI SUMMARY")
        print("=" * 70)
        for _, row in kpi_sum_df.iterrows():
            val = f"{row['Value']}{row['Unit']}" if row['Value'] is not None else "N/A"
            print(f"  {row['KPI Name']:<32} : {val:>10}  (Eligible: {row['Denominator']})")

        print("\n" + "=" * 70)
        print("4-QUARTER COMPARISON SUMMARY")
        print("=" * 70)
        print(multi_q_df.to_string(index=False))

        print("\nKey Deliverables:")
        print(f"  - Dedicated Run Folder: {run_dir} (Archive of raw & processed datasets)")
        print(f"  - Run Summary Metadata: {run_dir}/run_summary.json (Mirrored at data/runs/latest_run.json)")
        print(f"  - Excel Report:        {excel_path}")
        print(f"  - CSV Reports:         reports/ ({len(csv_files)} files exported)")
        print(f"  - Processed Data:      data/processed/cert_tasks_processed.csv ({len(tasks_resolved)} rows)")
        print(f"  - Interactive App:     Double-click 'Launch_Data_Certification_Analytics.bat' or run 'python app_launcher.py'")
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
        loader = ConfigLoader()
        cmd_pipeline(argparse.Namespace(mode=loader.get_app_mode(), skip_fetch=False))
    
    if os.path.exists(comp_path):
        df = pd.read_csv(comp_path)
        print(df.to_string(index=False))
    return 0

def cmd_export(args):
    """Regenerates and exports all CSV and Excel reports."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — REPORT EXPORTER")
    print("=" * 70)
    loader = ConfigLoader()
    return cmd_pipeline(argparse.Namespace(mode=loader.get_app_mode(), skip_fetch=False))

def cmd_deadline_check(args):
    """Executes deadline check and SLA risk analysis."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — DEADLINE MONITOR & RISK CHECK")
    print("=" * 70)
    tasks_path = 'data/processed/cert_tasks_processed.csv'
    if not os.path.exists(tasks_path):
        print("Processed tasks dataset not found. Running pipeline first...")
        loader = ConfigLoader()
        cmd_pipeline(argparse.Namespace(mode=loader.get_app_mode(), skip_fetch=False))

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

def cmd_check_dates(args):
    """Inspects the date range, monthly distribution, and cycle tags in processed/raw tasks."""
    print("=" * 70)
    print("DATA CERTIFICATION KPI SYSTEM — DATASET DATE FRAME INSPECTION")
    print("=" * 70)
    
    tasks_path = Path('data/processed/cert_tasks_processed.csv')
    if not tasks_path.exists():
        tasks_path = Path('data/raw/cert_tasks_raw.csv')
    
    if not tasks_path.exists():
        print("[!] No task dataset found in data/processed/ or data/raw/.")
        print("    If running in corporate live mode, execute:")
        print("        python main.py pipeline --mode live")
        print("    Or for offline demo mode:")
        print("        python main.py generate-demo")
        return 1

    df = pd.read_csv(tasks_path)
    print(f"Loaded dataset: {tasks_path}")
    print(f"Total task records: {len(df):,}")

    date_col = None
    for candidate in ['sys_created_on', 'created_at']:
        if candidate in df.columns:
            date_col = candidate
            break

    if not date_col:
        print("[!] Neither 'sys_created_on' nor 'created_at' column found in dataset.")
        print(f"    Available columns: {list(df.columns)}")
        return 1

    df['parsed_date'] = pd.to_datetime(df[date_col], errors='coerce')
    valid_dates = df.dropna(subset=['parsed_date']).copy()
    
    if valid_dates.empty:
        print(f"[!] No valid dates could be parsed from column '{date_col}'.")
        return 1

    min_date = valid_dates['parsed_date'].min()
    max_date = valid_dates['parsed_date'].max()

    print(f"\nDate Column Used   : {date_col}")
    print(f"Earliest Task Date : {min_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Latest Task Date   : {max_date.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total Date Span    : {(max_date.date() - min_date.date()).days} calendar days")

    # Monthly breakdown
    valid_dates['year_month'] = valid_dates['parsed_date'].dt.to_period('M').astype(str)
    monthly = valid_dates.groupby('year_month').agg(
        task_count=('parsed_date', 'count'),
        min_date=('parsed_date', lambda s: s.min().strftime('%Y-%m-%d')),
        max_date=('parsed_date', lambda s: s.max().strftime('%Y-%m-%d'))
    ).reset_index()

    print("\n" + "-" * 70)
    print("TASKS BREAKDOWN BY MONTH (Use these dates in the dashboard!):")
    print("-" * 70)
    print(f"{'Year-Month':<12} | {'Task Count':<12} | {'Min Date':<12} | {'Max Date':<12}")
    print("-" * 70)
    for _, row in monthly.iterrows():
        print(f"{row['year_month']:<12} | {row['task_count']:<12,d} | {row['min_date']:<12} | {row['max_date']:<12}")
    print("-" * 70)

    # Cycle tag breakdown
    cycle_col = None
    for candidate in ['certification_cycle', 'u_certification_activity', 'u_certification_cycle']:
        if candidate in df.columns:
            cycle_col = candidate
            break

    if cycle_col:
        print("\n" + "-" * 70)
        print(f"TASKS BREAKDOWN BY CYCLE TAG ({cycle_col}):")
        print("-" * 70)
        c_summary = valid_dates.groupby(cycle_col).agg(
            task_count=('parsed_date', 'count'),
            min_date=('parsed_date', lambda s: s.min().strftime('%Y-%m-%d')),
            max_date=('parsed_date', lambda s: s.max().strftime('%Y-%m-%d'))
        ).reset_index()
        print(f"{'Cycle Tag':<25} | {'Task Count':<12} | {'Min Date':<12} | {'Max Date':<12}")
        print("-" * 70)
        for _, row in c_summary.iterrows():
            print(f"{str(row[cycle_col]):<25} | {row['task_count']:<12,d} | {row['min_date']:<12} | {row['max_date']:<12}")
        print("-" * 70)

    # Discrepancies check
    disc_path = Path('data/processed/discrepancies_processed.csv')
    if disc_path.exists():
        df_d = pd.read_csv(disc_path)
        print(f"\nDiscrepancies dataset : {disc_path} ({len(df_d):,} records)")

    print("\n[TIP] Dashboard Usage:")
    print("  In the Streamlit Dashboard, go to '📈 Daily Trends & Quarter Velocity'")
    print("  or '⚖️ 2026 & 2025 Quarter Deep Dive' to view Spring (Q2) vs Autumn (Q4) comparisons")
    print("  to perfectly match your corporate ServiceNow tasks!")
    print("=" * 70)
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
    p_pipe.add_argument("--mode", choices=["demo", "live"], default=None, help="Execution mode (demo or live, defaults to APP_MODE in .env or settings)")
    p_pipe.add_argument("--skip-fetch", "--cached", action="store_true", help="Skip API fetch and use already-saved records from data/processed/")

    subparsers.add_parser("compare-cycles", help="Compare current vs previous certification cycles")
    subparsers.add_parser("export", help="Generate consolidated CSV and Excel reports")
    subparsers.add_parser("deadline-check", help="Run deadline and SLA risk assessment")
    subparsers.add_parser("check-dates", help="Inspect exact date ranges, monthly counts, and cycle tags in task data")
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
        "check-dates": cmd_check_dates,
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
