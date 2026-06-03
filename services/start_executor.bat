@echo off
echo Checking Docker image...

docker images | findstr rs-worker-python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker image does not exist,starting build...
    call build_docker.bat
)

echo Starting executor service on port 8004...
cd executor_service
python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload
