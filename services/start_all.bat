@echo off
echo ========================================
echo   RSMarking 服务启动器
echo ========================================

REM 检查Docker是否运行
docker version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] Docker未运行，请先启动Docker Desktop
    pause
    exit /b 1
)

REM 构建Docker镜像（如果不存在）
docker images | findstr rs-worker-python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 构建Docker镜像...
    cd executor_service\runtime
    docker build -t rs-worker-python:latest -f python_base.Dockerfile .
    cd ..\..
)

echo.
echo 启动服务...
echo.

REM 启动数据服务（新窗口）
start "Data Service - Port 8002" cmd /k "cd data_service && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

REM 等待3秒
timeout /t 3 /nobreak >nul

REM 启动执行服务（新窗口）
start "Executor Service - Port 8004" cmd /k "cd executor_service && python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload"

echo.
echo ========================================
echo   服务已启动
echo ========================================
echo.
echo   数据服务: http://localhost:8002
echo   执行服务: http://localhost:8004
echo.
echo   按任意键退出此窗口（服务会继续运行）
echo ========================================
pause >nul
