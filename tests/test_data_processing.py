import pytest
import pandas as pd
from datetime import datetime
from src.data_processing.normalizer import DataNormalizer
from src.data_processing.validator import DataValidator
from src.data_processing.relationships import RelationshipResolver
from src.data_processing.quality_checks import QualityChecker

def test_normalization():
    norm = DataNormalizer(field_mapping={'raw_state': 'state'}, tz_config='UTC')
    df = pd.DataFrame({
        'raw_state': [' Open ', ' Closed Complete '],
        'date_col': ['2026-10-01 12:00:00', '2026-10-05 08:30:00']
    })
    res = norm.normalize(df, date_cols=['date_col'], string_cols=['state'])
    assert 'state' in res.columns
    assert res['state'].iloc[0] == 'Open'
    assert pd.api.types.is_datetime64_any_dtype(res['date_col'])

def test_duplicate_and_sequence_validation():
    val = DataValidator(config={'exclude_statuses': ['Cancelled'], 'status_col': 'state'})
    df = pd.DataFrame({
        'sys_id': ['id1', 'id2', 'id1', 'id3'],
        'state': ['Open', 'Cancelled', 'Open', 'Closed Complete'],
        'created_at': ['2026-10-01', '2026-10-02', '2026-10-01', '2026-10-05'],
        'closed_at': ['2026-10-05', None, '2026-10-05', '2026-10-02'] # id3 has impossible sequence (closed < created)
    })
    valid, invalid, excluded = val.validate(
        df,
        id_col='sys_id',
        required_fields=['sys_id', 'state'],
        date_seq_cols=[('created_at', 'closed_at')]
    )
    # id1 duplicated -> invalid
    # id3 bad sequence -> invalid
    assert len(invalid) == 3 # 2 duplicates + 1 bad sequence
    assert len(excluded) == 1 # 1 cancelled
    assert len(valid) == 0

def test_relationship_resolution():
    resolver = RelationshipResolver()
    tasks_df = pd.DataFrame({'sys_id': ['T1', 'T2', 'T3']})
    disc_df = pd.DataFrame({
        'disc_id': ['D1', 'D2', 'D3'],
        'u_certification_task': ['T1', 'T1', 'UNKNOWN_TASK'] # D3 is orphaned
    })
    tasks_res, disc_res, stats = resolver.resolve(
        tasks_df, disc_df,
        task_id_col='sys_id',
        disc_link_col='u_certification_task'
    )
    assert stats['orphaned_discrepancies'] == 1
    assert stats['total_linked'] == 2
    assert tasks_res[tasks_res['sys_id'] == 'T1']['discrepancy_count'].iloc[0] == 2
    assert tasks_res[tasks_res['sys_id'] == 'T2']['discrepancy_count'].iloc[0] == 0

def test_quality_checks():
    checker = QualityChecker(config={'task_required_fields': ['sys_id', 'state']})
    tasks = pd.DataFrame({'sys_id': ['1', '2'], 'state': ['Open', None]})
    disc = pd.DataFrame()
    report = checker.run_checks(tasks, disc)
    assert report['task_data_completeness']['overall_score'] == 75.0 # sys_id 100%, state 50%
