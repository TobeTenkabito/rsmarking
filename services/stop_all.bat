@echo off
echo 停止所有服务...

REM 终止Python进程
taskkill /F /IM python.exe /T 2>nul

REM 停止所有相关Docker容器
for /f "tokens=*" %%i in ('docker ps -q --filter "ancestor=rs-worker-python:latest"') do docker stop %%i

echo 服务已停止
pause
