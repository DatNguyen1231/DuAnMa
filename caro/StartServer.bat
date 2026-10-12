@echo off
setlocal

cd /d "%~dp0"
title Caro Online Server

echo ==========================================
echo        CARO ONLINE - AUTO RUN
echo ==========================================
echo Project folder: %cd%
echo.

set SERVER_IP=101.103.113.70
set SERVER_PORT=8001

REM 1. Kiem tra Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Khong tim thay Python.
    echo Hay cai Python 3.10 hoac moi hon va tick "Add Python to PATH".
    pause
    exit /b 1
)

REM 2. Kiem tra main.py
if not exist "main.py" (
    echo [ERROR] Khong tim thay file main.py trong thu muc nay.
    echo Hay dat file StartServer.bat cung thu muc voi main.py.
    pause
    exit /b 1
)

REM 3. Tao virtual environment neu chua co
if not exist "venv\Scripts\python.exe" (
    echo [INFO] Chua co venv. Dang tao moi...
    python -m venv venv

    if errorlevel 1 (
        echo [ERROR] Tao venv that bai.
        pause
        exit /b 1
    )
)

REM 4. Bat venv
echo [INFO] Dang activate venv...
call "venv\Scripts\activate.bat"

REM 5. Cai thu vien
echo [INFO] Dang nang cap pip...
python -m pip install --upgrade pip

if errorlevel 1 (
    echo [ERROR] Nang cap pip that bai.
    pause
    exit /b 1
)

echo [INFO] Dang cai thu vien tu requirements.txt...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo [ERROR] Cai thu vien that bai.
    pause
    exit /b 1
)

REM 6. Chay backend API o cua so rieng
echo [INFO] Dang start backend FastAPI tai http://%SERVER_IP%:%SERVER_PORT%
start "Caro Backend" cmd /k "cd /d ""%cd%"" && call venv\Scripts\activate.bat && python -m uvicorn main:app --host 0.0.0.0 --port %SERVER_PORT% --reload"

REM 7. Mo frontend
if exist "index.html" (
    echo [INFO] Dang mo frontend tai http://%SERVER_IP%:%SERVER_PORT%/ui
    timeout /t 3 >nul
    start http://%SERVER_IP%:%SERVER_PORT%/ui
) else (
    echo [WARN] Khong tim thay index.html. Chi mo Swagger docs.
    timeout /t 3 >nul
    start http://%SERVER_IP%:%SERVER_PORT%/docs
)

echo.
echo ==========================================
echo Da chay xong.
echo Backend: http://%SERVER_IP%:%SERVER_PORT%
echo Swagger: http://%SERVER_IP%:%SERVER_PORT%/docs
echo Frontend: http://%SERVER_IP%:%SERVER_PORT%/ui
echo ==========================================
echo.
echo Co the dong cua so nay, nhung dung dong cua so Backend neu dang dung app.
pause
