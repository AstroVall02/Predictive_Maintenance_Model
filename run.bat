@echo off
setlocal enabledelayedexpansion

title Predictive Maintenance System
cd /d "%~dp0"

echo ======================================================================
echo       Predictive Maintenance ML System - Medical Infrastructure
echo ======================================================================
echo.

:: 1. Detect Python
where python >nul 2>nul
if %ERRORLEVEL% equ 0 (
    set "PY_CMD=python"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% equ 0 (
        set "PY_CMD=py"
    ) else (
        echo [ERROR] Python was not found on your system PATH.
        echo Please install Python 3.10+ and ensure "Add Python to PATH" is checked.
        echo.
        pause
        exit /b 1
    )
)

:: 2. Check and activate virtual environment if present
if exist "%~dp0.venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment: .venv
    call "%~dp0.venv\Scripts\activate.bat"
    set "PY_CMD=python"
) else if exist "%~dp0venv\Scripts\activate.bat" (
    echo [*] Activating virtual environment: venv
    call "%~dp0venv\Scripts\activate.bat"
    set "PY_CMD=python"
)

:: 3. Verify core dependencies
echo [*] Checking dependencies...
!PY_CMD! -c "import flask, sklearn, joblib, pandas, numpy" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Required packages missing. Installing from requirements.txt...
    !PY_CMD! -m pip install -r "%~dp0requirements.txt"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies. Please run 'pip install -r requirements.txt' manually.
        pause
        exit /b 1
    )
)

:: 4. Verify dataset, model, and database prerequisites
if not exist "%~dp0data\telemetry_dataset.csv" (
    echo [*] Dataset not found. Generating synthetic telemetry data...
    cd /d "%~dp0data"
    !PY_CMD! generate_data.py
    cd /d "%~dp0"
)

if not exist "%~dp0models\rul_model.pkl" (
    echo [*] Model file not found. Training RUL model...
    cd /d "%~dp0app"
    !PY_CMD! ml_model.py
    cd /d "%~dp0"
)

if not exist "%~dp0predictive_maintenance.db" (
    echo [*] Database not found. Initializing schema and seed data...
    cd /d "%~dp0app"
    !PY_CMD! database.py
    cd /d "%~dp0"
)

:: 5. Launch application
echo.
echo ======================================================================
echo   Server URL : http://127.0.0.1:5000
echo.
echo   Demo Login Accounts:
echo     - IoT Engineer       : iot_engineer / iot123
echo     - Biomedical Manager : manager / mgr123
echo     - Technician         : (Select technician name from dropdown)
echo.
echo   Press Ctrl+C in this console to stop the server.
echo ======================================================================
echo.

:: Launch browser in background after short delay
start "" cmd /c "ping -n 3 127.0.0.1 >nul & start http://127.0.0.1:5000"

:: Start the Flask web app
cd /d "%~dp0app"
!PY_CMD! app.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Server exited with code %ERRORLEVEL%.
    pause
)
