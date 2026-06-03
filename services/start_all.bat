@echo off
echo ========================================
echo   RSMarking service launcher
echo ========================================

REM Check whether Docker is running
docker version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [Error] Docker is not running. Start Docker Desktop first.
    pause
    exit /b 1
)

REM Build Docker image if missing
docker images | findstr rs-worker-python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Build Docker image...
    cd executor_service\runtime
    docker build -t rs-worker-python:latest -f python_base.Dockerfile .
    cd ..\..
)

echo.
echo Starting services...
echo.

REM Start data service in a new window
start "Data Service - Port 8002" cmd /k "cd data_service && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

REM Wait 3 seconds
timeout /t 3 /nobreak >nul

REM Start executor service in a new window
start "Executor Service - Port 8004" cmd /k "cd executor_service && python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload"

echo.
echo ========================================
echo   Services started
echo ========================================
echo.
echo   Data service: http://localhost:8002
echo   Executor service: http://localhost:8004
echo.
echo   Press any key to exit this window (services will continue running)
echo ========================================
pause >nul
