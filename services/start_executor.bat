@echo off
echo 检查Docker镜像...

docker images | findstr rs-worker-python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker镜像不存在，开始构建...
    call build_docker.bat
)

echo 启动执行服务 端口 8004...
cd executor_service
python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload
