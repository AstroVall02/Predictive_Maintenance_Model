@echo off
setlocal enabledelayedexpansion

title Predictive Maintenance - White-Box Tests (pytest)
cd /d "%~dp0"

echo ======================================================================
echo          Predictive Maintenance - White-Box Testing (pytest)
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

:: 3. Verify pytest is installed
!PY_CMD! -m pytest --version >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [!] pytest is not installed. Installing pytest...
    !PY_CMD! -m pip install pytest
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install pytest.
        pause
        exit /b 1
    )
)

:: 4. Verify model exists (used by predict/analyse tests)
if not exist "%~dp0models\rul_model.pkl" (
    echo [*] Model file missing. Training model for tests...
    if not exist "%~dp0data\telemetry_dataset.csv" (
        cd /d "%~dp0data"
        !PY_CMD! generate_data.py
        cd /d "%~dp0"
    )
    cd /d "%~dp0app"
    !PY_CMD! ml_model.py
    cd /d "%~dp0"
)

:: 5. Run pytest
echo [*] Running white-box tests in tests/test_white_box.py...
echo.
!PY_CMD! -m pytest "%~dp0tests\test_white_box.py" -v %*

set "TEST_EXIT_CODE=%ERRORLEVEL%"
echo.
echo ======================================================================
if %TEST_EXIT_CODE% equ 0 (
    echo   [SUCCESS] All white-box test cases PASSED.
) else (
    echo   [FAILURE] Some test cases failed with exit code %TEST_EXIT_CODE%.
)
echo ======================================================================
echo.
pause
exit /b %TEST_EXIT_CODE%
