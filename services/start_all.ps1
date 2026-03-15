# RSMarking 服务启动脚本 (PowerShell版本)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   RSMarking 服务启动器" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan

# 检查Docker是否运行
try {
    docker version | Out-Null
} catch {
    Write-Host "[错误] Docker未运行，请先启动Docker Desktop" -ForegroundColor Red
    Read-Host "按Enter键退出"
    exit 1
}

# 检查Python是否安装
try {
    python --version | Out-Null
} catch {
    Write-Host "[错误] Python未安装或未添加到PATH" -ForegroundColor Red
    Read-Host "按Enter键退出"
    exit 1
}

# 构建Docker镜像
$imageExists = docker images --format "{{.Repository}}" | Select-String "rs-worker-python"
if (-not $imageExists) {
    Write-Host "构建Docker镜像..." -ForegroundColor Yellow
    Set-Location "executor_service\runtime"
    docker build -t rs-worker-python:latest -f python_base.Dockerfile .
    Set-Location "..\.."
}

Write-Host "`n启动服务..." -ForegroundColor Green

# 启动数据服务
$dataJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\data_service
    python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
}

# 启动执行服务
$executorJob = Start-Job -ScriptBlock {
    Set-Location $using:PWD\executor_service
    python -m uvicorn main:app --host 0.0.0.0 --port 8004 --reload
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   服务已启动" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "   数据服务: " -NoNewline; Write-Host "http://localhost:8002" -ForegroundColor Yellow
Write-Host "   执行服务: " -NoNewline; Write-Host "http://localhost:8004" -ForegroundColor Yellow
Write-Host ""
Write-Host "   按 Ctrl+C 停止所有服务" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan

# 等待用户中断
try {
    while ($true) {
        Start-Sleep -Seconds 1

        # 检查服务状态
        if ($dataJob.State -eq "Failed") {
            Write-Host "[警告] 数据服务已停止" -ForegroundColor Red
        }
        if ($executorJob.State -eq "Failed") {
            Write-Host "[警告] 执行服务已停止" -ForegroundColor Red
        }
    }
} finally {
    # 清理
    Write-Host "`n停止服务..." -ForegroundColor Yellow
    Stop-Job $dataJob, $executorJob
    Remove-Job $dataJob, $executorJob
}
