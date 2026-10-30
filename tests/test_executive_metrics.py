import pytest
import pandas as pd
from src.dashboard.app import count_resolved_discrepancies

def test_count_resolved_discrepancies_state_closed_complete():
    df_disc = pd.DataFrame({
        'sys_id': ['d1', 'd2', 'd3'],
        'state': ['Closed Complete', 'Open', 'closed complete'],
        'u_certification_task': ['t1', 't2', 't3']
    })
    df_tasks = pd.DataFrame({
        'sys_id': ['t1', 't2', 't3'],
        'state': ['Open', 'Open', 'Open']
    })
    resolved, total = count_resolved_discrepancies(df_disc, df_tasks)
    assert total == 3
    assert resolved == 2  # d1 and d3 have state Closed Complete

def test_count_resolved_discrepancies_linked_task_closed_complete():
    # Discrepancies say Open, but tasks are Closed Complete
    df_disc = pd.DataFrame({
        'sys_id': ['d1', 'd2', 'd3'],
        'u_status': ['Open', 'Open', 'Open'],
        'u_certification_task': ['t1', 't2', 't3']
    })
    df_tasks = pd.DataFrame({
        'sys_id': ['t1', 't2', 't3'],
        'state': ['Closed Complete', 'Work in Progress', 'Closed Complete']
    })
    resolved, total = count_resolved_discrepancies(df_disc, df_tasks)
    assert total == 3
    assert resolved == 2  # d1 and d3 are linked to tasks marked Closed Complete

def test_count_resolved_discrepancies_combined_state_and_task():
    df_disc = pd.DataFrame({
        'sys_id': ['d1', 'd2', 'd3', 'd4'],
        'state': ['Resolved', 'Open', 'Open', 'Closed Complete'],
        'u_certification_task': ['t1', 't2', 't3', 't4']
    })
    df_tasks = pd.DataFrame({
        'sys_id': ['t1', 't2', 't3', 't4'],
        'state': ['Open', 'Closed Complete', 'Open', 'Open']
    })
    resolved, total = count_resolved_discrepancies(df_disc, df_tasks)
    assert total == 4
    # d1 is Resolved, d2 task is Closed Complete, d4 is Closed Complete
    assert resolved == 3

def test_count_resolved_discrepancies_empty_or_none():
    assert count_resolved_discrepancies(None) == (0, 0)
    assert count_resolved_discrepancies(pd.DataFrame()) == (0, 0)
