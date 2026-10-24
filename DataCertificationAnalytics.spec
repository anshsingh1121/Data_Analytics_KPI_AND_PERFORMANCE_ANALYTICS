# -*- mode: python ; coding: utf-8 -*-
import os
import pathlib
import streamlit
from PyInstaller.utils.hooks import copy_metadata, collect_data_files, collect_submodules

streamlit_dir = pathlib.Path(streamlit.__file__).parent

datas = [
    (str(streamlit_dir / "static"), "streamlit/static"),
    ("config", "config"),
    ("src", "src"),
    ("main.py", "."),
]

# Ensure streamlit, plotly, openpyxl, pandas metadata are packaged
datas += copy_metadata("streamlit")
datas += copy_metadata("openpyxl")
datas += copy_metadata("plotly")
datas += copy_metadata("pandas")

hiddenimports = [
    "streamlit",
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner.magic_expressions",
    "openpyxl",
    "plotly",
    "pandas",
    "requests",
    "yaml",
    "src",
    "src.config.loader",
    "src.config.validation",
    "src.connectors.servicenow_client",
    "src.connectors.ssl_helper",
    "src.discovery.connection_diagnostics",
    "src.discovery.schema_discovery",
    "src.data_processing.normalizer",
    "src.data_processing.validator",
    "src.data_processing.relationships",
    "src.data_processing.quality_checks",
    "src.analytics.kpi_engine",
    "src.analytics.cycle_manager",
    "src.analytics.trend_analysis",
    "src.analytics.backlog_analysis",
    "src.analytics.productivity_analysis",
    "src.analytics.exception_analysis",
    "src.storage.snapshot_store",
    "src.storage.run_history",
    "src.reporting.report_generator",
    "src.reporting.csv_exporter",
    "src.reporting.excel_exporter",
    "src.scheduler.deadline_monitor",
]

hiddenimports += collect_submodules("streamlit")
hiddenimports += collect_submodules("plotly")

a = Analysis(
    ['run_app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'scipy', 'IPython', 'notebook'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DataCertificationAnalytics',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DataCertificationAnalytics',
)
