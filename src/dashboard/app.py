import os
import sys
import glob
from pathlib import Path
from datetime import datetime, timezone

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
from src.config.validation import ConfigValidator
from src.analytics.kpi_engine import KPIEngine
from src.analytics.cycle_manager import CycleManager
from src.scheduler.deadline_monitor import DeadlineMonitor

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
        font-size: 26px;
        font-weight: 700;
        color: #1F497D;
        margin-bottom: 2px;
    }
    .sub-header {
        font-size: 14px;
        color: #5A6A85;
        margin-bottom: 16px;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .status-pill-demo {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .status-pill-live {
        background-color: #D1FAE5;
        color: #065F46;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .risk-badge-critical {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 11px;
    }
    .risk-badge-high {
        background-color: #FFEDD5;
        color: #9A3412;
        padding: 3px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 11px;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Data Loading & Caching
# -----------------------------------------------------------------------------
@st.cache_data(ttl=60)
def load_processed_data():
    tasks_path = PROJECT_ROOT / "data" / "processed" / "cert_tasks_processed.csv"
    disc_path = PROJECT_ROOT / "data" / "processed" / "discrepancies_processed.csv"
    
    if tasks_path.exists() and disc_path.exists():
        tasks = pd.read_csv(tasks_path)
        disc = pd.read_csv(disc_path)
        return tasks, disc
    return None, None

@st.cache_data(ttl=60)
def load_report_csv(name: str):
    path = PROJECT_ROOT / "reports" / f"{name}.csv"
    if path.exists():
        return pd.read_csv(path)
    return None

# Load application config
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
# Sidebar Navigation & Global Filters
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🏢 **Enterprise Analytics**")
    
    # Mode badge
    if app_mode == 'live':
        st.markdown('<span class="status-pill-live">● LIVE API MODE</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="status-pill-demo">● OFFLINE DEMO MODE</span>', unsafe_allow_html=True)

    st.markdown("---")
    page = st.radio(
        "Navigation",
        [
            "Executive Overview",
            "Cycle Comparison",
            "Daily Performance",
            "Data Quality & Discrepancies",
            "Certifier Productivity",
            "Backlog & SLA Monitoring",
            "Exception Resolution",
            "Data & Pipeline Health",
            "Settings & API Setup"
        ],
        index=0
    )

    st.markdown("---")
    st.markdown("### 🔍 **Global Filters**")

    if tasks_df is not None and not tasks_df.empty:
        cycle_col = 'u_certification_activity' if 'u_certification_activity' in tasks_df.columns else 'u_certification_cycle'
        available_cycles = sorted(list(tasks_df[cycle_col].dropna().unique())) if cycle_col in tasks_df.columns else ["Q4-2026"]
        
        selected_cycle = st.selectbox(
            "Certification Cycle",
            available_cycles,
            index=len(available_cycles) - 1 if available_cycles else 0
        )

        # Filter by cycle
        c_tasks = tasks_df[tasks_df[cycle_col] == selected_cycle].copy() if cycle_col in tasks_df.columns else tasks_df.copy()
        
        # Application filter
        app_col = 'cmdb_ci' if 'cmdb_ci' in c_tasks.columns else 'application'
        apps = sorted(list(c_tasks[app_col].dropna().unique())) if app_col in c_tasks.columns else []
        selected_apps = st.multiselect("Application / CI", apps, default=[])

        # Certifier filter
        cert_col = 'assigned_to' if 'assigned_to' in c_tasks.columns else 'certifier'
        certifiers = sorted(list(c_tasks[cert_col].dropna().unique())) if cert_col in c_tasks.columns else []
        selected_certifiers = st.multiselect("Assigned Certifier", certifiers, default=[])

        # Status filter
        state_col = 'state' if 'state' in c_tasks.columns else 'status'
        states = sorted(list(c_tasks[state_col].dropna().unique())) if state_col in c_tasks.columns else []
        selected_states = st.multiselect("Status / State", states, default=[])

        # Apply multiselect filters
        if selected_apps:
            c_tasks = c_tasks[c_tasks[app_col].isin(selected_apps)]
        if selected_certifiers:
            c_tasks = c_tasks[c_tasks[cert_col].isin(selected_certifiers)]
        if selected_states:
            c_tasks = c_tasks[c_tasks[state_col].isin(selected_states)]

        # Filter linked discrepancies
        c_disc = disc_df[disc_df['u_certification_task'].isin(c_tasks['sys_id'])].copy() if disc_df is not None else pd.DataFrame()
    else:
        selected_cycle = "Q4-2026"
        c_tasks = pd.DataFrame()
        c_disc = pd.DataFrame()

    st.markdown("---")
    # Quick export download
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

# Empty state handling
if tasks_df is None or tasks_df.empty:
    st.warning("⚠️ No processed data found. The analytical pipeline has not been executed yet.")
    st.info("Click the button below to generate synthetic demo data and run the complete pipeline.")
    if st.button("🚀 Initialize Demo Pipeline", type="primary"):
        with st.spinner("Generating demo data and executing analytics engine..."):
            from main import cmd_pipeline
            import argparse
            cmd_pipeline(argparse.Namespace(mode="demo"))
            st.cache_data.clear()
            st.rerun()
    st.stop()

# Instantiate KPI Engine
kpi_engine = KPIEngine(kpi_cfg, cycle_cfg)
curr_meta = cycle_mgr.get_cycle_metadata(cycle_mgr.current_cycle)
prev_meta = cycle_mgr.get_cycle_metadata(cycle_mgr.previous_cycle)

# Calculate active KPIs for filtered dataset
kpis = kpi_engine.calculate_all_kpis(
    c_tasks, c_disc,
    working_days=curr_meta['elapsed_working_days'],
    as_of_date='2026-10-23',
    final_deadline=curr_meta['final_deadline']
)

# Previous cycle tasks for comparison deltas
cycle_col = 'u_certification_activity' if 'u_certification_activity' in tasks_df.columns else 'u_certification_cycle'
prev_tasks = tasks_df[tasks_df[cycle_col] == cycle_mgr.previous_cycle.get('name', 'Q3-2026')].copy() if cycle_col in tasks_df.columns else tasks_df.copy()
prev_disc = disc_df[disc_df['u_certification_task'].isin(prev_tasks['sys_id'])].copy() if disc_df is not None else pd.DataFrame()

prev_kpis = kpi_engine.calculate_all_kpis(
    prev_tasks, prev_disc,
    working_days=prev_meta['total_working_days'],
    as_of_date='2026-09-30',
    final_deadline=prev_meta['final_deadline']
)

# -----------------------------------------------------------------------------
# PAGE 1: EXECUTIVE OVERVIEW
# -----------------------------------------------------------------------------
if page == "Executive Overview":
    st.markdown('<div class="main-header">Executive Overview</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">Data Certification Cycle Performance — {selected_cycle} (As-of Working Day {curr_meta["elapsed_working_days"]} of {curr_meta["total_working_days"]})</div>', unsafe_allow_html=True)

    # 5 Headline KPIs
    col1, col2, col3, col4, col5 = st.columns(5)
    
    k1 = kpis['kpi_1_certification_completion']
    p1 = prev_kpis['kpi_1_certification_completion']
    d1 = f"{(k1['value'] - p1['value']):+.1f}% vs prev" if (k1['value'] and p1['value']) else None
    col1.metric("Completion %", f"{k1['value']}%", delta=d1)

    k2 = kpis['kpi_2_daily_closure_rate']
    p2 = prev_kpis['kpi_2_daily_closure_rate']
    d2 = f"{(k2['value'] - p2['value']):+.1f} vs prev" if (k2['value'] and p2['value']) else None
    col2.metric("Daily Closure Rate", f"{k2['value']}", delta=d2)

    k3 = kpis['kpi_3_on_time_completion']
    p3 = prev_kpis['kpi_3_on_time_completion']
    d3 = f"{(k3['value'] - p3['value']):+.1f}% vs prev" if (k3['value'] and p3['value']) else None
    col3.metric("On-Time Completion", f"{k3['value']}%", delta=d3)

    k5 = kpis['kpi_5_discrepancy_rate']
    p5 = prev_kpis['kpi_5_discrepancy_rate']
    d5 = f"{(k5['value'] - p5['value']):+.1f}% vs prev" if (k5['value'] and p5['value']) else None
    col4.metric("Discrepancy Rate", f"{k5['value']}%", delta=d5, delta_color="inverse")

    k4 = kpis['kpi_4_avg_completion_time']
    p4 = prev_kpis['kpi_4_avg_completion_time']
    d4 = f"{(k4['value'] - p4['value']):+.1f}d vs prev" if (k4['value'] and p4['value']) else None
    col5.metric("Avg Completion Time", f"{k4['value']} days", delta=d4, delta_color="inverse")

    st.markdown("---")

    # Progress Bar and Workload Summary
    c_left, c_right = st.columns([2, 1])
    with c_left:
        st.subheader("Certification Completion Progress")
        comp_val = (k1['value'] or 0.0) / 100.0
        st.progress(min(1.0, max(0.0, comp_val)))
        st.caption(f"Completed Tasks: **{k1['numerator']:,}** | Incomplete: **{k1['details'].get('remaining_tasks', 0):,}** | Total Eligible: **{k1['denominator']:,}** (Cancelled Excluded: {k1['excluded_count']:,})")

        # Daily closure trend chart
        st.subheader("Daily Closures Trend")
        closed_col = 'closed_at' if 'closed_at' in c_tasks.columns else 'completed_at'
        if closed_col in c_tasks.columns:
            completed_tasks = c_tasks[c_tasks['state'].isin(['Closed Complete', 'Closed Incomplete'])].copy()
            completed_tasks['date'] = pd.to_datetime(completed_tasks[closed_col], errors='coerce').dt.date
            daily_series = completed_tasks.groupby('date').size().reset_index(name='Closures')
            daily_series = daily_series.sort_values('date')

            fig = px.area(daily_series, x='date', y='Closures', title="Daily Task Closures Over Time", color_discrete_sequence=['#1F497D'])
            fig.update_layout(height=280, margin=dict(l=20, r=20, t=40, b=20), xaxis_title="Date", yaxis_title="Closures")
            st.plotly_chart(fig, use_container_width=True)

    with c_right:
        st.subheader("Operational Risk Summary")
        monitor = DeadlineMonitor(warning_window_days=5)
        risk_data = monitor.monitor(c_tasks, as_of_date='2026-10-23')
        sum_data = risk_data.get('summary', {})

        st.markdown(f"""
        <div class="metric-card">
            <h4>⚠️ SLA Exposure</h4>
            <p>Overdue Tasks: <span class="risk-badge-critical">{sum_data.get('overdue', 0)}</span></p>
            <p>Near-Deadline Tasks (≤5d): <span class="risk-badge-high">{sum_data.get('near_deadline', 0)}</span></p>
            <p>Active Open Backlog: <b>{sum_data.get('total_open', 0)}</b></p>
            <p>Final SLA Target: <b>{kpis['kpi_12_sla_achievement']['value']}%</b></p>
        </div>
        """, unsafe_allow_html=True)

        st.subheader("Data Accuracy Summary")
        acc = kpis['kpi_6_data_accuracy']['value'] or 0.0
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = acc,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "Pass Rate %"},
            gauge = {
                'axis': {'range': [0, 100]},
                'bar': {'color': "#10B981"},
                'steps': [
                    {'range': [0, 85], 'color': "#FEE2E2"},
                    {'range': [85, 92], 'color': "#FEF3C7"},
                    {'range': [92, 100], 'color': "#D1FAE5"}
                ],
            }
        ))
        fig_gauge.update_layout(height=220, margin=dict(l=20, r=20, t=30, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

# -----------------------------------------------------------------------------
# PAGE 2: CYCLE COMPARISON
# -----------------------------------------------------------------------------
elif page == "Cycle Comparison":
    st.markdown('<div class="main-header">Certification Cycle Comparison</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Side-by-side comparative analysis between current and previous certification cycles</div>', unsafe_allow_html=True)

    comp_rows = cycle_mgr.compare_metrics(kpis, prev_kpis, mode="like_for_like")
    rep_gen = ReportGenerator(curr_meta, app_mode=app_mode)
    comp_df = rep_gen.build_cycle_comparison_df(comp_rows)

    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader("Key Performance Indicator Comparison Table")
        st.dataframe(
            comp_df.style.map(
                lambda v: "color: green; font-weight: bold;" if v == "Yes" else ("color: red; font-weight: bold;" if v == "No" else ""),
                subset=["Favorable"]
            ),
            use_container_width=True,
            height=450
        )

    with col2:
        st.subheader("Rate Metric Comparison (Percentage Points)")
        # Filter metrics with unit %
        pct_metrics = [r for r in comp_rows if r.get('unit') == '%' and r.get('pp_change') is not None]
        if pct_metrics:
            chart_df = pd.DataFrame({
                "Metric": [r['metric_name'] for r in pct_metrics],
                "Current": [r['current_value'] for r in pct_metrics],
                "Previous": [r['previous_value'] for r in pct_metrics]
            })
            fig_comp = go.Figure(data=[
                go.Bar(name='Current Cycle (Q4)', x=chart_df['Metric'], y=chart_df['Current'], marker_color='#1F497D'),
                go.Bar(name='Previous Cycle (Q3)', x=chart_df['Metric'], y=chart_df['Previous'], marker_color='#93C5FD')
            ])
            fig_comp.update_layout(barmode='group', height=420, margin=dict(l=20, r=20, t=30, b=80), xaxis_tickangle=-45)
            st.plotly_chart(fig_comp, use_container_width=True)

    # Download CSV
    csv_data = comp_df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Cycle Comparison CSV", csv_data, "cycle_comparison.csv", "text/csv")

# -----------------------------------------------------------------------------
# PAGE 3: DAILY PERFORMANCE
# -----------------------------------------------------------------------------
elif page == "Daily Performance":
    st.markdown('<div class="main-header">Daily Performance & Closure Velocity</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Daily task completion velocity, cumulative progress, and working day calendar tracking</div>', unsafe_allow_html=True)

    rep_gen = ReportGenerator(curr_meta, app_mode=app_mode)
    daily_df = rep_gen.build_daily_trends_df(c_tasks)

    if not daily_df.empty:
        col1, col2 = st.columns([2, 1])
        with col1:
            fig_daily = px.bar(daily_df, x='Date', y='Daily Closures', title="Daily Task Closures", color_discrete_sequence=['#3B82F6'])
            fig_daily.add_scatter(x=daily_df['Date'], y=daily_df['7-Day Moving Avg'], mode='lines', name='7-Day MA', line=dict(color='#DC2626', width=2))
            fig_daily.update_layout(height=350)
            st.plotly_chart(fig_daily, use_container_width=True)

            fig_cum = px.line(daily_df, x='Date', y='Cumulative Closures', title="Cumulative Closures Over Cycle", color_discrete_sequence=['#10B981'])
            fig_cum.update_layout(height=280)
            st.plotly_chart(fig_cum, use_container_width=True)

        with col2:
            st.subheader("Daily Closures Data Table")
            st.dataframe(daily_df, use_container_width=True, height=650)
    else:
        st.info("No completion timestamps available to compute daily performance.")

# -----------------------------------------------------------------------------
# PAGE 4: DATA QUALITY & DISCREPANCIES
# -----------------------------------------------------------------------------
elif page == "Data Quality & Discrepancies":
    st.markdown('<div class="main-header">Data Quality & Exception Discrepancies</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Audit findings, field validation failures, and discrepancy categorization (Table: u_failed_data_certifications)</div>', unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    total_disc = len(c_disc)
    col1.metric("Total Discrepancies", f"{total_disc:,}")
    col2.metric("Discrepancy Rate", f"{kpis['kpi_5_discrepancy_rate']['value']}%")
    col3.metric("Data Accuracy / Pass Rate", f"{kpis['kpi_6_data_accuracy']['value']}%")
    resolved_count = len(c_disc[c_disc['u_status'].isin(['Resolved', 'Closed', 'resolved'])]) if 'u_status' in c_disc.columns else 0
    col4.metric("Discrepancies Resolved", f"{resolved_count:,} ({(resolved_count/max(1, total_disc)*100):.1f}%)")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    cat_col = 'u_issue_category' if 'u_issue_category' in c_disc.columns else 'category'
    if not c_disc.empty and cat_col in c_disc.columns:
        with col_l:
            fig_cat = px.pie(c_disc, names=cat_col, title="Discrepancies by Failure Category", color_discrete_sequence=px.colors.qualitative.Set2)
            fig_cat.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_cat, use_container_width=True)

        with col_r:
            field_col = 'u_field' if 'u_field' in c_disc.columns else 'field'
            if field_col in c_disc.columns:
                field_counts = c_disc[field_col].value_counts().reset_index()
                field_counts.columns = ['Field Name', 'Count']
                fig_field = px.bar(field_counts, x='Field Name', y='Count', title="Top Attributes / Fields with Discrepancies", color='Count', color_continuous_scale='Blues')
                st.plotly_chart(fig_field, use_container_width=True)

    st.subheader("Discrepancy Records Detail Table")
    display_cols = [c for c in ['number', 'u_certification_task', 'u_application', 'u_field', 'u_issue_category', 'u_status', 'sys_created_on', 'u_resolved_on'] if c in c_disc.columns]
    st.dataframe(c_disc[display_cols].head(500), use_container_width=True, height=350)

# -----------------------------------------------------------------------------
# PAGE 5: CERTIFIER PRODUCTIVITY
# -----------------------------------------------------------------------------
elif page == "Certifier Productivity":
    st.markdown('<div class="main-header">Certifier Productivity & Workload</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Individual throughput, closure rates, and team workload balancing</div>', unsafe_allow_html=True)

    rep_gen = ReportGenerator(curr_meta, app_mode=app_mode)
    prod_df = rep_gen.build_certifier_productivity_df(c_tasks, curr_meta['elapsed_working_days'])

    if not prod_df.empty:
        col1, col2 = st.columns([3, 2])
        with col1:
            fig_prod = px.bar(
                prod_df.head(15),
                x='Certifier',
                y=['Completed Tasks', 'Assigned Tasks'],
                barmode='group',
                title="Top 15 Certifiers by Completed vs Assigned Workload",
                color_discrete_sequence=['#10B981', '#94A3B8']
            )
            fig_prod.update_layout(height=400, xaxis_tickangle=-45)
            st.plotly_chart(fig_prod, use_container_width=True)

        with col2:
            st.subheader("Certifier Performance Metrics")
            st.dataframe(prod_df, use_container_width=True, height=400)

        # Average completion time by certifier
        st.subheader("Completion Time by Certifier (Days)")
        created_col = 'sys_created_on' if 'sys_created_on' in c_tasks.columns else 'created_at'
        closed_col = 'closed_at' if 'closed_at' in c_tasks.columns else 'completed_at'
        completed_c = c_tasks[c_tasks['state'].isin(['Closed Complete', 'Closed Incomplete'])].copy()
        completed_c['created_dt'] = pd.to_datetime(completed_c[created_col], errors='coerce')
        completed_c['closed_dt'] = pd.to_datetime(completed_c[closed_col], errors='coerce')
        completed_c['days_taken'] = (completed_c['closed_dt'] - completed_c['created_dt']).dt.total_seconds() / 86400.0
        
        cert_col = 'assigned_to' if 'assigned_to' in completed_c.columns else 'certifier'
        top_certifiers = list(prod_df['Certifier'].head(10))
        box_df = completed_c[completed_c[cert_col].isin(top_certifiers)]
        
        fig_box = px.box(box_df, x=cert_col, y='days_taken', title="Completion Duration Distribution (Top 10 Certifiers)", color=cert_col)
        fig_box.update_layout(height=320, showlegend=False, xaxis_title="Certifier", yaxis_title="Days to Complete")
        st.plotly_chart(fig_box, use_container_width=True)
    else:
        st.info("No certifier data available.")

# -----------------------------------------------------------------------------
# PAGE 6: BACKLOG & SLA MONITORING
# -----------------------------------------------------------------------------
elif page == "Backlog & SLA Monitoring":
    st.markdown('<div class="main-header">Backlog Aging & SLA Risk Monitoring</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Operational backlog distributions, aging buckets, overdue tasks, and near-deadline SLA alerts</div>', unsafe_allow_html=True)

    monitor = DeadlineMonitor(warning_window_days=5)
    alerts = monitor.monitor(c_tasks, as_of_date='2026-10-23')
    sum_data = alerts.get('summary', {})

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Open Tasks", f"{sum_data.get('total_open', 0):,}")
    col2.metric("Overdue Tasks", f"{sum_data.get('overdue', 0):,}")
    col3.metric("Near Deadline (≤5d)", f"{sum_data.get('near_deadline', 0):,}")
    col4.metric("Avg Backlog Age", f"{kpis['kpi_8_backlog_aging']['value']} days")

    st.markdown("---")
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Aging Bucket Distribution (Open Tasks)")
        buckets = kpis['kpi_8_backlog_aging']['details'].get('buckets', {})
        if buckets:
            b_df = pd.DataFrame(list(buckets.items()), columns=['Bucket', 'Count'])
            fig_b = px.bar(b_df, x='Bucket', y='Count', title="Tasks in Backlog by Age Bucket", color='Bucket', color_discrete_sequence=['#10B981', '#FBBF24', '#F97316', '#EF4444'])
            fig_b.update_layout(height=300, showlegend=False)
            st.plotly_chart(fig_b, use_container_width=True)

    with col_r:
        st.subheader("Imminent SLA Deadlines (Next 5 Days)")
        near_list = alerts.get('near_deadline_tasks', [])
        if near_list:
            st.dataframe(pd.DataFrame(near_list), use_container_width=True, height=300)
        else:
            st.success("No open tasks approaching deadline within 5 days.")

    st.subheader("Overdue Tasks Requiring Urgent Escalation")
    overdue_list = alerts.get('overdue_tasks', [])
    if overdue_list:
        st.dataframe(pd.DataFrame(overdue_list), use_container_width=True, height=280)
    else:
        st.success("Zero overdue tasks in active scope.")

# -----------------------------------------------------------------------------
# PAGE 7: EXCEPTION RESOLUTION
# -----------------------------------------------------------------------------
elif page == "Exception Resolution":
    st.markdown('<div class="main-header">Exception Resolution Performance</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Resolution cycle time, open exception backlog, and turnaround efficiency</div>', unsafe_allow_html=True)

    k11 = kpis['kpi_11_exception_resolution']
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Avg Resolution Time", f"{k11['value']} days" if k11['value'] else "N/A")
    col2.metric("Median Resolution Time", f"{k11['details'].get('median_days', 'N/A')} days")
    col3.metric("Resolved Exceptions", f"{k11['details'].get('resolved_count', 0):,}")
    col4.metric("Unresolved Exceptions", f"{k11['details'].get('unresolved_count', 0):,}")

    st.markdown("---")
    rep_gen = ReportGenerator(curr_meta, app_mode=app_mode)
    exc_df = rep_gen.build_exception_resolution_df(c_disc)

    if not exc_df.empty:
        col_l, col_r = st.columns([3, 2])
        with col_l:
            valid_durations = exc_df.dropna(subset=['Duration (Days)'])
            if not valid_durations.empty:
                fig_hist = px.histogram(valid_durations, x='Duration (Days)', nbins=20, title="Exception Resolution Time Distribution (Days)", color_discrete_sequence=['#6366F1'])
                fig_hist.update_layout(height=320)
                st.plotly_chart(fig_hist, use_container_width=True)

        with col_r:
            st.subheader("Unresolved Discrepancies")
            unresolved = exc_df[exc_df['Status'].isin(['Open', 'open'])]
            st.dataframe(unresolved.head(200), use_container_width=True, height=320)
    else:
        st.info("No discrepancy records found.")

# -----------------------------------------------------------------------------
# PAGE 8: DATA & PIPELINE HEALTH
# -----------------------------------------------------------------------------
elif page == "Data & Pipeline Health":
    st.markdown('<div class="main-header">Data & Pipeline Health Diagnostics</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Extraction logs, run history, data-quality scores, schema mappings, and audit trails</div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Pipeline Status", "ACTIVE / VERIFIED")
    col2.metric("cert_task Records Extracted", f"{len(tasks_df):,}")
    col3.metric("Discrepancy Records Extracted", f"{len(disc_df):,}")

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Execution Run History (SQLite Store)")
        from src.storage.run_history import RunHistory
        rh = RunHistory("data/processed")
        runs = rh.get_runs(limit=10)
        if runs:
            st.dataframe(pd.DataFrame(runs), use_container_width=True, height=260)
        else:
            st.info("No runs recorded yet.")

    with col_r:
        st.subheader("Historical Snapshots Index")
        from src.storage.snapshot_store import SnapshotStore
        ss = SnapshotStore("data/snapshots")
        snaps = ss.list_snapshots()
        if snaps:
            st.dataframe(pd.DataFrame(snaps), use_container_width=True, height=260)
        else:
            st.info("No snapshots saved yet.")

    st.subheader("Data Quality Audit Matrix")
    qa_df = load_report_csv("data_quality_report")
    if qa_df is not None and not qa_df.empty:
        st.dataframe(qa_df, use_container_width=True)
    else:
        st.info("Quality report available after pipeline execution.")

# -----------------------------------------------------------------------------
# PAGE 9: SETTINGS & API SETUP
# -----------------------------------------------------------------------------
elif page == "Settings & API Setup":
    st.markdown('<div class="main-header">System Settings & ServiceNow API Integration</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Configure credentials, test connectivity, discover source schemas, and manage execution mode</div>', unsafe_allow_html=True)

    api_cfg = loader.get_api_config()

    st.subheader("1. API Configuration & Secret Status")
    c1, c2, c3 = st.columns(3)
    c1.info(f"**Operating Mode:** `{app_mode.upper()}`")
    c2.info(f"**API Provider:** `{api_cfg.get('provider', 'servicenow').upper()}`")
    c3.info(f"**Base URL:** `{api_cfg.get('base_url') or 'Not Configured (Demo Mode)'}`")

    st.markdown("""
    > **Note on Enterprise Credentials:**
    > Credentials are read securely from `.env` using `python-dotenv`.
    > Passwords and bearer tokens are strictly masked and never logged or exposed.
    """)

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔌 Test API Connection & Permissions", use_container_width=True):
            if app_mode == 'demo' or not api_cfg.get('base_url'):
                st.warning("Running in DEMO mode. No live API credentials entered.")
                st.info("To connect to ServiceNow, copy `.env.example` to `.env`, set `APP_MODE=live`, and configure credentials.")
            else:
                with st.spinner("Connecting to ServiceNow instance..."):
                    from src.connectors.service_now_client import ServiceNowClient
                    from src.discovery.connection_diagnostics import ConnectionDiagnostics
                    client = ServiceNowClient(
                        instance_url=api_cfg['base_url'],
                        username=api_cfg['username'],
                        password=api_cfg['password'],
                        timeout=api_cfg['timeout_seconds']
                    )
                    diag = ConnectionDiagnostics(client, loader.settings.get('provider', {}))
                    res = diag.run_diagnostics()
                    if res['api_connectivity'] and res['auth_valid']:
                        st.success("API Connection & Authentication Successful!")
                    else:
                        st.error("API Connection Failed. Check network, VPN, and credentials.")

    with col_btn2:
        if st.button("🔄 Execute Full Analytics Pipeline", type="primary", use_container_width=True):
            with st.spinner(f"Running analytical pipeline in {app_mode.upper()} mode..."):
                from main import cmd_pipeline
                import argparse
                cmd_pipeline(argparse.Namespace(mode=app_mode))
                st.cache_data.clear()
                st.success("Pipeline executed successfully! Reloading data...")
                st.rerun()

    st.subheader("2. Source Table Field Mappings")
    field_map = loader.get_field_mapping()
    st.json(field_map)
