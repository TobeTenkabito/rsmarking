param(
    [switch]$StopDocker,
    [switch]$NoPause
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RepoRoot "logs\launch"
$PidFile = Join-Path $LogDir "processes.json"

function Resolve-DockerComposeCommand {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        $oldErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            & $docker.Source compose version 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return @{
                    FilePath = $docker.Source
                    ArgsPrefix = @("compose")
                }
            }
        }
        finally {
            $ErrorActionPreference = $oldErrorActionPreference
        }
    }

    $dockerCompose = Get-Command docker-compose -ErrorAction SilentlyContinue
    if ($dockerCompose) {
        return @{
            FilePath = $dockerCompose.Source
            ArgsPrefix = @()
        }
    }

    throw "Docker Compose was not found."
}

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
        $compose = Resolve-DockerComposeCommand
        Push-Location (Join-Path $RepoRoot "infrastructure\docker")
        try {
            & $compose.FilePath @($compose.ArgsPrefix + @("down"))
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
