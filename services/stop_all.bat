@echo off
echo Stopping all services...

REM Terminate Python processes
taskkill /F /IM python.exe /T 2>nul

REM Stop all related Docker containers
for /f "tokens=*" %%i in ('docker ps -q --filter "ancestor=rs-worker-python:latest"') do docker stop %%i

echo Services stopped
pause
