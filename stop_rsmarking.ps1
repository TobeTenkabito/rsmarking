param(
    [switch]$StopDocker,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RepoRoot "logs\launch"
$PidFile = Join-Path $LogDir "processes.json"

try {
    if (Test-Path $PidFile) {
        $items = Get-Content $PidFile -Raw | ConvertFrom-Json
        foreach ($item in @($items)) {
            $proc = Get-Process -Id $item.Pid -ErrorAction SilentlyContinue
            if ($proc) {
                Write-Host "Stopping $($item.Name) pid=$($item.Pid)" -ForegroundColor Yellow
                & taskkill /PID $item.Pid /T /F | Out-Null
            }
        }
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
    else {
        Write-Host "No tracked RSMarking processes were found." -ForegroundColor Yellow
    }

    if ($StopDocker) {
        Write-Host "Stopping Docker infrastructure" -ForegroundColor Yellow
        Push-Location (Join-Path $RepoRoot "infrastructure\docker")
        try {
            docker compose down
        }
        finally {
            Pop-Location
        }
    }

    Write-Host "RSMarking stop complete." -ForegroundColor Green
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    if (-not $NoPause) {
        Read-Host "Press Enter to exit"
    }
    exit 1
}

if (-not $NoPause) {
    Read-Host "Press Enter to exit"
}
