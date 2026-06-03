@echo off
echo Build Docker image...

cd executor_service\runtime

REM Build the worker runtime image.
docker build -t rs-worker-python:latest -f python_base.Dockerfile .

if %ERRORLEVEL% EQU 0 (
    echo Image built successfully!
    docker images | findstr rs-worker-python
) else (
    echo Image build failed!
    pause
    exit /b 1
)

cd ..\..
pause
