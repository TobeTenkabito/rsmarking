# RSMarking service startup script (PowerShell version)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   RSMarking service launcher" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

# Check whether Docker is running
try {
    docker version | Out-Null
} catch {
    Write-Host "[Error] Docker is not running. Start Docker Desktop first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Check whether Python is installed
try {
    python --version | Out-Null
} catch {
    Write-Host "[Error] Python is not installed or not on PATH" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Build Docker image
$imageExists = docker images --format "{{.Repository}}" | Select-String "rs-worker-python"
if (-not $imageExists) {
    Write-Host "Build Docker image..." -ForegroundColor Yellow
    Set-Location "executor_service\runtime"
    docker build -t rs-worker-python:latest -f python_base.Dockerfile .
    Set-Location "..\.."
}

Write-Host "`nStarting services..." -ForegroundColor Green

# Start data service
$dataJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\data_service
    python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
}

# Start executor service
$executorJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\executor_service
    python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   Services started" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "   Data service: " -NoNewline; Write-Host "http://localhost:8002" -ForegroundColor Yellow
Write-Host "   Executor service: " -NoNewline; Write-Host "http://localhost:8004" -ForegroundColor Yellow
Write-Host ""
Write-Host "   Press Ctrl+C to stop all services" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

# Wait for user interruption
try {
    while ($true) {
        Start-Sleep -Seconds 1

        # Check service status
        if ($dataJob.State -eq "Failed") {
            Write-Host "[Warning] Data service has stopped" -ForegroundColor Red
        }
        if ($executorJob.State -eq "Failed") {
            Write-Host "[Warning] Executor service has stopped" -ForegroundColor Red
        }
    }
} finally {
    # Cleanup
    Write-Host "`nStopping services..." -ForegroundColor Yellow
    Stop-Job $dataJob, $executorJob
    Remove-Job $dataJob, $executorJob
}
