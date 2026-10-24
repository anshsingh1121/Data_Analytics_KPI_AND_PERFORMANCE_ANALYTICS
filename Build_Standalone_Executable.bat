@echo off
title Build Data Certification Analytics Standalone Application
cd /d "%~dp0"

echo ======================================================================
echo   DATA CERTIFICATION KPI & PERFORMANCE ANALYTICS
echo   Building Standalone Executable (.exe) Application...
echo ======================================================================
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is required on the build machine to create the executable.
    pause
    exit /b 1
)

python build_standalone_exe.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build encountered an issue.
    pause
    exit /b %errorlevel%
)

echo.
echo Build complete. Press any key to close this window...
pause >nul
