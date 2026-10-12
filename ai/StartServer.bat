@echo off
setlocal

cd /d "%~dp0"
title OCR API Runner

echo ==========================================
echo        OCR API - AUTO RUN
echo ==========================================
echo Project folder: %cd%
echo.

set SERVER_IP=101.103.113.70
set BACKEND_HOST=0.0.0.0

REM 1. Kiem tra Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Khong tim thay Python.
    echo Hay cai Python 3.10 hoac 3.11 va tick "Add Python to PATH".
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

REM 3.1. Tao lai virtual environment neu venv cu bi hong
"venv\Scripts\python.exe" --version >nul 2>nul
if errorlevel 1 (
    echo [WARN] Venv hien tai bi loi. Dang tao lai...
    python -m venv --clear venv

    if errorlevel 1 (
        echo [ERROR] Tao lai venv that bai.
        pause
        exit /b 1
    )
)

REM 4. Bat venv
echo [INFO] Dang activate venv...
call "venv\Scripts\activate.bat"
set FLAGS_use_mkldnn=0
set FLAGS_enable_pir_in_executor=0
set PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=0

REM 5. Cai thu vien neu co requirements.txt
echo [INFO] Dang nang cap pip...
python -m pip install --upgrade pip

if errorlevel 1 (
    echo [ERROR] Nang cap pip that bai.
    pause
    exit /b 1
)

if exist "requirements.txt" (
    echo [INFO] Dang cai thu vien tu requirements.txt...
    python -m pip install -r requirements.txt

    if errorlevel 1 (
        echo [ERROR] Cai thu vien that bai.
        pause
        exit /b 1
    )
) else (
    echo [WARN] Khong co requirements.txt.
    echo [INFO] Dang cai cac thu vien can thiet...
    python -m pip install fastapi uvicorn[standard] python-multipart numpy opencv-python-headless paddleocr paddlepaddle==3.2.2

    if errorlevel 1 (
        echo [ERROR] Cai thu vien that bai.
        pause
        exit /b 1
    )
)

REM 6. Chay backend API o cua so rieng
echo [INFO] Dang start backend FastAPI tai http://%SERVER_IP%:8000
start "OCR Backend API" cmd /k "cd /d "%cd%" && call venv\Scripts\activate.bat && set FLAGS_use_mkldnn=0 && set FLAGS_enable_pir_in_executor=0 && set PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT=0 && python -m uvicorn main:app --host %BACKEND_HOST% --port 8000 --reload"

REM 7. Neu co index.html thi mo frontend do FastAPI phuc vu tai /ui
if exist "index.html" (
    echo [INFO] Tim thay index.html. Dang mo frontend tai http://%SERVER_IP%:8000/ui
    timeout /t 3 >nul
    start http://%SERVER_IP%:8000/ui
) else (
    echo [WARN] Khong tim thay index.html. Chi mo Swagger docs.
    timeout /t 3 >nul
    start http://%SERVER_IP%:8000/docs
)

echo.
echo ==========================================
echo Da chay xong.
echo Backend: http://%SERVER_IP%:8000
echo Swagger: http://%SERVER_IP%:8000/docs
echo Frontend: http://%SERVER_IP%:8000/ui
echo ==========================================
echo.
echo Co the dong cua so nay, nhung dung dong cua so Backend neu dang dung app.
pause
