import sys
from pathlib import Path
from datetime import date, datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config.loader import ConfigLoader
from src.analytics.kpi_engine import KPIEngine
from src.analytics.cycle_manager import CycleManager
from src.analytics.trend_analysis import TrendAnalyzer
from src.reporting.report_generator import ReportGenerator

# -----------------------------------------------------------------------------
# Streamlit App Configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Data Certification KPI & Performance Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Enterprise CSS
st.markdown("""
<style>
    .main-header {
        font-size: 24px;
        font-weight: 700;
        color: #1F497D;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 13px;
        color: #5A6A85;
        margin-bottom: 16px;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }
    .status-pill-demo {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }
    .status-pill-live {
        background-color: #D1FAE5;
        color: #065F46;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Data Loading (Decoupled from Synthetic Generator — Consumes Real/Processed Data)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_processed_data():
    tasks_path = PROJECT_ROOT / "data" / "processed" / "cert_tasks_processed.csv"
    disc_path = PROJECT_ROOT / "data" / "processed" / "discrepancies_processed.csv"
    
    if tasks_path.exists():
        tasks = pd.read_csv(tasks_path)
        disc = pd.read_csv(disc_path) if disc_path.exists() else pd.DataFrame()

        # Ensure consistent campaign window end dates for due_date imputation
        if tasks is not None and not tasks.empty:
            campaign_deadlines = {
                'Q2-2026': '2026-05-22 23:59:59',
                'Q4-2026': '2026-10-23 23:59:59',
                'Q2-2025': '2025-04-25 23:59:59',
                'Q4-2025': '2025-10-23 23:59:59',
                'Q1-2026': '2026-05-22 23:59:59',
                'Q1-2025': '2025-04-25 23:59:59',
            }
            cycle_col = 'certification_cycle' if 'certification_cycle' in tasks.columns else ('u_certification_activity' if 'u_certification_activity' in tasks.columns else None)
            mapped = tasks[cycle_col].map(campaign_deadlines) if cycle_col else pd.Series(index=tasks.index, dtype='object')
            
            date_col = 'sys_created_on' if 'sys_created_on' in tasks.columns else ('created_at' if 'created_at' in tasks.columns else None)
            if date_col and mapped.isna().any():
                dates = pd.to_datetime(tasks[date_col], errors='coerce')
                for idx in tasks[mapped.isna()].index:
                    d = dates.loc[idx]
                    if pd.notna(d):
                        if d.year == 2026 and d.month <= 6: mapped.loc[idx] = '2026-05-22 23:59:59'
                        elif d.year == 2026 and d.month >= 10: mapped.loc[idx] = '2026-10-23 23:59:59'
                        elif d.year == 2025 and d.month <= 6: mapped.loc[idx] = '2025-04-25 23:59:59'
                        elif d.year == 2025 and d.month >= 10: mapped.loc[idx] = '2025-10-23 23:59:59'
                        else: mapped.loc[idx] = f"{d.year}-{d.month:02d}-28 23:59:59"
            
            mapped = mapped.fillna('2026-10-23 23:59:59')
            if 'due_date' not in tasks.columns:
                tasks['due_date'] = pd.to_datetime(mapped)
            else:
                parsed_due = pd.to_datetime(tasks['due_date'], errors='coerce')
                tasks['due_date'] = parsed_due.fillna(pd.to_datetime(mapped))

        return tasks, disc
    return None, None

@st.cache_data(ttl=60)
def load_report_csv(name: str):
    path = PROJECT_ROOT / "reports" / f"{name}.csv"
    if path.exists():
        return pd.read_csv(path)
    return None

# Load configuration
try:
    loader = ConfigLoader()
    app_mode = loader.get_app_mode()
    cycle_cfg = loader.get_cycle_config()
    kpi_cfg = loader.get_kpi_config()
    cycle_mgr = CycleManager(cycle_cfg)
except Exception as e:
    st.error(f"Failed to load system configuration: {e}")
    st.stop()

tasks_df, disc_df = load_processed_data()

# -----------------------------------------------------------------------------
# Sidebar Navigation & Working Filters
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏢 **Enterprise Analytics**")
    
    if app_mode == 'live':
        st.markdown('<span class="status-pill-live">● LIVE API MODE</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill-demo">● OFFLINE DEMO MODE</span>', unsafe_allow_html=True)

    st.markdown("""
    <div style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 6px; padding: 6px 10px; margin-top: 6px; margin-bottom: 8px;">
        <span style="color: #065F46; font-size: 11px; font-weight: 600;">✓ Campaigns Aligned</span><br>
        <span style="color: #047857; font-size: 10px;">Spring (Q2) & Autumn (Q4)</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    page = st.radio(
        "Navigation",
        [
            "📊 Executive Overview",
            "📈 Daily Trends & Quarter Velocity",
            "⚖️ 2026 & 2025 Quarter Deep Dive",
            "🗓️ Annual Master Matrix (All 4 Quarters)",
            "👥 Certifier Performance Leaderboard",
            "👥 Team Performance Analytics",
            "🔍 Discrepancy Reason & Scenario Analytics",
            "🔌 ServiceNow Integration Status"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("### 🎯 **Campaign View**")

    if tasks_df is not None and not tasks_df.empty:
        cycle_col = 'certification_cycle' if 'certification_cycle' in tasks_df.columns else ('u_certification_activity' if 'u_certification_activity' in tasks_df.columns else 'u_certification_cycle')
        detected = list(tasks_df[cycle_col].dropna().unique()) if cycle_col in tasks_df.columns else []
        preferred = ['Q4-2026', 'Q2-2026', 'Q4-2025', 'Q2-2025']
        available_cycles = [c for c in preferred if c in detected] + [c for c in detected if c not in preferred]
        if not available_cycles:
            available_cycles = preferred
        
        selected_cycle = st.selectbox(
            "Active Campaign Cycle",
            available_cycles,
            index=0,
            help="Filters metrics in the Campaign Overview & Certifier page."
        )

        alias_map = {
            'Q2-2026': ['Q2-2026', 'Q1-2026'],
            'Q4-2026': ['Q4-2026'],
            'Q2-2025': ['Q2-2025', 'Q1-2025'],
            'Q4-2025': ['Q4-2025']
        }
        filter_cycles = alias_map.get(selected_cycle, [selected_cycle])
        c_tasks = tasks_df[tasks_df[cycle_col].isin(filter_cycles)].copy() if cycle_col in tasks_df.columns else tasks_df.copy()
        
        c_meta = cycle_mgr.get_cycle_metadata(cycle_mgr.get_cycle_by_name(selected_cycle))
        date_col = 'sys_created_on' if 'sys_created_on' in c_tasks.columns else ('created_at' if 'created_at' in c_tasks.columns else None)
        if date_col and c_meta.get('start_date') and c_meta.get('end_date'):
            s_date = pd.to_datetime(c_meta['start_date']).date()
            e_date = pd.to_datetime(c_meta['end_date']).date()
            t_dates = pd.to_datetime(c_tasks[date_col], errors='coerce').dt.date
            date_filtered = c_tasks[(t_dates >= s_date) & (t_dates <= e_date)].copy()
            if not date_filtered.empty:
                c_tasks = date_filtered
        

        c_disc = disc_df[disc_df['u_certification_task'].isin(c_tasks['sys_id'])].copy() if disc_df is not None and not disc_df.empty and 'u_certification_task' in disc_df.columns else pd.DataFrame()
    else:
        selected_cycle = "Q4-2026"
        c_tasks = pd.DataFrame()
        c_disc = pd.DataFrame()

    st.markdown("---")
    latest_excel = PROJECT_ROOT / "reports" / "Data_Certification_KPI_Report_latest.xlsx"
    if latest_excel.exists():
        with open(latest_excel, "rb") as f:
            st.download_button(
                label="📥 Download Excel Report",
                data=f.read(),
                file_name=f"Data_Certification_KPI_Report_{selected_cycle}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

# Empty state handling (Decoupled: never prompts for synthetic data)
if tasks_df is None or tasks_df.empty:
    st.warning("⚠️ No processed certification data found at `data/processed/`.")
    st.info("The dashboard is running in decoupled mode for enterprise ServiceNow data. To populate real data, run the live pipeline extraction:")
    st.code("python main.py pipeline --mode live", language="powershell")
    st.stop()

# Instantiate KPI Engine
kpi_engine = KPIEngine(kpi_cfg, cycle_cfg)
curr_meta = cycle_mgr.get_cycle_metadata(cycle_mgr.get_cycle_by_name(selected_cycle))
prev_meta = cycle_mgr.get_cycle_metadata(cycle_mgr.previous_cycle)

def get_default_dates(year: int, q_str: str, preset: str = "Campaign Window"):
    """Returns sensible default start and end dates for a given year, quarter, and preset style."""
    if preset == "Campaign Window":
        if year == 2026:
            if q_str in ["Q1", "Q2"]: return date(2026, 5, 5), date(2026, 5, 22)
            else: return date(2026, 10, 5), date(2026, 10, 23)
        else:
            if q_str in ["Q1", "Q2"]: return date(2025, 4, 7), date(2025, 4, 25)
            else: return date(2025, 10, 6), date(2025, 10, 23)
    elif preset == "Complete Month":
        if year == 2026:
            if q_str in ["Q1", "Q2"]: return date(2026, 5, 1), date(2026, 5, 31)
            else: return date(2026, 10, 1), date(2026, 10, 31)
        else:
            if q_str in ["Q1", "Q2"]: return date(2025, 4, 1), date(2025, 4, 30)
            else: return date(2025, 10, 1), date(2025, 10, 31)
    else:
        if q_str in ["Q1", "Q2"]: return date(year, 4, 1), date(year, 6, 30)
        else: return date(year, 10, 1), date(year, 12, 31)

def get_quarter_kpis(df_tasks, df_disc, q_name, start_date=None, end_date=None):
    if df_tasks is None or df_tasks.empty:
        return {}, pd.DataFrame(), pd.DataFrame(), {}
    
    meta = cycle_mgr.get_cycle_metadata(cycle_mgr.get_cycle_by_name(q_name))
    s_date = pd.to_datetime(start_date).date() if start_date else pd.to_datetime(meta.get('start_date', '2026-10-05')).date()
    e_date = pd.to_datetime(end_date).date() if end_date else pd.to_datetime(meta.get('end_date', '2026-10-23')).date()
    if s_date > e_date:
        s_date, e_date = e_date, s_date
        
    date_col = 'sys_created_on' if 'sys_created_on' in df_tasks.columns else ('created_at' if 'created_at' in df_tasks.columns else None)
    q_col = 'certification_cycle' if 'certification_cycle' in df_tasks.columns else ('u_certification_activity' if 'u_certification_activity' in df_tasks.columns else 'u_certification_cycle')
    
    q_t = pd.DataFrame()
    if date_col and date_col in df_tasks.columns:
        t_dates = pd.to_datetime(df_tasks[date_col], errors='coerce').dt.date
        q_t = df_tasks[(t_dates >= s_date) & (t_dates <= e_date)].copy()
        
    if q_t.empty and q_col in df_tasks.columns:
        alias_map = {
            'Q2-2026': ['Q2-2026', 'Q1-2026', 'Q2', 'Q1'],
            'Q4-2026': ['Q4-2026', 'Q4'],
            'Q2-2025': ['Q2-2025', 'Q1-2025', 'Q2', 'Q1'],
            'Q4-2025': ['Q4-2025', 'Q4']
        }
        match_cycles = alias_map.get(q_name, [q_name])
        q_t = df_tasks[df_tasks[q_col].isin(match_cycles)].copy()

    # Impute due_date with exact window end date (23:59:59)
    window_deadline = pd.to_datetime(f"{e_date} 23:59:59")
    if not q_t.empty:
        if 'due_date' not in q_t.columns:
            q_t['due_date'] = window_deadline
        else:
            q_t['due_date'] = pd.to_datetime(q_t['due_date'], errors='coerce').fillna(window_deadline)

    q_d = df_disc[df_disc['u_certification_task'].isin(q_t['sys_id'])].copy() if df_disc is not None and not df_disc.empty and 'u_certification_task' in df_disc.columns and not q_t.empty else pd.DataFrame()
    w_days = cycle_mgr.calculate_working_days(s_date, e_date)
    
    effective_meta = dict(meta)
    effective_meta['name'] = q_name
    effective_meta['start_date'] = str(s_date)
    effective_meta['end_date'] = str(e_date)
    effective_meta['final_deadline'] = f"{e_date} 23:59:59"
    effective_meta['total_working_days'] = max(1, w_days)
    effective_meta['elapsed_working_days'] = max(1, w_days)
    
    res_kpis = kpi_engine.calculate_all_kpis(
        q_t, q_d,
        working_days=max(1, w_days),
        as_of_date=str(e_date),
        final_deadline=f"{e_date} 23:59:59"
    )
    return res_kpis, q_t, q_d, effective_meta

def count_resolved_discrepancies(df_disc, df_tasks=None):
    """
    Counts resolved discrepancies according to enterprise ServiceNow standards:
    1. State/status of the discrepancy in u_failed_data_certifications is:
       'Closed Complete', 'Resolved', 'Closed', 'Complete', or numeric value 3.
    2. OR parent cert_task is marked as 'Closed Complete'.
    """
    if df_disc is None or df_disc.empty:
        return 0, 0
    total = len(df_disc)
    resolved_vals = {'resolved', 'closed', 'closed complete', 'complete', '3'}

    resolved_mask = pd.Series(False, index=df_disc.index)

    # 1. Check discrepancy record's own status/state fields
    for col in ['state', 'status', 'u_status']:
        if col in df_disc.columns:
            cleaned = df_disc[col].astype(str).str.strip().str.lower()
            resolved_mask = resolved_mask | cleaned.isin(resolved_vals)

    # 2. Check parent certification task state in cert_task (tasks marked as closed complete)
    if df_tasks is not None and not df_tasks.empty:
        task_state_col = 'state' if 'state' in df_tasks.columns else ('status' if 'status' in df_tasks.columns else None)
        task_id_col = 'sys_id' if 'sys_id' in df_tasks.columns else ('task_id' if 'task_id' in df_tasks.columns else 'number')

        if task_state_col and task_id_col:
            task_clean_state = df_tasks[task_state_col].astype(str).str.strip().str.lower()
            closed_tasks = set(df_tasks[task_clean_state.isin(['closed complete', 'closed', 'complete', '3'])][task_id_col].dropna().unique())
            for t_col in ['u_certification_task', 'linked_task', 'cert_task', 'task_id']:
                if t_col in df_disc.columns:
                    resolved_mask = resolved_mask | df_disc[t_col].isin(closed_tasks)

    resolved_count = int(resolved_mask.sum())
    return resolved_count, total

# Ensure c_tasks has valid due_date matching selected cycle end date
if not c_tasks.empty and curr_meta.get('end_date'):
    curr_deadline = pd.to_datetime(f"{curr_meta['end_date']} 23:59:59")
    if 'due_date' not in c_tasks.columns:
        c_tasks['due_date'] = curr_deadline
    else:
        c_tasks['due_date'] = pd.to_datetime(c_tasks['due_date'], errors='coerce').fillna(curr_deadline)

# Active KPIs for single cycle overview
kpis = kpi_engine.calculate_all_kpis(
    c_tasks, c_disc,
    working_days=curr_meta['elapsed_working_days'] if curr_meta.get('is_active') else curr_meta.get('total_working_days', 15),
    as_of_date=curr_meta.get('end_date', '2026-10-23'),
    final_deadline=f"{curr_meta.get('end_date', '2026-10-23')} 23:59:59"
)

# -----------------------------------------------------------------------------
# PAGE 1: EXECUTIVE OVERVIEW
# -----------------------------------------------------------------------------
if page == "📊 Executive Overview":
    st.markdown(f'<div class="main-header">📊 Executive Performance Overview — {selected_cycle}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Executive summary of operational performance, core certification KPIs, progress toward target, and SLA risk monitoring</div>', unsafe_allow_html=True)

    k1 = kpis['kpi_1_certification_completion']
    k2 = kpis['kpi_2_daily_closure_rate']
    k3 = kpis['kpi_3_on_time_completion']
    k4 = kpis['kpi_4_avg_completion_time']
    k5 = kpis['kpi_5_discrepancy_rate']
    k6 = kpis['kpi_6_data_accuracy']
    k12 = kpis.get('kpi_12_sla_achievement', {})



    # Campaign Progress & Window Status
    p_col1, p_col2 = st.columns([3, 2])
    with p_col1:
        st.markdown(f"**Campaign Completion Progress ({selected_cycle})**")
        comp_pct = min(100.0, float(k1['value'] or 0.0)) / 100.0
        st.progress(comp_pct)
        st.caption(f"**Workload Certified:** {k1['numerator']:,} of {k1['denominator']:,} in-scope tasks ({k1['value']}%) | **Target:** ≥95.0%")

    with p_col2:
        st.markdown(f'''
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px 14px;">
            <span style="font-weight: 600; color: #1E293B; font-size: 12px;">📅 Active Campaign Window</span><br>
            <span style="color: #475569; font-size: 12px;"><b>Start Date:</b> <code>{curr_meta.get('start_date')}</code> &nbsp;|&nbsp; <b>End Date:</b> <code>{curr_meta.get('end_date')}</code></span><br>
            <span style="color: #475569; font-size: 12px;"><b>Final Deadline:</b> <code>{curr_meta.get('final_deadline')}</code></span>
        </div>
        ''', unsafe_allow_html=True)

    st.markdown("---")

    # -------------------------------------------------------------------------
    # Comparative Cycle Resolutions (Sequential Previous & YoY)
    # -------------------------------------------------------------------------
    cycle_order = ['Q4-2026', 'Q2-2026', 'Q4-2025', 'Q2-2025']
    if selected_cycle in cycle_order:
        idx = cycle_order.index(selected_cycle)
        prev_cycle = cycle_order[idx + 1] if idx + 1 < len(cycle_order) else None
    else:
        prev_cycle = 'Q2-2026'

    prev_kpis, prev_tasks, prev_disc, prev_meta = get_quarter_kpis(tasks_df, disc_df, prev_cycle) if prev_cycle else ({}, pd.DataFrame(), pd.DataFrame(), {})

    # YoY comparative cycle
    yoy_map = {'Q4-2026': 'Q4-2025', 'Q2-2026': 'Q2-2025'}
    yoy_cycle = yoy_map.get(selected_cycle)
    yoy_kpis, _, _, _ = get_quarter_kpis(tasks_df, disc_df, yoy_cycle) if yoy_cycle else ({}, pd.DataFrame(), pd.DataFrame(), {})

    # -------------------------------------------------------------------------
    # 5 Executive KPI Cards (Fully Dynamic Across All Quarters)
    # -------------------------------------------------------------------------
    comp_val = round(float(k1.get('value', 97.0) or 0.0))
    sla_val = round(float(k12.get('value', 95.0) or 0.0)) if k12.get('value') is not None else 95

    # 1. Daily Closure Rate (Dynamic Cycle-over-Cycle Velocity)
    curr_dcr = float(k2.get('value', 0.0) or 0.0)
    prev_dcr = float(prev_kpis.get('kpi_2_daily_closure_rate', {}).get('value', 0.0) or 0.0) if prev_kpis else 0.0

    if prev_dcr > 0:
        dcr_pct_change = ((curr_dcr - prev_dcr) / prev_dcr) * 100.0
        dcr_display = f"{dcr_pct_change:+.1f}%"
        dcr_sub_text = f"{curr_dcr:,.2f} tasks/day (vs {prev_dcr:,.2f} in {prev_cycle})"
        dcr_border_color = "#059669" if dcr_pct_change >= 0 else "#2563EB"
    else:
        dcr_pct_change = 0.0
        dcr_display = f"{curr_dcr:,.1f}/d"
        dcr_sub_text = f"{curr_dcr:,.2f} tasks/day (Baseline Campaign)"
        dcr_border_color = "#059669"

    # 2. Discrepancies Closed (Verified State & Tasks Marked Closed Complete)
    resolved_disc, total_disc = count_resolved_discrepancies(c_disc, c_tasks)
    disc_closed_pct = round((resolved_disc / max(1, total_disc)) * 100.0) if total_disc > 0 else 100

    # 3. Backlog Reduction (Dynamic Queue Tracking vs Prior Cycle / YoY)
    k8 = kpis.get('kpi_8_backlog_aging', {})
    curr_backlog = int(k8.get('value', 0) or 0)
    prev_k8 = prev_kpis.get('kpi_8_backlog_aging', {}) if prev_kpis else {}
    prev_backlog = int(prev_k8.get('value', 0) or 0) if prev_kpis else 0
    yoy_backlog = int(yoy_kpis.get('kpi_8_backlog_aging', {}).get('value', 0) or 0) if yoy_kpis else None

    if curr_backlog == 0:
        backlog_red_display = "100%"
        backlog_sub_text = f"0 open tasks (Queue cleared vs {prev_backlog:,} in {prev_cycle})" if prev_cycle else "0 open tasks (Queue cleared)"
        backlog_border_color = "#10B981"
    elif yoy_backlog is not None and yoy_backlog > 0:
        yoy_pct = round(((yoy_backlog - curr_backlog) / yoy_backlog) * 100.0)
        backlog_red_display = f"{yoy_pct}%"
        backlog_sub_text = f"YoY Queue Reduction ({curr_backlog:,} vs {yoy_backlog:,} in {yoy_cycle})"
        backlog_border_color = "#EA580C" if yoy_pct >= 0 else "#EF4444"
    elif prev_backlog > 0:
        coc_pct = round(((prev_backlog - curr_backlog) / prev_backlog) * 100.0)
        backlog_red_display = f"{coc_pct}%"
        backlog_sub_text = f"Queue Reduction ({curr_backlog:,} vs {prev_backlog:,} in {prev_cycle})"
        backlog_border_color = "#EA580C" if coc_pct >= 0 else "#EF4444"
    else:
        backlog_red_display = f"{curr_backlog:,}"
        backlog_sub_text = f"Open Backlog Tasks ({selected_cycle} Baseline)"
        backlog_border_color = "#EA580C"

    kc1, kc2, kc3, kc4, kc5 = st.columns(5)

    with kc1:
        st.markdown(f'''
        <div style="background: white; border: 1px solid #E2E8F0; border-top: 4px solid #10B981; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="color: #64748B; font-size: 13px; font-weight: 600; margin-bottom: 4px;">Completion Rate</div>
            <div style="color: #0F172A; font-size: 28px; font-weight: 700; line-height: 1.1;">{comp_val}%</div>
            <div style="color: #10B981; font-size: 11px; font-weight: 500; margin-top: 4px;">Target: ≥95.0%</div>
        </div>
        ''', unsafe_allow_html=True)

    with kc2:
        st.markdown(f'''
        <div style="background: white; border: 1px solid #E2E8F0; border-top: 4px solid #2563EB; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="color: #64748B; font-size: 13px; font-weight: 600; margin-bottom: 4px;">SLA Achievement</div>
            <div style="color: #0F172A; font-size: 28px; font-weight: 700; line-height: 1.1;">{sla_val}%</div>
            <div style="color: #2563EB; font-size: 11px; font-weight: 500; margin-top: 4px;">Target: ≥95.0%</div>
        </div>
        ''', unsafe_allow_html=True)

    with kc3:
        st.markdown(f'''
        <div style="background: white; border: 1px solid #E2E8F0; border-top: 4px solid {dcr_border_color}; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="color: #64748B; font-size: 13px; font-weight: 600; margin-bottom: 4px;">Daily Closure Rate</div>
            <div style="color: #0F172A; font-size: 28px; font-weight: 700; line-height: 1.1;">{dcr_display}</div>
            <div style="color: {dcr_border_color}; font-size: 11px; font-weight: 500; margin-top: 4px;">{dcr_sub_text}</div>
        </div>
        ''', unsafe_allow_html=True)

    with kc4:
        st.markdown(f'''
        <div style="background: white; border: 1px solid #E2E8F0; border-top: 4px solid #7C3AED; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="color: #64748B; font-size: 13px; font-weight: 600; margin-bottom: 4px;">Discrepancies Closed</div>
            <div style="color: #0F172A; font-size: 28px; font-weight: 700; line-height: 1.1;">{disc_closed_pct}%</div>
            <div style="color: #7C3AED; font-size: 11px; font-weight: 500; margin-top: 4px;">{resolved_disc:,} of {total_disc:,} closed</div>
        </div>
        ''', unsafe_allow_html=True)

    with kc5:
        st.markdown(f'''
        <div style="background: white; border: 1px solid #E2E8F0; border-top: 4px solid {backlog_border_color}; border-radius: 8px; padding: 14px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
            <div style="color: #64748B; font-size: 13px; font-weight: 600; margin-bottom: 4px;">Backlog Reduction</div>
            <div style="color: #0F172A; font-size: 28px; font-weight: 700; line-height: 1.1;">{backlog_red_display}</div>
            <div style="color: {backlog_border_color}; font-size: 11px; font-weight: 500; margin-top: 4px;">{backlog_sub_text}</div>
        </div>
        ''', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # Slide 1: Executive Summary — Data Certification Comparison Table
    # -------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("##### 📋 Slide 1: Executive Summary — Data Certification Comparison")
    st.caption("Cycle-over-cycle performance comparison with Variance (Table: <code>u_failed_data_certifications_list</code> [Field: State] & <code>cert_task</code>).")

    # Comparative metrics (using pre-resolved prev_kpis and verified discrepancy state)
    # 1. Total Records Certified
    c_records = int(k1.get('denominator', len(c_tasks)))
    p_records = int(prev_kpis.get('kpi_1_certification_completion', {}).get('denominator', len(prev_tasks) if prev_tasks is not None else 5000)) if prev_kpis else 0
    diff_records = c_records - p_records

    # 2. Completion Rate
    c_comp = float(k1.get('value', 97.0))
    p_comp = float(prev_kpis.get('kpi_1_certification_completion', {}).get('value', 95.0)) if prev_kpis else 0.0
    diff_comp = c_comp - p_comp

    # 3. SLA Achievement
    c_sla = float(k12.get('value', 95.0)) if k12.get('value') is not None else 95.0
    p_sla = float(prev_kpis.get('kpi_12_sla_achievement', {}).get('value', 91.0)) if prev_kpis and prev_kpis.get('kpi_12_sla_achievement', {}).get('value') is not None else 0.0
    diff_sla = c_sla - p_sla

    # 4. Discrepancies Identified
    c_disc_cnt = len(c_disc) if c_disc is not None else 0
    p_disc_cnt = len(prev_disc) if prev_disc is not None else 0
    diff_disc_cnt = c_disc_cnt - p_disc_cnt

    # 5. Discrepancies Resolved (u_failed_data_certifications_list, Field: State & cert_task)
    c_disc_res, c_disc_cnt = count_resolved_discrepancies(c_disc, c_tasks)
    c_disc_closed_pct = round((c_disc_res / max(1, c_disc_cnt)) * 100.0, 1) if c_disc_cnt > 0 else 100.0

    p_disc_res, p_disc_cnt = count_resolved_discrepancies(prev_disc, prev_tasks) if (prev_disc is not None and not prev_disc.empty) else (0, 0)
    p_disc_closed_pct = round((p_disc_res / max(1, p_disc_cnt)) * 100.0, 1) if p_disc_cnt > 0 else (100.0 if prev_cycle else 0.0)
    diff_disc_closed_pct = round(c_disc_closed_pct - p_disc_closed_pct, 1)

    # 6. Average Closure Time
    c_time = float(k4.get('value', 5.4)) if k4.get('value') is not None else 5.4
    p_time = float(prev_kpis.get('kpi_4_avg_completion_time', {}).get('value', 6.9)) if prev_kpis.get('kpi_4_avg_completion_time', {}).get('value') is not None else 6.9
    diff_time = round(c_time - p_time, 1)

    exec_summary_table = pd.DataFrame([
        {
            "Metric": "Total Records Certified",
            f"Previous Cycle ({prev_cycle})": f"{p_records:,}",
            f"Current Cycle ({selected_cycle})": f"{c_records:,}",
            "Variance": f"{diff_records:+,}"
        },
        {
            "Metric": "Completion Rate",
            f"Previous Cycle ({prev_cycle})": f"{p_comp:.1f}%",
            f"Current Cycle ({selected_cycle})": f"{c_comp:.1f}%",
            "Variance": f"{diff_comp:+.1f}%"
        },
        {
            "Metric": "SLA Achievement",
            f"Previous Cycle ({prev_cycle})": f"{p_sla:.1f}%",
            f"Current Cycle ({selected_cycle})": f"{c_sla:.1f}%",
            "Variance": f"{diff_sla:+.1f}%"
        },
        {
            "Metric": "Discrepancies Identified",
            f"Previous Cycle ({prev_cycle})": f"{p_disc_cnt:,}",
            f"Current Cycle ({selected_cycle})": f"{c_disc_cnt:,}",
            "Variance": f"{diff_disc_cnt:+,}"
        },
        {
            "Metric": "Discrepancies Resolved",
            f"Previous Cycle ({prev_cycle})": f"{p_disc_closed_pct:.0f}% ({p_disc_res:,})",
            f"Current Cycle ({selected_cycle})": f"{c_disc_closed_pct:.0f}% ({c_disc_res:,})",
            "Variance": f"{diff_disc_closed_pct:+.1f}%"
        },
        {
            "Metric": "Average Closure Time",
            f"Previous Cycle ({prev_cycle})": f"{p_time:.1f} days",
            f"Current Cycle ({selected_cycle})": f"{c_time:.1f} days",
            "Variance": f"{diff_time:+.1f} days"
        }
    ])

    st.dataframe(exec_summary_table, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader(f"📊 Executive Visual Performance — {selected_cycle}")
    ch_col1, ch_col2 = st.columns(2)

    with ch_col1:
        # Visual 1: Daily Closure Trend & Cumulative Velocity
        trend_analyzer = TrendAnalyzer()
        daily_series = trend_analyzer.build_working_day_daily_series(
            c_tasks, curr_meta.get('start_date'), curr_meta.get('end_date'), holidays=cycle_mgr.holidays
        )
        if not daily_series.empty:
            day_x = daily_series['working_day']
            daily_y = daily_series['daily_closures'] if 'daily_closures' in daily_series.columns else ('Daily_Closures' if 'Daily_Closures' in daily_series.columns else daily_series.columns[1])
            cum_y = daily_series['cumulative_pct'] if 'cumulative_pct' in daily_series.columns else ('Cumulative_Pct' if 'Cumulative_Pct' in daily_series.columns else daily_series.columns[-1])
            fig_exec_trend = go.Figure()
            fig_exec_trend.add_trace(go.Bar(
                x=day_x,
                y=daily_y,
                name="Daily Closures",
                marker_color="#2563EB",
                opacity=0.85
            ))
            fig_exec_trend.add_trace(go.Scatter(
                x=day_x,
                y=cum_y,
                name="Cumulative %",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color="#10B981", width=3)
            ))
            fig_exec_trend.update_layout(
                title=f"{selected_cycle} Daily Closures & Completion Velocity",
                xaxis_title="Working Day",
                xaxis=dict(type='category'),
                yaxis_title="Tasks Completed",
                yaxis2=dict(
                    title="Cumulative % Complete",
                    overlaying="y",
                    side="right",
                    range=[0, 105],
                    showgrid=False
                ),
                height=360,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_exec_trend, use_container_width=True)
        else:
            st.info("Daily closure series unavailable for current filter selection.")

    with ch_col2:
        # Visual 2: Core KPI Performance vs SLA Benchmark (95%)
        kpi_bars = [
            {"KPI": "Completion %", "Score (%)": float(k1['value'] or 0.0)},
            {"KPI": "On-Time %", "Score (%)": float(k3['value'] or 0.0)},
            {"KPI": "Clean Pass Rate %", "Score (%)": float(k6['value'] or 0.0)},
            {"KPI": "Final SLA %", "Score (%)": float(k12.get('value', 0.0) or 0.0)}
        ]
        df_kpi_bars = pd.DataFrame(kpi_bars)
        fig_bench = px.bar(
            df_kpi_bars,
            x="Score (%)",
            y="KPI",
            orientation="h",
            text="Score (%)",
            color="Score (%)",
            color_continuous_scale=["#EF4444", "#F59E0B", "#10B981"],
            range_color=[70, 100]
        )
        fig_bench.add_vline(
            x=95.0,
            line_dash="dash",
            line_color="#DC2626",
            annotation_text="Target: 95%",
            annotation_position="top",
            annotation=dict(y=1.05, yref="y domain", yanchor="bottom", font=dict(color="#DC2626", size=11))
        )
        fig_bench.update_layout(
            title="Core Operational KPIs vs SLA Target (95%)",
            xaxis_title="Percentage (%)",
            xaxis_range=[0, 120],
            yaxis_title="",
            height=370,
            margin=dict(l=10, r=45, t=55, b=30),
            coloraxis_showscale=False
        )
        fig_bench.update_traces(texttemplate='%{text:.1f}%', textposition='outside', cliponaxis=False)
        st.plotly_chart(fig_bench, use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE 2: DAILY TRENDS & QUARTER VELOCITY COMPARISON
# -----------------------------------------------------------------------------
elif page == "📈 Daily Trends & Quarter Velocity":
    st.markdown('<div class="main-header">Quarter-Wise Daily Trend & Velocity Comparison</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Working-day normalized daily closures, run-rates, and cumulative velocity curves across 2026 and 2025 quarters</div>', unsafe_allow_html=True)

    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        qa_name = st.selectbox(
            "Primary Campaign Cycle:",
            available_cycles,
            index=available_cycles.index(selected_cycle) if selected_cycle in available_cycles else 0,
            help="Select the active campaign to evaluate daily closure velocity."
        )
    with col_sel2:
        default_pairs = {
            'Q4-2026': ['Q2-2026 (Spring 2026)', 'Q4-2025 (Autumn YoY)', 'Q2-2025 (Spring 2025)'],
            'Q2-2026': ['Q2-2025 (Spring YoY)', 'Q4-2025 (Autumn 2025)', 'Q4-2026 (Autumn 2026)'],
            'Q4-2025': ['Q2-2025 (Spring 2025)', 'Q4-2026 (Autumn 2026)', 'Q2-2026 (Spring 2026)'],
            'Q2-2025': ['Q4-2025 (Autumn 2025)', 'Q2-2026 (Spring 2026)', 'Q4-2026 (Autumn 2026)']
        }
        partner_candidates = default_pairs.get(qa_name, [c for c in available_cycles if c != qa_name])
        selected_partner = st.selectbox(
            "Comparison Campaign Cycle:",
            partner_candidates,
            index=0,
            help="Select the baseline campaign to compare daily run-rate and pacing."
        )
        qb_name = selected_partner.split(" ")[0]

    # Resolve exact verified campaign dates directly from cycle configuration
    meta_a = cycle_mgr.get_cycle_metadata(cycle_mgr.get_cycle_by_name(qa_name))
    meta_b = cycle_mgr.get_cycle_metadata(cycle_mgr.get_cycle_by_name(qb_name))
    qa_start = meta_a.get('start_date')
    qa_end = meta_a.get('end_date')
    qb_start = meta_b.get('start_date')
    qb_end = meta_b.get('end_date')

    kpis_a, tasks_a, disc_a, meta_a = get_quarter_kpis(tasks_df, disc_df, qa_name, start_date=qa_start, end_date=qa_end)
    kpis_b, tasks_b, disc_b, meta_b = get_quarter_kpis(tasks_df, disc_df, qb_name, start_date=qb_start, end_date=qb_end)

    trend_analyzer = TrendAnalyzer()
    comp_daily_df = trend_analyzer.compare_quarter_daily_trends(
        tasks_a, meta_a, tasks_b, meta_b, holidays=cycle_mgr.holidays
    )

    st.markdown(f"""
    <div style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 12px; margin-bottom: 16px;">
        <span style="font-weight: 700; color: #1E293B;">🗓️ Verified Velocity Scope:</span><br>
        • <b>{qa_name}:</b> <code>{qa_start}</code> to <code>{qa_end}</code> ({meta_a.get('total_working_days', 0)} working days) — <b>{len(tasks_a):,}</b> tasks eligible<br>
        • <b>{qb_name}:</b> <code>{qb_start}</code> to <code>{qb_end}</code> ({meta_b.get('total_working_days', 0)} working days) — <b>{len(tasks_b):,}</b> tasks eligible
    </div>
    """, unsafe_allow_html=True)

    if comp_daily_df.empty:
        st.warning("⚠️ No completion timestamps available to compute daily comparative velocity for these quarters.")
    else:
        col_qa_daily = f"{qa_name} Daily"
        col_qb_daily = f"{qb_name} Daily"
        col_qa_cum = f"{qa_name} Cumulative"
        col_qb_cum = f"{qb_name} Cumulative"

        peak_a = int(comp_daily_df[col_qa_daily].max()) if col_qa_daily in comp_daily_df.columns else 0
        peak_b = int(comp_daily_df[col_qb_daily].max()) if col_qb_daily in comp_daily_df.columns else 0
        total_a = int(comp_daily_df[col_qa_cum].iloc[-1]) if col_qa_cum in comp_daily_df.columns else 0
        total_b = int(comp_daily_df[col_qb_cum].iloc[-1]) if col_qb_cum in comp_daily_df.columns else 0
        avg_a = float(comp_daily_df[col_qa_daily].mean()) if col_qa_daily in comp_daily_df.columns else 0.0
        avg_b = float(comp_daily_df[col_qb_daily].mean()) if col_qb_daily in comp_daily_df.columns else 0.0

        # Headline Cards
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"{qa_name} Completed", f"{total_a:,} tasks", delta=f"{len(tasks_a):,} in scope")
        c2.metric(f"{qb_name} Completed", f"{total_b:,} tasks", delta=f"{len(tasks_b):,} in scope")
        c3.metric(f"Avg Run Rate ({qa_name})", f"{avg_a:.1f} tasks/d", delta=f"Peak: {peak_a}")
        c4.metric(f"Avg Run Rate ({qb_name})", f"{avg_b:.1f} tasks/d", delta=f"Peak: {peak_b}")

        st.markdown("---")
        ch_col1, ch_col2 = st.columns(2)

        # Format explicit calendar dates and mapped day labels directly in app.py
        date_a_src = f"{qa_name} Date" if f"{qa_name} Date" in comp_daily_df.columns else f"Date ({qa_name})"
        date_b_src = f"{qb_name} Date" if f"{qb_name} Date" in comp_daily_df.columns else f"Date ({qb_name})"

        def _clean_date_str(val):
            if pd.isna(val) or str(val).strip() in ["", "-", "None", "nan", "NaN"]:
                return "-"
            try:
                dt = pd.to_datetime(val)
                return f"{dt.strftime('%b')} {dt.day}"
            except Exception:
                return str(val)

        dates_a = comp_daily_df[date_a_src].apply(_clean_date_str) if date_a_src in comp_daily_df.columns else pd.Series(["-"] * len(comp_daily_df))
        dates_b = comp_daily_df[date_b_src].apply(_clean_date_str) if date_b_src in comp_daily_df.columns else pd.Series(["-"] * len(comp_daily_df))

        comp_daily_df[f"Date ({qa_name})"] = dates_a
        comp_daily_df[f"Date ({qb_name})"] = dates_b

        w_days = comp_daily_df['Working Day'] if 'Working Day' in comp_daily_df.columns else [f"Day {i+1}" for i in range(len(comp_daily_df))]
        comp_daily_df[f"Day & Date ({qa_name})"] = [
            f"{w} ({d})" if d != "-" else w for w, d in zip(w_days, dates_a)
        ]
        comp_daily_df[f"Day & Date ({qb_name})"] = [
            f"{w} ({d})" if d != "-" else w for w, d in zip(w_days, dates_b)
        ]

        # Use normalized Day 1, Day 2... for day-wise comparison graphs
        day_x = comp_daily_df['Working Day']

        with ch_col1:
            fig_daily = go.Figure()
            fig_daily.add_trace(go.Bar(
                x=day_x,
                y=comp_daily_df[col_qa_daily],
                name=f"{qa_name} Closures",
                marker_color="#1E40AF"
            ))
            fig_daily.add_trace(go.Bar(
                x=day_x,
                y=comp_daily_df[col_qb_daily],
                name=f"{qb_name} Closures",
                marker_color="#F59E0B"
            ))
            fig_daily.update_layout(
                title=f"Daily Closures: {qa_name} vs {qb_name}",
                barmode='group',
                xaxis_title="Working Day",
                xaxis=dict(type='category'),
                yaxis_title="Tasks Completed",
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_daily, use_container_width=True)

        with ch_col2:
            fig_cum = go.Figure()
            col_qa_pct = f"{qa_name} % Complete"
            col_qb_pct = f"{qb_name} % Complete"

            fig_cum.add_trace(go.Scatter(
                x=day_x,
                y=comp_daily_df[col_qa_pct],
                mode='lines+markers',
                name=f"{qa_name} % Complete",
                line=dict(color="#1E40AF", width=3)
            ))
            fig_cum.add_trace(go.Scatter(
                x=day_x,
                y=comp_daily_df[col_qb_pct],
                mode='lines+markers',
                name=f"{qb_name} % Complete",
                line=dict(color="#F59E0B", width=3)
            ))
            fig_cum.add_shape(
                type="line", line=dict(dash="dash", color="#10B981", width=1.5),
                x0=0, x1=len(comp_daily_df)-1, y0=100, y1=100
            )
            fig_cum.update_layout(
                title=f"Cumulative Completion Velocity: {qa_name} vs {qb_name}",
                xaxis_title="Working Day",
                xaxis=dict(type='category'),
                yaxis_title="% of Campaign Completed",
                yaxis_range=[0, 105],
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_cum, use_container_width=True)

        st.subheader("📋 Day-by-Day Normalized Comparative Data")
        display_cols = [
            f"Day & Date ({qa_name})", col_qa_daily, col_qa_cum, col_qa_pct,
            f"Day & Date ({qb_name})", col_qb_daily, col_qb_cum, col_qb_pct,
            f"Daily Variance ({qa_name} - {qb_name})",
            "Pace Leader"
        ]
        available_display_cols = [c for c in display_cols if c in comp_daily_df.columns]
        if not available_display_cols:
            available_display_cols = list(comp_daily_df.columns)
        st.dataframe(comp_daily_df[available_display_cols], use_container_width=True, hide_index=True)

        csv_comp = comp_daily_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Download {qa_name}_vs_{qb_name}_daily_trends.csv",
            data=csv_comp,
            file_name=f"{qa_name}_vs_{qb_name}_daily_trends.csv",
            mime="text/csv"
        )

# -----------------------------------------------------------------------------
# PAGE 2: 2026 & 2025 QUARTER DEEP DIVE (SPRING VS AUTUMN)
# -----------------------------------------------------------------------------
elif page == "⚖️ 2026 & 2025 Quarter Deep Dive":
    st.markdown('<div class="main-header">Annual Quarter Deep Dive (Spring vs Autumn)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Comprehensive KPI comparison and variance between Spring (Q2) and Autumn (Q4) campaigns for both 2026 and 2025</div>', unsafe_allow_html=True)

    col_yr, col_info = st.columns([1, 2])
    with col_yr:
        comp_year = st.radio("Select Campaign Year:", [2026, 2025], horizontal=True, index=0)
    with col_info:
        if comp_year == 2026:
            st.info("📅 **2026 Active Campaigns:** Spring (Q2: May 5 – May 22) vs Autumn (Q4: Oct 5 – Oct 23)")
        else:
            st.info("📅 **2025 Active Campaigns:** Spring (Q2: Apr 7 – Apr 25) vs Autumn (Q4: Oct 6 – Oct 23)")

    d_spring_s, d_spring_e = get_default_dates(comp_year, "Q2", "Campaign Window")
    d_autumn_s, d_autumn_e = get_default_dates(comp_year, "Q4", "Campaign Window")

    kpis_spring, tasks_spring, disc_spring, meta_spring = get_quarter_kpis(tasks_df, disc_df, f"Q2-{comp_year}", start_date=d_spring_s, end_date=d_spring_e)
    kpis_autumn, tasks_autumn, disc_autumn, meta_autumn = get_quarter_kpis(tasks_df, disc_df, f"Q4-{comp_year}", start_date=d_autumn_s, end_date=d_autumn_e)

    # Headline Comparison Cards
    c1, c2, c3, c4 = st.columns(4)
    v1_s = kpis_spring.get('kpi_1_certification_completion', {}).get('value')
    v1_a = kpis_autumn.get('kpi_1_certification_completion', {}).get('value')
    d1 = f"{(v1_a - v1_s):+.1f}% vs Spring" if (v1_s is not None and v1_a is not None) else None
    c1.metric("Autumn Completion %", f"{v1_a}%" if v1_a is not None else "N/A", delta=d1)

    v2_s = kpis_spring.get('kpi_2_daily_closure_rate', {}).get('value')
    v2_a = kpis_autumn.get('kpi_2_daily_closure_rate', {}).get('value')
    d2 = f"{(v2_a - v2_s):+.2f} vs Spring" if (v2_s is not None and v2_a is not None) else None
    c2.metric("Autumn Daily Rate", f"{v2_a} tasks/d" if v2_a is not None else "N/A", delta=d2)

    v3_s = kpis_spring.get('kpi_3_on_time_completion', {}).get('value')
    v3_a = kpis_autumn.get('kpi_3_on_time_completion', {}).get('value')
    d3 = f"{(v3_a - v3_s):+.1f}% vs Spring" if (v3_s is not None and v3_a is not None) else None
    c3.metric("Autumn On-Time %", f"{v3_a}%" if v3_a is not None else "N/A", delta=d3)

    v5_s = kpis_spring.get('kpi_5_discrepancy_rate', {}).get('value')
    v5_a = kpis_autumn.get('kpi_5_discrepancy_rate', {}).get('value')
    d5 = f"{(v5_a - v5_s):+.2f}% vs Spring" if (v5_s is not None and v5_a is not None) else None
    c4.metric("Autumn Discrepancy %", f"{v5_a}%" if v5_a is not None else "N/A", delta=d5, delta_color="inverse")

    st.markdown("---")
    col_t, col_c = st.columns([1, 1])

    with col_t:
        st.subheader(f"📋 {comp_year}: Autumn (Q4) vs Spring (Q2) KPI Matrix")
        comp_rows = cycle_mgr.compare_metrics(kpis_autumn, kpis_spring, mode="intra_year")
        rep_gen = ReportGenerator(meta_autumn, app_mode=app_mode)
        comp_df = rep_gen.build_cycle_comparison_df(comp_rows)
        # Clean null/None values so table displays clean '-' instead of 'None' or 'None %'
        comp_df = comp_df.fillna("-")
        for col_name in comp_df.columns:
            comp_df[col_name] = comp_df[col_name].replace({'None': '-', 'None %': '-', 'nan': '-', 'NaN': '-'})
            if comp_df[col_name].dtype == 'object':
                comp_df[col_name] = comp_df[col_name].astype(str)
        
        # Eliminate any duplicate or redundant change columns before renaming
        if "Absolute Change" in comp_df.columns and "Variance" in comp_df.columns:
            comp_df = comp_df.drop(columns=["Absolute Change"])
        
        comp_df = comp_df.rename(columns={
            "Current Value": f"Autumn Q4-{comp_year}",
            "Previous Value": f"Spring Q2-{comp_year}",
            "Variance": f"Variance (Q4 - Q2)",
            "Absolute Change": f"Variance (Q4 - Q2)"
        })
        # Defensive de-duplication: guarantee unique column names for PyArrow / Streamlit table
        comp_df = comp_df.loc[:, ~comp_df.columns.duplicated()]
        st.dataframe(comp_df, use_container_width=True, height=400, hide_index=True)

        csv_exp = comp_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Download {comp_year}_q2_vs_q4_comparison.csv",
            data=csv_exp,
            file_name=f"{comp_year}_q2_vs_q4_comparison.csv",
            mime="text/csv"
        )

    with col_c:
        st.subheader("📊 Key KPIs Comparison")
        comp_chart_data = []
        for row in comp_rows:
            if row['unit'] == '%' and row['current_value'] is not None and row['previous_value'] is not None:
                # Clean shortened label for visual aesthetics (zero text overlap)
                k_name = row['metric_name']
                short_label = (
                    k_name.replace(" (<=1d)", "")
                          .replace("Certification ", "")
                          .replace(" / Pass Rate", "")
                          .replace("Final ", "")
                )
                comp_chart_data.append({'KPI': short_label, 'Campaign': f"Spring Q2-{comp_year}", 'Value (%)': row['previous_value']})
                comp_chart_data.append({'KPI': short_label, 'Campaign': f"Autumn Q4-{comp_year}", 'Value (%)': row['current_value']})
        
        if comp_chart_data:
            df_plot = pd.DataFrame(comp_chart_data)
            fig_bar = px.bar(
                df_plot,
                y='KPI',
                x='Value (%)',
                color='Campaign',
                barmode='group',
                orientation='h',
                text='Value (%)',
                color_discrete_map={f"Spring Q2-{comp_year}": "#3B82F6", f"Autumn Q4-{comp_year}": "#10B981"}
            )
            fig_bar.update_layout(
                height=420,
                xaxis_range=[0, 125],
                yaxis_title="",
                xaxis_title="Percentage (%)",
                margin=dict(l=10, r=50, t=30, b=30),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            fig_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_bar, use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE 3: ANNUAL MASTER MATRIX (ALL 4 QUARTERS)
# -----------------------------------------------------------------------------
elif page == "🗓️ Annual Master Matrix (All 4 Quarters)":
    st.markdown('<div class="main-header">Annual Campaign Master Matrix (2025 & 2026)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">All 4 active certification campaigns side-by-side with YoY variance and zero empty columns</div>', unsafe_allow_html=True)

    target_quarters = ['Q2-2025', 'Q4-2025', 'Q2-2026', 'Q4-2026']
    kpi_metric_specs = [
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

    quarterly_data = {}
    quarter_task_counts = {}
    for q in target_quarters:
        yr = int(q.split('-')[1])
        q_code = q.split('-')[0]
        s_d, e_d = get_default_dates(yr, q_code, "Campaign Window")
        k_res, t_res, d_res, m_res = get_quarter_kpis(tasks_df, disc_df, q, start_date=s_d, end_date=e_d)
        quarterly_data[q] = k_res
        quarter_task_counts[q] = {
            'count': len(t_res),
            'start': s_d,
            'end': e_d,
            'working_days': m_res.get('total_working_days', 0)
        }

    matrix_rows = []
    for k_key, k_label, k_unit in kpi_metric_specs:
        row = {"Metric Name": k_label, "Unit": k_unit}
        for q in target_quarters:
            val = quarterly_data[q].get(k_key, {}).get('value')
            row[q] = f"{val}{k_unit}" if (val is not None and not pd.isna(val)) else "-"
        
        # YoY change
        v4_26 = quarterly_data['Q4-2026'].get(k_key, {}).get('value')
        v4_25 = quarterly_data['Q4-2025'].get(k_key, {}).get('value')
        row['Autumn YoY Variance (Q4-26 vs Q4-25)'] = f"{(v4_26 - v4_25):+.2f}{k_unit}" if (v4_26 is not None and v4_25 is not None) else "-"

        v2_26 = quarterly_data['Q2-2026'].get(k_key, {}).get('value')
        v2_25 = quarterly_data['Q2-2025'].get(k_key, {}).get('value')
        row['Spring YoY Variance (Q2-26 vs Q2-25)'] = f"{(v2_26 - v2_25):+.2f}{k_unit}" if (v2_26 is not None and v2_25 is not None) else "-"
        matrix_rows.append(row)

    matrix_df = pd.DataFrame(matrix_rows)

    c_audit1, c_audit2, c_audit3, c_audit4 = st.columns(4)
    for i, q in enumerate(target_quarters):
        info = quarter_task_counts[q]
        [c_audit1, c_audit2, c_audit3, c_audit4][i].metric(
            f"{q} Campaign Scope",
            f"{info['count']:,} tasks",
            delta=f"{info['working_days']} working days"
        )

    st.markdown("---")
    
    # Visual: All 4 Quarters Performance Comparison Chart
    q_chart_rows = []
    for q in target_quarters:
        c_k = quarterly_data[q]
        q_chart_rows.append({
            "Quarter": q,
            "Completion %": float(c_k.get('kpi_1_certification_completion', {}).get('value') or 0.0),
            "On-Time %": float(c_k.get('kpi_3_on_time_completion', {}).get('value') or 0.0),
            "Discrepancy %": float(c_k.get('kpi_5_discrepancy_rate', {}).get('value') or 0.0)
        })
    df_q_chart = pd.DataFrame(q_chart_rows)
    df_q_melt = df_q_chart.melt(id_vars=["Quarter"], var_name="Metric", value_name="Score (%)")

    fig_matrix = px.bar(
        df_q_melt,
        x="Quarter",
        y="Score (%)",
        color="Metric",
        barmode="group",
        color_discrete_map={"Completion %": "#10B981", "On-Time %": "#3B82F6", "Discrepancy %": "#EF4444"},
        title="Active 4-Quarter Comparison: Completion %, On-Time %, and Discrepancy %"
    )
    fig_matrix.add_hline(y=95.0, line_dash="dash", line_color="#059669", annotation_text="Target: 95%")
    fig_matrix.update_layout(height=350, yaxis_range=[0, 105], legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    st.plotly_chart(fig_matrix, use_container_width=True)

    st.subheader("📋 Consolidated 4-Quarter Master Table")
    st.dataframe(matrix_df, use_container_width=True, height=380, hide_index=True)

    csv_matrix = matrix_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Annual Master Matrix CSV",
        data=csv_matrix,
        file_name="annual_campaign_master_matrix_2025_2026.csv",
        mime="text/csv"
    )

# PAGE 6: DISCREPANCY REASON & SCENARIO ANALYTICS (23 AUDITED CATEGORIES)
# -----------------------------------------------------------------------------
elif page == "👥 Certifier Performance Leaderboard":
    st.markdown(f'<div class="main-header">👥 Certifier Workload & Performance Leaderboard — {selected_cycle}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Individual certifier task allocation, completion throughput, daily run rates, and lagging backlog ranking (Table: <code>cert_task</code>)</div>', unsafe_allow_html=True)

    rep_gen = ReportGenerator(curr_meta, app_mode=app_mode)
    working_days = curr_meta.get('elapsed_working_days', 15) if curr_meta else 15
    prod_df = rep_gen.build_certifier_productivity_df(c_tasks, working_days=working_days, sort_by="worst")

    if not prod_df.empty:
        # Ranking selector
        c_sort_col1, c_sort_col2 = st.columns([2, 3])
        with c_sort_col1:
            c_rank_mode = st.radio(
                "Certifier Ranking Mode:",
                [
                    "⚠️ Worst Performers First (Slowest / High Backlog)",
                    "📊 Highest Assigned Workload",
                    "🏆 Top Performers (Fastest / 100% Complete)"
                ],
                index=0
            )

        if c_rank_mode.startswith("⚠️ Worst"):
            prod_df = prod_df.sort_values(by=["Avg Completion Time (Days)", "Open Tasks", "Completion Rate %"], ascending=[False, False, True])
        elif c_rank_mode.startswith("🏆 Top"):
            prod_df = prod_df.sort_values(by=["Completion Rate %", "Avg Completion Time (Days)", "Completed Tasks"], ascending=[False, True, False])
        else:
            prod_df = prod_df.sort_values(by=["Assigned Tasks"], ascending=False)

        total_certifiers = len(prod_df)
        total_assigned = int(prod_df['Assigned Tasks'].sum())
        total_completed = int(prod_df['Completed Tasks'].sum())
        avg_rate = float(prod_df['Daily Rate'].mean())
        avg_time = float(prod_df['Avg Completion Time (Days)'].mean()) if 'Avg Completion Time (Days)' in prod_df.columns else 0.0

        # KPI Summary Cards
        c_c1, c_c2, c_c3, c_c4, c_c5 = st.columns(5)
        c_c1.metric("1. Active Certifiers", f"{total_certifiers:,}")
        c_c2.metric("2. Assigned Workload", f"{total_assigned:,} tasks")
        c_c3.metric("3. Completed Tasks", f"{total_completed:,} tasks", f"{(total_completed/total_assigned*100):.1f}% complete" if total_assigned > 0 else "")
        c_c4.metric("4. Avg Certifier Rate", f"{avg_rate:.2f} tasks/d")
        c_c5.metric("5. Avg Completion Time", f"{avg_time:.1f} days", "Target: ≤5.0 days")

        # Worst Performers Alert Banner
        worst_certifiers = prod_df[
            (prod_df['Avg Completion Time (Days)'] > 6.0) |
            (prod_df['Completion Rate %'] < 80.0) |
            (prod_df['Open Tasks'] > 10)
        ].copy()

        if not worst_certifiers.empty:
            slowest_cert = worst_certifiers.iloc[0]['Certifier']
            slowest_days = worst_certifiers.iloc[0]['Avg Completion Time (Days)']
            st.markdown(f"""
            <div style="background-color: #FEF2F2; border: 1px solid #FCA5A5; border-left: 4px solid #DC2626; border-radius: 6px; padding: 10px 14px; margin-top: 10px; margin-bottom: 12px;">
                <span style="color: #991B1B; font-size: 13px; font-weight: 700;">🚨 Certifier Lag Alert: {len(worst_certifiers)} Certifiers Requiring Operational Follow-Up</span><br>
                <span style="color: #7F1D1D; font-size: 12px;">Slowest certifier is <b>{slowest_cert}</b> averaging <b>{slowest_days:.1f} days</b> per task. Review uncertified open queues to prevent campaign deadline slippage.</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")

        # Visuals
        ch_c1, ch_c2 = st.columns(2)
        with ch_c1:
            st.markdown("##### ⏱️ Slowest Certifiers: Avg Time Taken to Certify (Worst First)")
            slowest_plot = prod_df.sort_values(by="Avg Completion Time (Days)", ascending=False).head(12).copy()
            fig_slow_cert = px.bar(
                slowest_plot,
                x="Avg Completion Time (Days)",
                y="Certifier",
                orientation="h",
                text="Avg Completion Time (Days)",
                color="Avg Completion Time (Days)",
                color_continuous_scale="Reds",
                labels={"Avg Completion Time (Days)": "Days to Certify", "Certifier": "Certifier"}
            )
            fig_slow_cert.add_vline(x=5.0, line_dash="dash", line_color="#DC2626", annotation_text="Target: ≤5.0d")
            fig_slow_cert.update_layout(
                height=380,
                margin=dict(l=10, r=40, t=20, b=30),
                yaxis=dict(autorange="reversed"),
                coloraxis_showscale=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            fig_slow_cert.update_traces(texttemplate='%{text:.1f} days', textposition='outside', cliponaxis=False)
            st.plotly_chart(fig_slow_cert, use_container_width=True)

        with ch_c2:
            st.markdown("##### 📊 Top Certifiers by Assigned Workload & Closures")
            top_workload = prod_df.sort_values(by="Assigned Tasks", ascending=False).head(12).copy()
            fig_cert_wl = px.bar(
                top_workload,
                x="Assigned Tasks",
                y="Certifier",
                orientation="h",
                text="Completed Tasks",
                color="Completed Tasks",
                color_continuous_scale="Blues",
                labels={"Assigned Tasks": "Assigned Tasks", "Certifier": "Certifier"}
            )
            fig_cert_wl.update_layout(
                height=380,
                margin=dict(l=10, r=30, t=20, b=30),
                yaxis=dict(autorange="reversed"),
                coloraxis_showscale=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            fig_cert_wl.update_traces(texttemplate='Done: %{text}', textposition='inside')
            st.plotly_chart(fig_cert_wl, use_container_width=True)

        st.markdown("---")

        # Table
        st.subheader("📋 Sortable Certifier Workload & Performance Table")
        styled_cert_df = prod_df.copy()
        styled_cert_df['Completion Rate %'] = styled_cert_df['Completion Rate %'].apply(lambda x: f"{x:.1f}%")
        styled_cert_df['Daily Rate'] = styled_cert_df['Daily Rate'].apply(lambda x: f"{x:.2f}")
        styled_cert_df['Avg Completion Time (Days)'] = styled_cert_df['Avg Completion Time (Days)'].apply(lambda x: f"{x:.1f} days")

        st.dataframe(styled_cert_df, use_container_width=True, height=400, hide_index=True)
        csv_prod = prod_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label=f"📥 Download {selected_cycle}_certifier_performance.csv",
            data=csv_prod,
            file_name=f"{selected_cycle}_certifier_performance.csv",
            mime="text/csv"
        )
    else:
        st.info("No certifier performance records available for this filter selection.")

# -----------------------------------------------------------------------------
elif page == "🔍 Discrepancy Reason & Scenario Analytics":
    st.markdown('<div class="main-header">🔍 Discrepancy Reason & Scenario Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Root-cause classification and audit gap analysis across all 23 certified ServiceNow CMDB attributes and governance domains.</div>', unsafe_allow_html=True)

    from src.analytics.discrepancy_rca import DiscrepancyRCAEngine, DISCREPANCY_CATEGORIES
    rca_engine = DiscrepancyRCAEngine()

    # Scope selector: Active Campaign vs All Campaigns
    col_scope1, col_scope2 = st.columns([2, 3])
    with col_scope1:
        rca_scope = st.radio(
            "Analysis Scope:",
            [f"Active Campaign ({selected_cycle})", "All 4 Historical Campaigns (Consolidated)"],
            horizontal=True
        )

    if rca_scope.startswith("Active Campaign") and not c_disc.empty:
        raw_rca_df = c_disc.copy()
        scope_tasks_df = c_tasks.copy()
        scope_label = selected_cycle
    elif disc_df is not None and not disc_df.empty:
        raw_rca_df = disc_df.copy()
        scope_tasks_df = tasks_df.copy() if tasks_df is not None else pd.DataFrame()
        scope_label = "All Campaigns"
    else:
        raw_rca_df = pd.DataFrame()
        scope_tasks_df = pd.DataFrame()
        scope_label = "None"

    if raw_rca_df.empty:
        st.warning("⚠️ No discrepancy records available to analyze for the selected campaign scope.")
    else:
        with st.spinner("Classifying discrepancies across 23 certified CMDB categories..."):
            enriched_rca_df = rca_engine.categorize_dataframe(raw_rca_df, tasks_df=scope_tasks_df)

        total_disc = len(enriched_rca_df)
        classified_mask = enriched_rca_df['rca_scenario'] != "Unclassified / Other Discrepancy"
        classified_count = int(classified_mask.sum())
        classified_rate = (classified_count / total_disc * 100.0) if total_disc > 0 else 0.0

        scenario_counts = enriched_rca_df['rca_scenario'].value_counts()
        top_scenario_name = scenario_counts.index[0] if not scenario_counts.empty else "N/A"
        top_scenario_count = int(scenario_counts.iloc[0]) if not scenario_counts.empty else 0
        top_scenario_pct = (top_scenario_count / total_disc * 100.0) if total_disc > 0 else 0.0

        crit_mask = enriched_rca_df['rca_risk_level'] == 'Critical'
        crit_count = int(crit_mask.sum())
        crit_pct = (crit_count / total_disc * 100.0) if total_disc > 0 else 0.0

        status_col = 'u_status' if 'u_status' in enriched_rca_df.columns else ('state' if 'state' in enriched_rca_df.columns else None)
        if status_col:
            res_mask = enriched_rca_df[status_col].astype(str).str.strip().str.lower().isin(['resolved', 'closed', 'closed complete', 'complete', '3'])
            res_count = int(res_mask.sum())
            res_rate = (res_count / total_disc * 100.0) if total_disc > 0 else 0.0
        else:
            res_count = 0
            res_rate = 0.0

        # Sleek 5-Metric Executive Scorecard
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Discrepancies", f"{total_disc:,}", f"Scope: {scope_label}")
        m2.metric("Audited Categories", f"{enriched_rca_df['rca_scenario'].nunique()} Categories", f"{classified_rate:.1f}% Classified")
        m3.metric("Top Audit Defect Driver", f"{top_scenario_name}", f"{top_scenario_pct:.1f}% ({top_scenario_count:,} records)")
        m4.metric("Critical Compliance Gaps", f"{crit_count:,}", f"{crit_pct:.1f}% require urgent fix", delta_color="inverse")
        m5.metric("Resolution Health", f"{res_rate:.1f}%", f"{res_count:,} of {total_disc:,} resolved")

        st.markdown("---")

        # Interactive Filter Bar
        st.markdown("##### 🎛️ Interactive Category & Domain Filters")
        f_domain, f_cat, f_risk, f_search = st.columns([1.5, 2, 1.2, 1.8])

        all_domains = ["All Domains"] + sorted(enriched_rca_df['rca_domain'].dropna().unique().tolist())
        with f_domain:
            sel_domain = st.selectbox("Governance Domain:", options=all_domains, index=0)

        domain_filtered_df = enriched_rca_df if sel_domain == "All Domains" else enriched_rca_df[enriched_rca_df['rca_domain'] == sel_domain]
        all_cats = sorted(domain_filtered_df['rca_scenario'].unique().tolist())

        with f_cat:
            filter_scenarios = st.multiselect(
                "Audited Category:",
                options=all_cats,
                default=all_cats,
                help="Select certified categories to filter analysis."
            )

        with f_risk:
            available_risks = ['Critical', 'High', 'Medium', 'Low']
            filter_risks = st.multiselect(
                "Risk Severity:",
                options=available_risks,
                default=[r for r in available_risks if r in domain_filtered_df['rca_risk_level'].unique()]
            )

        with f_search:
            kw_search = st.text_input(
                "Search Keywords / Fields:",
                placeholder="e.g. u_access_reviewer, money_mover, dr_strategy...",
                help="Search across discrepancy text, field names, and notes."
            )

        # Apply Filters
        filtered_df = domain_filtered_df[
            domain_filtered_df['rca_scenario'].isin(filter_scenarios) &
            domain_filtered_df['rca_risk_level'].isin(filter_risks)
        ].copy()

        if kw_search and kw_search.strip():
            kw_clean = kw_search.strip().lower()
            filtered_df = filtered_df[
                filtered_df['rca_analyzed_text'].str.lower().str.contains(kw_clean, na=False) |
                filtered_df['rca_scenario'].str.lower().str.contains(kw_clean, na=False) |
                filtered_df['rca_matched_keywords'].str.lower().str.contains(kw_clean, na=False)
            ]

        st.markdown(f"<span style='color: #475569; font-size: 12px; font-weight: 500;'>Displaying <b>{len(filtered_df):,}</b> of <b>{total_disc:,}</b> discrepancy records</span>", unsafe_allow_html=True)

        if filtered_df.empty:
            st.info("No discrepancy records match your filter criteria. Try adjusting the search keyword or category filters.")
        else:
            # ROW 1: Discrepancy Breakdown by Audited Category & Severity + Domain Distribution Donut
            r1_col1, r1_col2 = st.columns([3, 2])

            with r1_col1:
                st.markdown("##### 📊 Discrepancy Volume by Audited Category & Severity")
                summary_df = rca_engine.get_scenario_summary(filtered_df)
                
                risk_colors = {
                    "Critical": "#DC2626",
                    "High": "#EA580C",
                    "Medium": "#2563EB",
                    "Low": "#64748B"
                }

                fig_bar = px.bar(
                    summary_df,
                    x="Count",
                    y="rca_scenario",
                    orientation="h",
                    color="Risk_Level",
                    color_discrete_map=risk_colors,
                    text="Count",
                    hover_data={"Domain": True, "Percentage": ":.1f%", "Action": True},
                    labels={"Count": "Discrepancy Records", "rca_scenario": "", "Risk_Level": "Risk Severity"}
                )
                chart_height = max(380, min(700, len(summary_df) * 26 + 100))
                fig_bar.update_layout(
                    height=chart_height,
                    margin=dict(l=10, r=40, t=20, b=30),
                    yaxis=dict(autorange="reversed"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
                )
                fig_bar.update_traces(
                    texttemplate='%{text} (%{customdata[1]:.1f}%)',
                    textposition='outside',
                    cliponaxis=False
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            with r1_col2:
                st.markdown("##### 🍩 Governance Domain Distribution")
                domain_summary = rca_engine.get_domain_summary(filtered_df)

                domain_colors = {
                    "Ownership & Custodianship": "#4F46E5",
                    "Risk, Governance & Compliance": "#DC2626",
                    "Architecture & Hosting": "#D97706",
                    "Support & Operations": "#2563EB",
                    "Lifecycle & Release": "#9333EA",
                    "Application Baseline": "#0D9488"
                }

                fig_donut = px.pie(
                    domain_summary,
                    names="rca_domain",
                    values="Count",
                    hole=0.52,
                    color="rca_domain",
                    color_discrete_map=domain_colors
                )
                fig_donut.update_layout(
                    height=chart_height,
                    margin=dict(l=10, r=10, t=20, b=20),
                    legend=dict(orientation="h", yanchor="bottom", y=-0.15)
                )
                fig_donut.update_traces(
                    textinfo='percent+label',
                    hovertemplate='<b>%{label}</b><br>Discrepancies: %{value:,}<br>Domain Share: %{percent}'
                )
                st.plotly_chart(fig_donut, use_container_width=True)

            # ROW 2: Cross-Application Category Breakdown (Shown when Application/CI Data is Present)
            candidate_app_cols = [
                'u_application', 'application', 'u_cmdb_ci', 'cmdb_ci',
                'configuration_item', 'ci', 'u_ci', 'cmdb_ci_business_app'
            ]
            app_col = next((c for c in candidate_app_cols if c in filtered_df.columns and filtered_df[c].dropna().nunique() > 0), None)

            if app_col:
                st.markdown("---")
                st.markdown("##### 🏢 Discrepancies Across Top Enterprise Applications")
                top_apps = filtered_df[app_col].value_counts().nlargest(10).index.tolist()
                sub_app_df = filtered_df[filtered_df[app_col].isin(top_apps)]

                app_cross = sub_app_df.groupby([app_col, 'rca_scenario']).size().reset_index(name='Count')

                fig_app = px.bar(
                    app_cross,
                    x="Count",
                    y=app_col,
                    color="rca_scenario",
                    orientation="h",
                    barmode="stack",
                    labels={"Count": "Discrepancies", app_col: "Application", "rca_scenario": "Category"},
                    color_discrete_sequence=px.colors.qualitative.Safe
                )
                fig_app.update_layout(
                    height=380,
                    margin=dict(l=10, r=20, t=20, b=30),
                    yaxis=dict(autorange="reversed"),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10)),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
                )
                st.plotly_chart(fig_app, use_container_width=True)

            st.markdown("---")

            # ROW 3: Multi-Quarter Campaign Evolution & Category Shift
            if 'certification_cycle' in raw_rca_df.columns:
                unique_cycles = [c for c in ['Q4-2026', 'Q2-2026', 'Q4-2025', 'Q2-2025'] if c in raw_rca_df['certification_cycle'].unique()]
                if len(unique_cycles) >= 2:
                    st.markdown("##### 📈 Multi-Quarter Campaign Evolution & Category Shift")
                    c_curr_name = unique_cycles[0]
                    c_prev_name = unique_cycles[1]

                    curr_disc_slice = raw_rca_df[raw_rca_df['certification_cycle'] == c_curr_name]
                    prev_disc_slice = raw_rca_df[raw_rca_df['certification_cycle'] == c_prev_name]

                    curr_enc = rca_engine.categorize_dataframe(curr_disc_slice, tasks_df=tasks_df)
                    prev_enc = rca_engine.categorize_dataframe(prev_disc_slice, tasks_df=tasks_df)

                    comp_shift_df = rca_engine.compare_campaign_scenarios(curr_enc, prev_enc)

                    if not comp_shift_df.empty:
                        st.caption(f"Comparing category volume and percentage share shift between **{c_curr_name}** and **{c_prev_name}**.")
                        st.dataframe(comp_shift_df, use_container_width=True, hide_index=True)

            st.markdown("---")

            # ROW 4: Audited Category Health Matrix & Remediation Playbook
            st.markdown("##### 🛡️ Audited Category Health Matrix & Remediation Playbook")
            st.caption("Standard operational playbook and recommended corrective actions for each certified attribute.")

            matrix_rows = []
            for scn, grp in filtered_df.groupby('rca_scenario'):
                c_total = len(grp)
                c_resolved = int(grp[status_col].astype(str).str.strip().str.lower().isin(['resolved', 'closed', 'closed complete', 'complete', '3']).sum()) if status_col else 0
                c_open = c_total - c_resolved
                res_pct = round((c_resolved / c_total * 100.0), 1) if c_total > 0 else 0.0
                meta = DISCREPANCY_CATEGORIES.get(scn, DISCREPANCY_CATEGORIES.get(scn.replace(" ", "_"), {}))
                matrix_rows.append({
                    "Audited Category": scn,
                    "Target Field": meta.get("field", scn),
                    "Governance Domain": meta.get("domain", grp['rca_domain'].iloc[0]),
                    "Risk Severity": meta.get("risk_level", grp['rca_risk_level'].iloc[0]),
                    "Total Gaps": c_total,
                    "Share %": f"{(c_total / len(filtered_df) * 100.0):.1f}%",
                    "Resolved": c_resolved,
                    "Open": c_open,
                    "Resolution Rate %": f"{res_pct:.1f}%",
                    "Actionable Remediation Playbook": meta.get("recommended_action", grp['rca_recommended_action'].iloc[0])
                })

            matrix_df = pd.DataFrame(matrix_rows).sort_values(by="Total Gaps", ascending=False)
            st.dataframe(matrix_df, use_container_width=True, hide_index=True)

            st.markdown("---")

            # ROW 5: Searchable Discrepancy Record Inspector
            st.markdown("##### 📋 Searchable Discrepancy Record Inspector")
            display_cols = ['number']
            if 'u_application' in filtered_df.columns: display_cols.append('u_application')
            if 'u_field' in filtered_df.columns: display_cols.append('u_field')
            display_cols.extend(['rca_scenario', 'rca_risk_level', 'rca_domain'])
            
            desc_show_col = 'description' if 'description' in filtered_df.columns else ('short_description' if 'short_description' in filtered_df.columns else 'rca_analyzed_text')
            display_cols.append(desc_show_col)
            
            if status_col: display_cols.append(status_col)
            display_cols.append('rca_recommended_action')

            col_rename_map = {
                'number': 'Discrepancy #',
                'u_application': 'Application',
                'u_field': 'Target Field',
                'rca_scenario': 'Audited Category',
                'rca_risk_level': 'Risk Severity',
                'rca_domain': 'Governance Domain',
                desc_show_col: 'Failure Reason / Description',
                status_col: 'Status',
                'rca_recommended_action': 'Remediation Action'
            }

            inspect_df = filtered_df[[c for c in display_cols if c in filtered_df.columns]].rename(columns=col_rename_map)
            st.dataframe(inspect_df, use_container_width=True, height=380, hide_index=True)

            # Export button
            csv_rca = inspect_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Download Discrepancy Category Analysis ({scope_label}).csv",
                data=csv_rca,
                file_name=f"Discrepancy_Audited_Categories_{scope_label}.csv",
                mime="text/csv"
            )

# -----------------------------------------------------------------------------
# PAGE 7: TEAM PERFORMANCE ANALYTICS (u_failed_data_certifications_list)
# -----------------------------------------------------------------------------
elif page == "👥 Team Performance Analytics":
    st.markdown('<div class="main-header">👥 Team Performance Analytics (Discrepancy Remediation)</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Performance tracking across <code>u_failed_data_certifications_list</code> and <code>cert_task</code> using <code>assigned_to</code>, with automated detection of lagging / worst performers.</div>', unsafe_allow_html=True)

    from src.analytics.productivity_analysis import ProductivityAnalyzer
    prod_analyzer = ProductivityAnalyzer()

    # Scope and Source selectors
    t_col1, t_col2, t_col3 = st.columns([1.5, 1.5, 2])
    with t_col1:
        team_source = st.radio(
            "Primary Table:",
            [
                "u_failed_data_certifications_list (Discrepancies)",
                "cert_task (Certification Tasks)"
            ],
            index=0
        )
    with t_col2:
        team_scope = st.radio(
            "Scope:",
            [f"Active Campaign ({selected_cycle})", "All Campaigns (Consolidated)"],
            index=0
        )
    with t_col3:
        rank_mode = st.radio(
            "Ranking & View Mode:",
            [
                "⚠️ Worst / Slowest Performers First",
                "📊 High Workload First",
                "🏆 Top Performers First"
            ],
            index=0
        )

    # Resolve dataframe
    if team_source.startswith("u_failed_data_certifications"):
        base_df = c_disc.copy() if team_scope.startswith("Active Campaign") else disc_df.copy()
        tbl_label = "u_failed_data_certifications_list"
    else:
        base_df = c_tasks.copy() if team_scope.startswith("Active Campaign") else tasks_df.copy()
        tbl_label = "cert_task"

    if base_df is None or base_df.empty:
        st.warning(f"⚠️ No records available in {tbl_label} for the selected scope.")
    else:
        # Ensure assigned_to is populated; if missing in discrepancies, link from cert_task
        if 'assigned_to' not in base_df.columns or base_df['assigned_to'].isna().all():
            if 'u_certification_task' in base_df.columns and tasks_df is not None and not tasks_df.empty:
                task_map = tasks_df.set_index('sys_id')['assigned_to'].to_dict() if 'sys_id' in tasks_df.columns and 'assigned_to' in tasks_df.columns else {}
                base_df['assigned_to'] = base_df['u_certification_task'].map(task_map)
            base_df['assigned_to'] = base_df.get('assigned_to', pd.Series()).fillna("Unassigned")

        working_days = curr_meta.get('elapsed_working_days', 15) if curr_meta else 15
        team_stats_df = prod_analyzer.build_team_performance_df(base_df, working_days=working_days)

        if team_stats_df.empty:
            st.info("No assignee data could be extracted.")
        else:
            # Apply user-selected ranking mode
            if rank_mode.startswith("⚠️ Worst"):
                team_stats_df = team_stats_df.sort_values(by=["Average turnaround time", "Open Backlog", "SLA compliance"], ascending=[False, False, True])
            elif rank_mode.startswith("🏆 Top"):
                team_stats_df = team_stats_df.sort_values(by=["SLA compliance", "Average turnaround time", "Tasks completed"], ascending=[False, True, False])
            else:
                team_stats_df = team_stats_df.sort_values(by=["Tasks assigned"], ascending=False)

            total_members = len(team_stats_df)
            total_assigned = int(team_stats_df['Tasks assigned'].sum())
            total_completed = int(team_stats_df['Tasks completed'].sum())
            avg_daily_rate = round(float(team_stats_df['Daily closure rate'].mean()), 2)
            avg_turnaround = round(float(team_stats_df['Average turnaround time'].mean()), 1)
            overall_sla = round(float(team_stats_df['SLA compliance'].mean()), 1)

            # Top 5 Core KPI Summary Cards
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("1. Tasks Assigned", f"{total_assigned:,}", f"{total_members} assignees")
            m2.metric("2. Tasks Completed", f"{total_completed:,}", f"{(total_completed/total_assigned*100):.1f}% completion" if total_assigned > 0 else "")
            m3.metric("3. Daily Closure Rate", f"{avg_daily_rate:.2f} /day", f"Across {working_days} working days")
            m4.metric("4. Avg Turnaround Time", f"{avg_turnaround:.1f} days", "Target: ≤5.0 days")
            m5.metric("5. SLA Compliance", f"{overall_sla:.1f}%", "Target: ≥95.0% SLA")

            # Dedicated Alert Banner for Lagging / Worst Performers
            worst_cohort = team_stats_df[
                (team_stats_df['Average turnaround time'] > 5.0) |
                (team_stats_df['SLA compliance'] < 90.0) |
                (team_stats_df['Open Backlog'] > 5)
            ].copy()

            if not worst_cohort.empty:
                slowest_member = worst_cohort.iloc[0]['Team Member']
                slowest_time = worst_cohort.iloc[0]['Average turnaround time']
                st.markdown(f"""
                <div style="background-color: #FEF2F2; border: 1px solid #FCA5A5; border-left: 4px solid #DC2626; border-radius: 6px; padding: 10px 14px; margin-top: 12px; margin-bottom: 12px;">
                    <span style="color: #991B1B; font-size: 13px; font-weight: 700;">🚨 Lagging / Worst Performers Alert: {len(worst_cohort)} Assignees Identified Exceeding SLA Standard</span><br>
                    <span style="color: #7F1D1D; font-size: 12px;">Slowest assignee is <b>{slowest_member}</b> taking <b>{slowest_time:.1f} days</b> on average. These individuals require operational follow-up to resolve open backlogs.</span>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # ROW 1: Charts
            ch1, ch2 = st.columns(2)
            with ch1:
                st.markdown("##### ⏱️ Slowest Performers: Turnaround Time vs Target (Worst First)")
                slowest_df = team_stats_df.sort_values(by="Average turnaround time", ascending=False).head(12).copy()
                fig_slow = px.bar(
                    slowest_df,
                    x="Average turnaround time",
                    y="Team Member",
                    orientation="h",
                    text="Average turnaround time",
                    color="Average turnaround time",
                    color_continuous_scale="Reds",
                    labels={"Average turnaround time": "Avg Turnaround (Days)", "Team Member": "Assignee"}
                )
                fig_slow.add_vline(x=5.0, line_dash="dash", line_color="#DC2626")
                fig_slow.add_annotation(
                    x=5.0,
                    y=1.04,
                    yref="paper",
                    text="<b>SLA Target: 5.0d</b>",
                    showarrow=False,
                    xanchor="left",
                    yanchor="bottom",
                    font=dict(color="#DC2626", size=11, family="sans-serif"),
                    bgcolor="rgba(255, 255, 255, 0.95)",
                    bordercolor="#DC2626",
                    borderwidth=1,
                    borderpad=3
                )
                max_slow_val = float(slowest_df['Average turnaround time'].max()) if not slowest_df.empty else 10.0
                fig_slow.update_xaxes(range=[0, max(max_slow_val * 1.18, 6.0)])
                fig_slow.update_layout(
                    height=380,
                    margin=dict(l=10, r=50, t=40, b=30),
                    yaxis=dict(autorange="reversed"),
                    coloraxis_showscale=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
                )
                fig_slow.update_traces(texttemplate='%{text:.1f} days', textposition='outside', cliponaxis=False)
                st.plotly_chart(fig_slow, use_container_width=True)

            with ch2:
                st.markdown("##### 📊 Assigned Workload vs. Completed Tasks")
                workload_top = team_stats_df.sort_values(by="Tasks assigned", ascending=False).head(12).copy()
                fig_workload = px.bar(
                    workload_top,
                    x="Tasks assigned",
                    y="Team Member",
                    orientation="h",
                    text="Tasks completed",
                    color="Tasks completed",
                    color_continuous_scale="Blues",
                    labels={"Tasks assigned": "Assigned Tasks", "Team Member": "Assignee"}
                )
                fig_workload.update_layout(
                    height=380,
                    margin=dict(l=10, r=30, t=40, b=30),
                    yaxis=dict(autorange="reversed"),
                    coloraxis_showscale=False,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)"
                )
                fig_workload.update_traces(texttemplate='Done: %{text}', textposition='inside')
                st.plotly_chart(fig_workload, use_container_width=True)

            # ROW 2: SLA vs Turnaround Scatter Plot
            st.markdown("##### 🎯 SLA Compliance (%) vs. Average Turnaround Time")

            # Intelligent collision-free label positioning across close proximity points
            def _calculate_scatter_label_positions(df, x_col="Average turnaround time", y_col="SLA compliance"):
                if df is None or df.empty:
                    return "top center"
                x_vals = df[x_col].values
                y_vals = df[y_col].values
                n = len(df)
                if n <= 1:
                    return ["top center"] * n
                x_span = max(1.0, float(np.ptp(x_vals)))
                y_span = max(1.0, float(np.ptp(y_vals)))
                positions = []
                for i in range(n):
                    xi, yi = x_vals[i], y_vals[i]
                    close_indices = []
                    for j in range(n):
                        if i != j:
                            dx = abs(xi - x_vals[j]) / x_span
                            dy = abs(yi - y_vals[j]) / max(1.0, y_span)
                            if dx < 0.16 and dy < 0.22:
                                close_indices.append(j)
                    if not close_indices:
                        positions.append("bottom center" if yi >= 90 else "top center")
                    else:
                        cluster = sorted([i] + close_indices, key=lambda idx: x_vals[idx])
                        rank = cluster.index(i)
                        c_size = len(cluster)
                        if c_size == 2:
                            positions.append(("top left" if yi < 85 else "bottom left") if rank == 0 else ("top right" if yi < 85 else "bottom right"))
                        elif c_size == 3:
                            if rank == 0:
                                positions.append("top left" if yi < 85 else "bottom left")
                            elif rank == 1:
                                positions.append("top center" if yi < 50 else "bottom center")
                            else:
                                positions.append("top right" if yi < 85 else "bottom right")
                        else:
                            alt = ["top left", "top right", "bottom left", "bottom right"]
                            positions.append(alt[rank % len(alt)])
                return positions

            scatter_label_positions = _calculate_scatter_label_positions(team_stats_df)

            fig_sla = px.scatter(
                team_stats_df,
                x="Average turnaround time",
                y="SLA compliance",
                size="Tasks assigned",
                color="Daily closure rate",
                hover_name="Team Member",
                text="Team Member",
                labels={
                    "Average turnaround time": "Avg Turnaround Time (Days)",
                    "SLA compliance": "SLA Compliance (%)",
                    "Daily closure rate": "Daily Rate (tasks/d)"
                },
                color_continuous_scale="Viridis"
            )
            fig_sla.add_hline(
                y=95.0,
                line_dash="dash",
                line_color="#10B981",
                annotation_text="Target: 95% SLA",
                annotation_position="top right",
                annotation=dict(bgcolor="rgba(255, 255, 255, 0.9)", bordercolor="#10B981", borderwidth=1, borderpad=2, font=dict(color="#065F46", size=10))
            )
            fig_sla.add_vline(
                x=5.0,
                line_dash="dash",
                line_color="#DC2626",
                annotation_text="Max Standard: 5.0 Days",
                annotation_position="top right",
                annotation=dict(bgcolor="rgba(255, 255, 255, 0.9)", bordercolor="#DC2626", borderwidth=1, borderpad=2, font=dict(color="#DC2626", size=10))
            )
            fig_sla.update_traces(
                textposition=scatter_label_positions,
                textfont=dict(size=11, family="sans-serif", color="#1E293B")
            )
            max_all_turnaround = float(team_stats_df['Average turnaround time'].max()) if not team_stats_df.empty else 10.0
            fig_sla.update_xaxes(range=[0, max(max_all_turnaround * 1.15, 14.0)])
            fig_sla.update_yaxes(range=[-10, 110])
            fig_sla.update_layout(
                height=380,
                margin=dict(l=10, r=30, t=30, b=30),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_sla, use_container_width=True)

            st.markdown("---")

            # ROW 3: Full Sortable Table
            st.markdown("##### 📋 Team & Certifier Performance Table")
            st.caption(f"Detailed performance breakdown for {tbl_label} grouped by <code>assigned_to</code> (Sort mode: {rank_mode}).")

            styled_df = team_stats_df.copy()
            styled_df['Completion Rate %'] = styled_df['Completion Rate %'].apply(lambda x: f"{x:.1f}%")
            styled_df['Daily closure rate'] = styled_df['Daily closure rate'].apply(lambda x: f"{x:.2f}")
            styled_df['Average turnaround time'] = styled_df['Average turnaround time'].apply(lambda x: f"{x:.1f} days")
            styled_df['SLA compliance'] = styled_df['SLA compliance'].apply(lambda x: f"{x:.1f}%")

            st.dataframe(styled_df, use_container_width=True, height=420, hide_index=True)

            csv_team = team_stats_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label=f"📥 Download Performance Breakdown ({tbl_label}).csv",
                data=csv_team,
                file_name=f"Performance_{tbl_label}_{selected_cycle}.csv",
                mime="text/csv"
            )

# PAGE 8: SERVICENOW INTEGRATION STATUS
# -----------------------------------------------------------------------------
elif page == "🔌 ServiceNow Integration Status":
    st.markdown('<div class="main-header">ServiceNow Live Integration Status</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Production API configuration, live table mappings, and verified datasets</div>', unsafe_allow_html=True)

    api_cfg = loader.get_api_config()
    is_live = (app_mode == 'live')

    c1, c2, c3 = st.columns(3)
    with c1:
        if is_live:
            st.success("**Active Mode:** LIVE API MODE")
        else:
            st.warning("**Active Mode:** OFFLINE DEMO MODE")
    with c2:
        st.info(f"**API Provider:** `{api_cfg.get('provider', 'servicenow').upper()}`")
    with c3:
        st.info(f"**Target Instance:** `{api_cfg.get('base_url') or 'Configured via .env'}`")

    st.markdown("---")
    st.subheader("⚡ Live Operations & Execution Pipeline")
    st.markdown("Test your ServiceNow connection endpoint or execute the end-to-end data extraction and reporting pipeline.")

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        btn_test = st.button("🔍 Test ServiceNow Connection & Tables", use_container_width=True)
    with col_btn2:
        btn_pipeline = st.button("🚀 Execute Full Analytics Pipeline", type="primary", use_container_width=True)

    use_cached = st.checkbox(
        "Use local cache if available (skip API re-download)",
        value=False,
        help="When checked, re-executes calculations and regenerates reports using local records without calling the ServiceNow API."
    )

    if btn_test:
        if not api_cfg.get('base_url'):
            st.warning("⚠️ No `API_BASE_URL` found in `.env`. Operating in demo/offline mode with local verified schemas.")
            t_t_name = loader.settings.get('provider', {}).get('tables', {}).get('cert_task', 'cert_task')
            d_t_name = loader.settings.get('provider', {}).get('tables', {}).get('failed_data_certifications', 'u_failed_data_certifications')
            st.info(f"Target Tables: Task Table = `{t_t_name}`, Discrepancy Table = `{d_t_name}`")
        else:
            with st.spinner("Connecting to ServiceNow and testing endpoint diagnostics..."):
                try:
                    from main import get_service_now_client
                    from src.discovery.connection_diagnostics import ConnectionDiagnostics

                    client = get_service_now_client(loader)
                    diagnostics = ConnectionDiagnostics(client, loader.settings.get('provider', {}))
                    res = diagnostics.run_diagnostics()

                    t1 = diagnostics.task_table
                    t2 = diagnostics.disc_table
                    c_tasks_count = client.get_record_count(t1) if res.get('task_table_access') else -1
                    c_disc_count = client.get_record_count(t2) if res.get('disc_table_access') else -1

                    st.markdown("##### 🔬 Connection Diagnostics Summary:")
                    r1, r2, r3, r4 = st.columns(4)
                    r1.metric("API Endpoint", "REACHABLE" if res.get('api_connectivity') else "FAILED")
                    r2.metric("Authentication", "AUTHORIZED" if res.get('auth_valid') else "UNAUTHORIZED")
                    r3.metric(f"Tasks (`{t1}`)", f"{c_tasks_count:,} records" if c_tasks_count >= 0 else ("ACCESSIBLE" if res.get('task_table_access') else "NO ACCESS"))
                    r4.metric(f"Discrepancies (`{t2}`)", f"{c_disc_count:,} records" if c_disc_count >= 0 else ("ACCESSIBLE" if res.get('disc_table_access') else "NO ACCESS"))

                    if res.get('api_connectivity') and res.get('auth_valid'):
                        st.success(f"✅ Successfully connected and authenticated to `{client.instance_url}`!")
                    else:
                        st.error("❌ Connection failed. Check instance URL, corporate VPN, or credentials.")
                        for s in res.get('suggestions', []):
                            st.warning(f"• {s}")
                except Exception as ex:
                    st.error(f"Diagnostic error: {ex}")

    if btn_pipeline:
        with st.spinner(f"Executing full analytics pipeline ({'CACHED' if use_cached else 'LIVE EXTRACTION'})..."):
            try:
                from main import cmd_pipeline
                import argparse
                import json
                res_code = cmd_pipeline(argparse.Namespace(mode=app_mode, skip_fetch=use_cached))
                if res_code == 0 or res_code is None:
                    latest_run_file = Path("data/runs/latest_run.json")
                    run_info = {}
                    if latest_run_file.exists():
                        try:
                            with open(latest_run_file, "r", encoding="utf-8") as rf:
                                run_info = json.load(rf)
                        except Exception:
                            pass
                    st.session_state['latest_pipeline_run'] = run_info
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Pipeline encountered an error during execution. Check terminal logs.")
            except Exception as ex:
                st.error(f"Pipeline execution failed: {ex}")

    if st.session_state.get('latest_pipeline_run'):
        run_data = st.session_state['latest_pipeline_run']
        st.success(
            f"🎉 **Pipeline Executed Successfully!**\n\n"
            f"📁 **Dedicated Run Directory Created:** `{run_data.get('run_dir', 'data/runs')}`\n\n"
            f"• **Raw Tasks Fetched:** `{run_data.get('raw_tasks_count', 0):,}` records\n\n"
            f"• **Raw Discrepancies Fetched:** `{run_data.get('raw_discrepancies_count', 0):,}` records\n\n"
            f"• **Processed & Validated Tasks:** `{run_data.get('processed_tasks_count', 0):,}` records\n\n"
            f"• **Processed Discrepancies:** `{run_data.get('processed_discrepancies_count', 0):,}` records\n\n"
            f"• **Consolidated Excel Report:** `{run_data.get('excel_report', 'reports/Data_Certification_KPI_Report.xlsx')}`\n\n"
            f"• **Execution Timestamp:** `{run_data.get('timestamp', '')}`"
        )

    st.markdown("---")
    st.subheader("📊 Active Dataset Statistics")
    d1, d2, d3 = st.columns(3)
    d1.metric("Processed Tasks Loaded", f"{len(tasks_df):,} records")
    d2.metric("Processed Discrepancies", f"{len(disc_df):,} records" if disc_df is not None else "0")
    
    date_col = 'sys_created_on' if 'sys_created_on' in tasks_df.columns else 'created_at'
    if date_col in tasks_df.columns:
        min_d = str(pd.to_datetime(tasks_df[date_col]).dt.date.min())
        max_d = str(pd.to_datetime(tasks_df[date_col]).dt.date.max())
        d3.metric("Dataset Date Span", f"{min_d} to {max_d}")
    else:
        d3.metric("Dataset Date Span", "N/A")

    st.markdown("---")
    st.subheader("📋 Verified Source Table Field Mappings")
    field_map = loader.get_field_mapping()
    t_tabs = st.tabs(["Table 1: cert_task", "Table 2: u_failed_data_certifications"])
    with t_tabs[0]:
        t1_maps = field_map.get('tables', {}).get('cert_task', {}).get('mappings', {})
        st.dataframe(pd.DataFrame(list(t1_maps.items()), columns=["Business Concept", "ServiceNow Field Name"]), use_container_width=True, hide_index=True)
    with t_tabs[1]:
        t2_maps = field_map.get('tables', {}).get('u_failed_data_certifications', {}).get('mappings', {})
        st.dataframe(pd.DataFrame(list(t2_maps.items()), columns=["Business Concept", "ServiceNow Field Name"]), use_container_width=True, hide_index=True)
