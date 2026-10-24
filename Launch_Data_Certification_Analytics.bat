@echo off
title Data Certification KPI and Performance Analytics
cd /d "%~dp0"

echo ======================================================================
echo   DATA CERTIFICATION KPI ^& PERFORMANCE ANALYTICS
echo   Initializing application...
echo ======================================================================

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python is not found in system PATH.
    echo Please ensure Python 3.10+ is installed or configured in your corporate environment.
    echo.
    pause
    exit /b 1
)

python app_launcher.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application terminated with an error code: %errorlevel%
    pause
)
