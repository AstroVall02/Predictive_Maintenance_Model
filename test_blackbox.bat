@echo off
setlocal enabledelayedexpansion

title Predictive Maintenance - Black-Box Tests (Selenium)
cd /d "%~dp0"

echo ======================================================================
echo         Predictive Maintenance - Black-Box Testing (Selenium)
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

:: 3. Check for selenium and pytest
echo [*] Checking testing dependencies: selenium, pytest...
!PY_CMD! -c "import pytest, selenium" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] Installing missing testing packages: selenium, pytest...
    !PY_CMD! -m pip install pytest selenium
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install test dependencies.
        pause
        exit /b 1
    )
)

:: 4. Verify database and model files exist
if not exist "%~dp0data\telemetry_dataset.csv" (
    echo [*] Generating synthetic telemetry data...
    pushd "%~dp0data"
    !PY_CMD! generate_data.py
    popd
)

if not exist "%~dp0models\rul_model.pkl" (
    echo [*] Model file missing. Training RUL model...
    pushd "%~dp0app"
    !PY_CMD! ml_model.py
    popd
)

if not exist "%~dp0predictive_maintenance.db" (
    echo [*] Initializing database...
    pushd "%~dp0app"
    !PY_CMD! database.py
    popd
)

:: 5. Check if Flask server is already running
set "AUTO_STARTED_SERVER=0"
!PY_CMD! -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=1)" >nul 2>nul
if %ERRORLEVEL% equ 0 goto :server_already_running

echo [*] Flask application is not running. Starting background test server...
set "AUTO_STARTED_SERVER=1"
pushd "%~dp0app"
start "FlaskTestServer" /min !PY_CMD! app.py
popd

echo [*] Waiting for Flask server to initialize...
for /L %%i in (1,1,12) do (
    ping -n 2 127.0.0.1 >nul
    !PY_CMD! -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/login', timeout=1)" >nul 2>nul
    if not errorlevel 1 goto :server_ready
)

echo.
echo [ERROR] Flask server could not be started automatically.
echo Please run 'run.bat' in a separate terminal window first, then run this script.
echo.
pause
exit /b 1

:server_already_running
echo [*] Flask application is already running on http://127.0.0.1:5000.

:server_ready
echo [*] Flask server is ready!

:: 6. Run Selenium Black-Box Tests
echo.
echo [*] Running black-box tests with Selenium Chrome WebDriver...
echo.
!PY_CMD! -m pytest "%~dp0tests\test_black_box.py" -v %*
set "TEST_EXIT_CODE=%ERRORLEVEL%"

:: 7. Clean up background server if we launched it
if not "!AUTO_STARTED_SERVER!"=="1" goto :skip_cleanup
echo.
echo [*] Shutting down background test server on port 5000...
taskkill /FI "WINDOWTITLE eq FlaskTestServer*" /T /F >nul 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000" ^| findstr "LISTENING"') do taskkill /f /t /pid %%a >nul 2>nul

:skip_cleanup
echo.
echo ======================================================================
if %TEST_EXIT_CODE% equ 0 (
    echo   [SUCCESS] All black-box test cases PASSED.
) else (
    echo   [FAILURE] Some black-box test cases failed with exit code %TEST_EXIT_CODE%.
)
echo ======================================================================
echo.
pause
exit /b %TEST_EXIT_CODE%
