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
            "🔌 ServiceNow Integration Status"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("### 🔍 **Working Tab Filters**")

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
        
        app_col = 'business_service' if 'business_service' in c_tasks.columns else ('cmdb_ci' if 'cmdb_ci' in c_tasks.columns else ('application' if 'application' in c_tasks.columns else None))
        apps = sorted(list(c_tasks[app_col].dropna().unique())) if app_col in c_tasks.columns else []
        selected_apps = st.multiselect("Application / Business Service", apps, default=[])

        cert_col = 'assigned_to' if 'assigned_to' in c_tasks.columns else 'certifier'
        certifiers = sorted(list(c_tasks[cert_col].dropna().unique())) if cert_col in c_tasks.columns else []
        selected_certifiers = st.multiselect("Assigned Certifier", certifiers, default=[])

        state_col = 'state' if 'state' in c_tasks.columns else 'status'
        states = sorted(list(c_tasks[state_col].dropna().unique())) if state_col in c_tasks.columns else []
        selected_states = st.multiselect("Task State / Status", states, default=[])

        if selected_apps:
            c_tasks = c_tasks[c_tasks[app_col].isin(selected_apps)]
        if selected_certifiers:
            c_tasks = c_tasks[c_tasks[cert_col].isin(selected_certifiers)]
        if selected_states:
            c_tasks = c_tasks[c_tasks[state_col].isin(selected_states)]

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

    # Top 6 KPI Metric Cards Row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Completion %", f"{k1['value']}%", delta=f"{k1['numerator']}/{k1['denominator']}")
    m2.metric("Daily Run Rate", f"{k2['value']} tasks/d", delta=f"{curr_meta['elapsed_working_days']} w-days")
    m3.metric("On-Time Rate", f"{k3['value']}%", delta=f"{k3['numerator']} on-time")
    m4.metric("Discrepancy Rate", f"{k5['value']}%", delta_color="inverse")
    m5.metric("Avg Duration", f"{k4['value']} days" if k4.get('value') is not None else "N/A")
    m6.metric("Final SLA %", f"{k12.get('value', 'N/A')}%")

    st.markdown("---")

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

    # Executive Scorecards: Volume, Backlog & Risks, Quality
    sc1, sc2, sc3 = st.columns(3)

    with sc1:
        st.markdown(f'''
        <div style="background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 14px;">
            <h4 style="margin: 0 0 8px 0; color: #166534; font-size: 15px;">📦 Total Campaign Workload</h4>
            <p style="margin: 4px 0; font-size: 13px; color: #15803D;">• <b>Total Eligible Tasks:</b> {k1['denominator']:,}</p>
            <p style="margin: 4px 0; font-size: 13px; color: #15803D;">• <b>Closed Complete:</b> {k1['numerator']:,}</p>
            <p style="margin: 4px 0; font-size: 13px; color: #15803D;">• <b>Excluded / Cancelled:</b> {k1['excluded_count']:,}</p>
        </div>
        ''', unsafe_allow_html=True)

    k8 = kpis.get('kpi_8_backlog_aging', {})
    k8_val = k8.get('value', 0)
    overdue_count = 0
    state_col = 'state' if 'state' in c_tasks.columns else ('status' if 'status' in c_tasks.columns else None)
    due_col = 'due_date' if 'due_date' in c_tasks.columns else None
    if state_col and due_col:
        open_m = c_tasks[state_col].isin(["Open", "Work in Progress", "Pending Review"])
        as_of_dt = pd.to_datetime(curr_meta.get('end_date', '2026-10-23'))
        if hasattr(as_of_dt, 'tzinfo') and as_of_dt.tzinfo is not None:
            as_of_dt = as_of_dt.tz_localize(None)
        due_dts = pd.to_datetime(c_tasks.loc[open_m, due_col], errors='coerce')
        if hasattr(due_dts.dt, 'tz') and due_dts.dt.tz is not None:
            due_dts = due_dts.dt.tz_localize(None)
        overdue_count = int((due_dts < as_of_dt).sum())

    with sc2:
        st.markdown(f'''
        <div style="background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 14px;">
            <h4 style="margin: 0 0 8px 0; color: #991B1B; font-size: 15px;">⏳ Backlog & SLA Risk</h4>
            <p style="margin: 4px 0; font-size: 13px; color: #B91C1C;">• <b>Open Tasks Remaining:</b> {int(k8_val):,}</p>
            <p style="margin: 4px 0; font-size: 13px; color: #B91C1C;">• <b>Overdue SLA Tasks:</b> {overdue_count:,}</p>
            <p style="margin: 4px 0; font-size: 13px; color: #B91C1C;">• <b>Final SLA Target:</b> ≥95.0%</p>
        </div>
        ''', unsafe_allow_html=True)

    total_disc = len(c_disc) if c_disc is not None else 0
    resolved_disc = 0
    if c_disc is not None and not c_disc.empty:
        for st_cand in ['state', 'status', 'u_status']:
            if st_cand in c_disc.columns:
                resolved_disc = int(c_disc[st_cand].isin(['Resolved', 'Closed', 'resolved']).sum())
                break

    with sc3:
        st.markdown(f'''
        <div style="background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 8px; padding: 14px;">
            <h4 style="margin: 0 0 8px 0; color: #1E40AF; font-size: 15px;">🛡️ Data Quality & Compliance</h4>
            <p style="margin: 4px 0; font-size: 13px; color: #1D4ED8;">• <b>Total Discrepancies:</b> {total_disc:,}</p>
            <p style="margin: 4px 0; font-size: 13px; color: #1D4ED8;">• <b>Exceptions Resolved:</b> {resolved_disc:,}</p>
            <p style="margin: 4px 0; font-size: 13px; color: #1D4ED8;">• <b>Clean Record Pass Rate:</b> {k6['value']}%</p>
        </div>
        ''', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# PAGE 2: DAILY TRENDS & QUARTER VELOCITY COMPARISON
# -----------------------------------------------------------------------------
elif page == "📈 Daily Trends & Quarter Velocity":
    st.markdown('<div class="main-header">Quarter-Wise Daily Trend & Velocity Comparison</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Working-day normalized daily closures, run-rates, and cumulative velocity curves across 2026 and 2025 quarters</div>', unsafe_allow_html=True)

    col_p1, col_p2 = st.columns([1, 2])
    with col_p1:
        comp_preset = st.selectbox(
            "Quarter Comparison Scope:",
            [
                "2026: Q2 vs Q4 (Spring vs Autumn)",
                "2025: Q2 vs Q4 (Spring vs Autumn)",
                "Q4-2026 vs Q4-2025 (Autumn YoY)",
                "Q2-2026 vs Q2-2025 (Spring YoY)",
                "Custom Quarter Pair (Manual Dates)"
            ],
            index=0,
            key="daily_comp_preset"
        )
    with col_p2:
        st.markdown("""
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 10px 14px; margin-top: 6px;">
            <span style="font-weight: 600; color: #1E293B; font-size: 13px;">⚡ Working Day Alignment Rule:</span><br>
            <span style="color: #475569; font-size: 12px;">Since campaigns start on different calendar days, velocity is normalized along <b>Working Day 1 to Day N</b> for an accurate like-for-like comparison.</span>
        </div>
        """, unsafe_allow_html=True)

    # Preset date configurations
    if comp_preset == "2026: Q2 vs Q4 (Spring vs Autumn)":
        def_qa_name, def_qb_name = "Q4-2026", "Q2-2026"
        def_qa_start, def_qa_end = date(2026, 10, 5), date(2026, 10, 23)
        def_qb_start, def_qb_end = date(2026, 5, 5), date(2026, 5, 22)
    elif comp_preset == "2025: Q2 vs Q4 (Spring vs Autumn)":
        def_qa_name, def_qb_name = "Q4-2025", "Q2-2025"
        def_qa_start, def_qa_end = date(2025, 10, 6), date(2025, 10, 23)
        def_qb_start, def_qb_end = date(2025, 4, 7), date(2025, 4, 25)
    elif comp_preset == "Q4-2026 vs Q4-2025 (Autumn YoY)":
        def_qa_name, def_qb_name = "Q4-2026", "Q4-2025"
        def_qa_start, def_qa_end = date(2026, 10, 5), date(2026, 10, 23)
        def_qb_start, def_qb_end = date(2025, 10, 6), date(2025, 10, 23)
    elif comp_preset == "Q2-2026 vs Q2-2025 (Spring YoY)":
        def_qa_name, def_qb_name = "Q2-2026", "Q2-2025"
        def_qa_start, def_qa_end = date(2026, 5, 5), date(2026, 5, 22)
        def_qb_start, def_qb_end = date(2025, 4, 7), date(2025, 4, 25)
    else:
        def_qa_name, def_qb_name = "Q4-2026", "Q4-2025"
        def_qa_start, def_qa_end = date(2026, 10, 5), date(2026, 10, 23)
        def_qb_start, def_qb_end = date(2025, 10, 6), date(2025, 10, 23)

    with st.expander("🛠️ **Adjust Quarter Comparison Dates & Custom Windows**", expanded=(comp_preset == "Custom Quarter Pair (Manual Dates)")):
        col_c_left, col_c_right = st.columns(2)
        with col_c_left:
            st.markdown("##### **Quarter A (Primary / Baseline)**")
            qa_yr = st.selectbox("Year A", [2026, 2025], index=0 if "2026" in def_qa_name else 1, key="daily_qa_yr")
            qa_q = st.selectbox("Quarter A", ["Q2", "Q4"], index=["Q2", "Q4"].index(def_qa_name.split("-")[0] if def_qa_name.split("-")[0] in ["Q2", "Q4"] else "Q4"), key="daily_qa_q")
            qa_name = f"{qa_q}-{qa_yr}"
            d_qa1, d_qa2 = st.columns(2)
            qa_start = d_qa1.date_input("Start Date A", value=def_qa_start, key="daily_qa_s")
            qa_end = d_qa2.date_input("End Date A", value=def_qa_end, key="daily_qa_e")

        with col_c_right:
            st.markdown("##### **Quarter B (Comparison / Prior)**")
            qb_yr = st.selectbox("Year B", [2026, 2025], index=1 if "2025" in def_qb_name else 0, key="daily_qb_yr")
            qb_q = st.selectbox("Quarter B", ["Q2", "Q4"], index=["Q2", "Q4"].index(def_qb_name.split("-")[0] if def_qb_name.split("-")[0] in ["Q2", "Q4"] else "Q4"), key="daily_qb_q")
            qb_name = f"{qb_q}-{qb_yr}"
            d_qb1, d_qb2 = st.columns(2)
            qb_start = d_qb1.date_input("Start Date B", value=def_qb_start, key="daily_qb_s")
            qb_end = d_qb2.date_input("End Date B", value=def_qb_end, key="daily_qb_e")

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

        with ch_col1:
            fig_daily = go.Figure()
            fig_daily.add_trace(go.Bar(
                x=comp_daily_df['Day_Label'],
                y=comp_daily_df[col_qa_daily],
                name=f"{qa_name} Closures",
                marker_color="#1E40AF"
            ))
            fig_daily.add_trace(go.Bar(
                x=comp_daily_df['Day_Label'],
                y=comp_daily_df[col_qb_daily],
                name=f"{qb_name} Closures",
                marker_color="#F59E0B"
            ))
            fig_daily.update_layout(
                title=f"Daily Closures by Working Day: {qa_name} vs {qb_name}",
                barmode='group',
                xaxis_title="Working Day Elapsed",
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
                x=comp_daily_df['Day_Label'],
                y=comp_daily_df[col_qa_pct],
                mode='lines+markers',
                name=f"{qa_name} % Complete",
                line=dict(color="#1E40AF", width=3)
            ))
            fig_cum.add_trace(go.Scatter(
                x=comp_daily_df['Day_Label'],
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
                xaxis_title="Working Day Elapsed",
                yaxis_title="% of Campaign Completed",
                yaxis_range=[0, 105],
                height=380,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
            )
            st.plotly_chart(fig_cum, use_container_width=True)

        st.subheader("📋 Day-by-Day Normalized Comparative Data")
        display_cols = ['Day_Label', f"Date ({qa_name})", col_qa_daily, col_qa_cum, col_qa_pct,
                        f"Date ({qb_name})", col_qb_daily, col_qb_cum, col_qb_pct, 'Daily Difference (A - B)']
        available_display_cols = [c for c in display_cols if c in comp_daily_df.columns]
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
    col_t, col_c = st.columns([3, 2])

    with col_t:
        st.subheader(f"📋 {comp_year}: Autumn (Q4) vs Spring (Q2) KPI Matrix")
        comp_rows = cycle_mgr.compare_metrics(kpis_autumn, kpis_spring, mode="intra_year")
        rep_gen = ReportGenerator(meta_autumn, app_mode=app_mode)
        comp_df = rep_gen.build_cycle_comparison_df(comp_rows)
        comp_df = comp_df.rename(columns={
            "Current Value": f"Autumn Q4-{comp_year}",
            "Previous Value": f"Spring Q2-{comp_year}",
            "Absolute Change": "Delta (Q4 - Q2)"
        })
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
                comp_chart_data.append({'KPI': row['metric_name'], 'Campaign': f"Spring Q2-{comp_year}", 'Value (%)': row['previous_value']})
                comp_chart_data.append({'KPI': row['metric_name'], 'Campaign': f"Autumn Q4-{comp_year}", 'Value (%)': row['current_value']})
        
        if comp_chart_data:
            df_plot = pd.DataFrame(comp_chart_data)
            fig_bar = px.bar(
                df_plot, x='KPI', y='Value (%)', color='Campaign', barmode='group',
                color_discrete_map={f"Spring Q2-{comp_year}": "#3B82F6", f"Autumn Q4-{comp_year}": "#10B981"}
            )
            fig_bar.update_layout(height=400, yaxis_range=[0, 105], xaxis_tickangle=-30)
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
        row['Autumn YoY (Q4-26 vs Q4-25)'] = f"{(v4_26 - v4_25):+.2f}{k_unit}" if (v4_26 is not None and v4_25 is not None) else "-"

        v2_26 = quarterly_data['Q2-2026'].get(k_key, {}).get('value')
        v2_25 = quarterly_data['Q2-2025'].get(k_key, {}).get('value')
        row['Spring YoY (Q2-26 vs Q2-25)'] = f"{(v2_26 - v2_25):+.2f}{k_unit}" if (v2_26 is not None and v2_25 is not None) else "-"
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
    st.dataframe(matrix_df, use_container_width=True, height=450, hide_index=True)

    csv_matrix = matrix_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Annual Master Matrix CSV",
        data=csv_matrix,
        file_name="annual_campaign_master_matrix_2025_2026.csv",
        mime="text/csv"
    )

