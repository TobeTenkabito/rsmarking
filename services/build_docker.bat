@echo off
echo 构建Docker镜像...

cd executor_service\runtime

REM 构建镜像
docker build -t rs-worker-python:latest -f python_base.Dockerfile .

if %ERRORLEVEL% EQU 0 (
    echo 镜像构建成功！
    docker images | findstr rs-worker-python
) else (
    echo 镜像构建失败！
    pause
    exit /b 1
)

cd ..\..
pause
