@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"
title Co Vua Online Server

echo ==========================================
echo        CO VUA ONLINE - AUTO RUN
echo ==========================================
echo Project folder: %cd%
echo.

set SERVER_IP=101.103.113.70
set SERVER_PORT=8002
set PYTHON_CMD=
set VENV_READY=0
set CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe

REM 1. Check project files
if not exist "main.py" (
    echo [ERROR] Cannot find main.py in this folder.
    echo Put StartServer.bat in the same folder as main.py.
    pause
    exit /b 1
)

if not exist "requirements.txt" (
    echo [ERROR] Cannot find requirements.txt in this folder.
    pause
    exit /b 1
)

REM 2. Use existing venv if it works
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" --version >nul 2>nul
    if not errorlevel 1 (
        set VENV_READY=1
    ) else (
        echo [WARN] Existing venv is broken or points to a missing Python install.
        call :FindPython

        if "!PYTHON_CMD!"=="" (
            echo [ERROR] Python is not installed or not available.
            echo Install Python 3.10 or newer and enable "Add Python to PATH".
            pause
            exit /b 1
        )

        set BROKEN_VENV=venv_broken_!RANDOM!
        echo [INFO] Renaming broken venv to !BROKEN_VENV!...
        ren "venv" "!BROKEN_VENV!"

        if errorlevel 1 (
            echo [ERROR] Failed to rename broken venv.
            echo Close any terminal using this folder and try again.
            pause
            exit /b 1
        )
    )
)

if "%VENV_READY%"=="0" (
    if "!PYTHON_CMD!"=="" call :FindPython

    if "!PYTHON_CMD!"=="" (
        echo [ERROR] Python is not installed or not available.
        echo Install Python 3.10 or newer and enable "Add Python to PATH".
        pause
        exit /b 1
    )

    echo [INFO] Creating venv...
    !PYTHON_CMD! -m venv venv

    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
)

REM 3. Activate venv
echo [INFO] Activating venv...
call "venv\Scripts\activate.bat"

if errorlevel 1 (
    echo [ERROR] Failed to activate venv.
    pause
    exit /b 1
)

REM 4. Install libraries
echo [INFO] Installing build tools...
python -m pip install setuptools wheel --no-cache-dir

if errorlevel 1 (
    echo [ERROR] Failed to install build tools.
    pause
    exit /b 1
)

echo [INFO] Installing libraries from requirements.txt...
python -m pip install -r requirements.txt --no-build-isolation --no-cache-dir

if errorlevel 1 (
    echo [ERROR] Failed to install libraries.
    pause
    exit /b 1
)

if "%SKIP_LAUNCH%"=="1" (
    echo [INFO] SKIP_LAUNCH is set. Backend and browser launch skipped.
    goto Done
)

REM 5. Start backend in a new window
echo [INFO] Starting backend FastAPI at http://%SERVER_IP%:%SERVER_PORT%
start "Co Vua Backend" cmd /k "cd /d ""%cd%"" && call venv\Scripts\activate.bat && python -m uvicorn main:app --host 0.0.0.0 --port %SERVER_PORT% --reload"

REM 6. Open frontend
if exist "index.html" (
    echo [INFO] Opening frontend at http://%SERVER_IP%:%SERVER_PORT%/ui
    timeout /t 3 >nul
    start http://%SERVER_IP%:%SERVER_PORT%/ui
) else (
    echo [WARN] Cannot find index.html. Opening Swagger docs only.
    timeout /t 3 >nul
    start http://%SERVER_IP%:%SERVER_PORT%/docs
)

echo.
echo ==========================================
echo Done.
echo Backend: http://%SERVER_IP%:%SERVER_PORT%
echo Swagger: http://%SERVER_IP%:%SERVER_PORT%/docs
echo Frontend: http://%SERVER_IP%:%SERVER_PORT%/ui
echo ==========================================
echo.
:Done
echo You can close this window, but keep the Backend window open while using the app.
pause
exit /b 0

:FindPython
set PYTHON_CMD=

where python >nul 2>nul
if not errorlevel 1 (
    python --version >nul 2>nul
    if not errorlevel 1 (
        set PYTHON_CMD=python
        exit /b 0
    )
)

where py >nul 2>nul
if not errorlevel 1 (
    py -3 --version >nul 2>nul
    if not errorlevel 1 (
        set PYTHON_CMD=py -3
        exit /b 0
    )
)

if exist "%CODEX_PYTHON%" (
    "%CODEX_PYTHON%" --version >nul 2>nul
    if not errorlevel 1 (
        set "PYTHON_CMD=%CODEX_PYTHON%"
        exit /b 0
    )
)

exit /b 0