# -----------------------------------------------------------------------------
# PAGE 5: CERTIFIER PERFORMANCE LEADERBOARD
# -----------------------------------------------------------------------------
elif page == "👥 Certifier Performance Leaderboard":
    st.markdown(f'<div class="main-header">👥 Certifier Workload & Performance Leaderboard — {selected_cycle}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Individual certifier task allocation, completion throughput, daily run rates, and backlog ranking (slowest first)</div>', unsafe_allow_html=True)

    rep_gen = ReportGenerator(curr_meta, app_mode=app_mode)
    prod_df = rep_gen.build_certifier_productivity_df(c_tasks, curr_meta['elapsed_working_days'], sort_by="worst")

    if not prod_df.empty:
        total_certifiers = len(prod_df)
        total_assigned = int(prod_df['Total Assigned'].sum()) if 'Total Assigned' in prod_df.columns else len(c_tasks)
        total_completed = int(prod_df['Completed'].sum()) if 'Completed' in prod_df.columns else 0
        avg_rate = float(prod_df['Daily Run Rate'].mean()) if 'Daily Run Rate' in prod_df.columns else 0.0

        c_c1, c_c2, c_c3, c_c4 = st.columns(4)
        c_c1.metric("Active Certifiers", f"{total_certifiers:,}")
        c_c2.metric("Total Assigned Workload", f"{total_assigned:,} tasks")
        c_c3.metric("Total Tasks Completed", f"{total_completed:,} tasks")
        c_c4.metric("Average Certifier Run Rate", f"{avg_rate:.1f} tasks/d")

        st.markdown("---")
        st.dataframe(prod_df, use_container_width=True, height=450, hide_index=True)
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
# PAGE 5: SERVICENOW INTEGRATION STATUS
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
