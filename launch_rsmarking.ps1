param(
    [string]$CondaEnv = "rsmarking",
    [string]$PythonCommand = "python",
    [switch]$SkipDocker,
    [switch]$SkipMigrations,
    [switch]$SkipExecutorImage,
    [switch]$RequireExecutorImage,
    [switch]$Reload,
    [switch]$VisibleLogs,
    [switch]$AllowInlineFallback,
    [switch]$NoBrowser,
    [switch]$NoPause,
    [int]$ExecutorImageBuildRetries = 1,
    [int]$DockerStartupTimeoutSeconds = 180
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$LogDir = Join-Path $RepoRoot "logs\launch"
$PidFile = Join-Path $LogDir "processes.json"

$RequiredPythonModules = @(
    "fastapi",
    "uvicorn",
    "celery",
    "redis",
    "sqlalchemy",
    "alembic",
    "rasterio",
    "psycopg2"
)

$Services = @(
    @{ Name = "annotation_service"; Port = 8001; App = "services.annotation_service.main:app" },
    @{ Name = "data_service";       Port = 8002; App = "services.data_service.main:app" },
    @{ Name = "vtile_service";      Port = 8003; App = "services.vtile_service.main:app" },
    @{ Name = "executor_service";   Port = 8004; App = "services.executor_service.main:app" },
    @{ Name = "tile_service";       Port = 8005; App = "services.tile_service.main:app" },
    @{ Name = "ai_gateway";         Port = 8006; App = "services.ai_gateway.main:app" }
)

function Write-Step($Message) {
    Write-Host "[*] $Message" -ForegroundColor Cyan
}

function Write-Ok($Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warn($Message) {
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Fail($Message) {
    throw $Message
}

function Invoke-Checked {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory = $RepoRoot,
        [switch]$AllowFailure,
        [switch]$SuppressOutput
    )

    Push-Location $WorkingDirectory
    $oldErrorActionPreference = $ErrorActionPreference

    try {
        # Important:
        # Some native commands, especially Docker Compose v2, write normal progress/status
        # messages to stderr. With $ErrorActionPreference = "Stop", PowerShell can treat
        # those stderr records as terminating errors even when the native command exits 0.
        # Temporarily relax it while invoking native commands.
        $ErrorActionPreference = "Continue"

        $output = & $FilePath @ArgumentList 2>&1
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
        Pop-Location
    }

    if (-not $SuppressOutput -and $output) {
        $output | ForEach-Object { Write-Host $_ }
    }

    if ($exitCode -ne 0 -and -not $AllowFailure) {
        $outText = if ($output) { $output -join "`n" } else { "" }
        Fail "Command failed with exit code ${exitCode}: $FilePath $($ArgumentList -join ' ')`n$outText"
    }

    return $exitCode
}

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
                    Label = "docker compose"
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
            Label = "docker-compose"
        }
    }

    Fail "Docker Compose was not found. Install Docker Desktop or docker-compose."
}

function Test-DockerRunning {
    $oldErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        docker version 2>&1 | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    catch {
        return $false
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }
}

function Start-DockerDesktopIfNeeded {
    if (Test-DockerRunning) {
        Write-Ok "Docker is running"
        return
    }

    $candidates = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Docker\Docker Desktop.exe"
    ) | Where-Object { $_ -and (Test-Path $_) }

    if ($candidates.Count -gt 0) {
        Write-Step "Starting Docker Desktop"
        Start-Process -FilePath $candidates[0] | Out-Null
    }
    else {
        Write-Warn "Docker is not running and Docker Desktop executable was not found automatically."
    }

    $deadline = (Get-Date).AddSeconds($DockerStartupTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerRunning) {
            Write-Ok "Docker is running"
            return
        }
        Start-Sleep -Seconds 3
    }

    Fail "Docker did not become available within $DockerStartupTimeoutSeconds seconds."
}

function Invoke-DockerComposeUp {
    param(
        [string]$WorkingDirectory
    )

    $compose = Resolve-DockerComposeCommand

    Push-Location $WorkingDirectory
    $oldErrorActionPreference = $ErrorActionPreference

    try {
        $ErrorActionPreference = "Continue"

        $output = & $compose.FilePath @($compose.ArgsPrefix + @("up", "-d")) 2>&1
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
        Pop-Location
    }

    if ($output) {
        $output | ForEach-Object { Write-Host $_ }
    }

    if ($exitCode -ne 0) {
        $outText = if ($output) { $output -join "`n" } else { "" }
        Fail "docker compose up -d failed with exit code $exitCode`n$outText"
    }
}

function Test-PythonLauncher {
    param(
        [hashtable]$Launcher,
        [string[]]$Modules
    )

    $moduleList = "'" + ($Modules -join "','") + "'"
    $script = "import importlib.util, sys; missing=[m for m in [$moduleList] if importlib.util.find_spec(m) is None]; print('missing=' + ','.join(missing) if missing else 'ok'); sys.exit(1 if missing else 0)"
    $args = @($Launcher.ArgsPrefix) + @("-c", $script)

    Push-Location $RepoRoot
    $oldErrorActionPreference = $ErrorActionPreference

    try {
        $ErrorActionPreference = "Continue"
        $output = & $Launcher.FilePath @args 2>&1
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
        Pop-Location
    }

    return @{
        Ok = ($exitCode -eq 0)
        Output = ($output -join "`n")
    }
}

function Resolve-CondaPythonExecutable {
    param(
        [string]$CondaCommand,
        [string]$EnvName
    )

    $oldErrorActionPreference = $ErrorActionPreference

    try {
        $ErrorActionPreference = "Continue"
        $output = & $CondaCommand run --no-capture-output -n $EnvName python -c "import sys; print(sys.executable)" 2>&1
        if ($LASTEXITCODE -eq 0) {
            foreach ($line in $output) {
                $candidate = "$line".Trim()
                if ($candidate -and (Test-Path $candidate) -and ([IO.Path]::GetFileName($candidate) -ieq "python.exe")) {
                    return (Resolve-Path $candidate).Path
                }
            }
        }

        $envOutput = & $CondaCommand env list --json 2>&1
        if ($LASTEXITCODE -eq 0) {
            $envInfo = ($envOutput -join "`n") | ConvertFrom-Json
            foreach ($prefix in @($envInfo.envs)) {
                if ((Split-Path -Leaf $prefix) -ieq $EnvName) {
                    $candidate = Join-Path $prefix "python.exe"
                    if (Test-Path $candidate) {
                        return (Resolve-Path $candidate).Path
                    }
                }
            }
        }
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
    }

    return $null
}

function Resolve-PythonLauncher {
    $direct = @{
        FilePath = $PythonCommand
        ArgsPrefix = @()
        Label = $PythonCommand
    }

    $directTest = Test-PythonLauncher -Launcher $direct -Modules $RequiredPythonModules
    if ($directTest.Ok) {
        return $direct
    }

    $conda = Get-Command conda -ErrorAction SilentlyContinue
    if ($conda) {
        $condaLauncher = @{
            FilePath = $conda.Source
            ArgsPrefix = @("run", "--no-capture-output", "-n", $CondaEnv, "python")
            Label = "conda run -n $CondaEnv python"
        }

        $condaTest = Test-PythonLauncher -Launcher $condaLauncher -Modules $RequiredPythonModules
        if ($condaTest.Ok) {
            # Do not keep using `conda run` for background services. On Windows,
            # concurrent conda runs can race over __conda_tmp_*.txt files in TEMP.
            # Resolve the env's python.exe once, then start every process directly.
            $condaPython = Resolve-CondaPythonExecutable -CondaCommand $conda.Source -EnvName $CondaEnv
            if ($condaPython) {
                $resolvedLauncher = @{
                    FilePath = $condaPython
                    ArgsPrefix = @()
                    Label = $condaPython
                }
                $resolvedTest = Test-PythonLauncher -Launcher $resolvedLauncher -Modules $RequiredPythonModules
                if ($resolvedTest.Ok) {
                    return $resolvedLauncher
                }
                Write-Warn "Resolved Conda python '$condaPython' did not pass module checks: $($resolvedTest.Output)"
            }

            Write-Warn "Conda env '$CondaEnv' passed module checks via conda run, but its python.exe could not be resolved safely."
        }
        else {
            Write-Warn "Conda env '$CondaEnv' is available, but required modules are missing: $($condaTest.Output)"
        }
    }

    Fail "No Python environment with required modules was found. Activate/install the '$CondaEnv' env from environment.yml, or pass -PythonCommand."
}

function Invoke-Python {
    param(
        [string[]]$ArgumentList,
        [string]$WorkingDirectory = $RepoRoot,
        [switch]$AllowFailure
    )

    return Invoke-Checked `
        -FilePath $script:PythonLauncher.FilePath `
        -ArgumentList (@($script:PythonLauncher.ArgsPrefix) + $ArgumentList) `
        -WorkingDirectory $WorkingDirectory `
        -AllowFailure:$AllowFailure
}

function Stop-TrackedProcesses {
    if (-not (Test-Path $PidFile)) {
        return
    }

    Write-Step "Stopping previously tracked RSMarking processes"

    try {
        $items = Get-Content $PidFile -Raw | ConvertFrom-Json
    }
    catch {
        Write-Warn "Could not parse existing pid file. Removing it."
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
        return
    }

    foreach ($item in @($items)) {
        $proc = Get-Process -Id $item.Pid -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "    stopping $($item.Name) pid=$($item.Pid)"
            & taskkill /PID $item.Pid /T /F | Out-Null
        }
    }

    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
}

function Wait-ContainerHealthy {
    param(
        [string]$Name,
        [int]$TimeoutSeconds = 120
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        $status = (& docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $Name 2>$null)

        if ($status -in @("healthy", "running")) {
            Write-Ok "$Name is $status"
            return
        }

        Start-Sleep -Seconds 2
    }

    Fail "Container '$Name' did not become healthy within $TimeoutSeconds seconds."
}

function Ensure-DatabaseBasics {
    Write-Step "Ensuring PostgreSQL databases and PostGIS extensions"

    Invoke-Checked `
        -FilePath "docker" `
        -ArgumentList @("exec", "rsmarking-postgres", "createdb", "-U", "rs_admin", "vector_db") `
        -AllowFailure `
        -SuppressOutput | Out-Null

    Invoke-Checked `
        -FilePath "docker" `
        -ArgumentList @("exec", "rsmarking-postgres", "psql", "-U", "rs_admin", "-d", "rsmarking", "-c", "CREATE EXTENSION IF NOT EXISTS postgis;") `
        -SuppressOutput | Out-Null

    Invoke-Checked `
        -FilePath "docker" `
        -ArgumentList @("exec", "rsmarking-postgres", "psql", "-U", "rs_admin", "-d", "vector_db", "-c", "CREATE EXTENSION IF NOT EXISTS postgis;") `
        -SuppressOutput | Out-Null
}

function Ensure-ExecutorImage {
    if ($SkipExecutorImage) {
        Write-Warn "Skipping executor sandbox image check because -SkipExecutorImage was provided."
        return
    }

    $exists = Invoke-Checked `
        -FilePath "docker" `
        -ArgumentList @("image", "inspect", "rs-worker-python:latest") `
        -AllowFailure `
        -SuppressOutput

    if ($exists -eq 0) {
        Write-Ok "Executor sandbox image exists"
        return
    }

    Write-Step "Building executor sandbox image"

    $attempts = [Math]::Max(1, $ExecutorImageBuildRetries + 1)
    for ($attempt = 1; $attempt -le $attempts; $attempt++) {
        Write-Host "    build attempt $attempt/$attempts"

        $exitCode = Invoke-Checked `
            -FilePath "docker" `
            -ArgumentList @(
                "build",
                "-t", "rs-worker-python:latest",
                "-f", "services/executor_service/runtime/python_base.Dockerfile",
                "services/executor_service/runtime"
            ) `
            -AllowFailure

        if ($exitCode -eq 0) {
            Write-Ok "Executor sandbox image built"
            return
        }

        if ($attempt -lt $attempts) {
            Write-Warn "Executor image build failed. Retrying after 5 seconds."
            Start-Sleep -Seconds 5
        }
    }

    $message = "Executor sandbox image could not be built. Backend services will still start, but custom script execution will be unavailable until image rs-worker-python:latest exists."
    if ($RequireExecutorImage) {
        Fail $message
    }

    Write-Warn $message
}

function Run-Migrations {
    if ($SkipMigrations) {
        return
    }

    Write-Step "Running data database migrations"

    Invoke-Python `
        -ArgumentList @("-m", "alembic", "upgrade", "head") `
        -WorkingDirectory (Join-Path $RepoRoot "infrastructure\db_migrations") | Out-Null

    Write-Step "Running annotation database migrations"

    Invoke-Python `
        -ArgumentList @("-m", "alembic", "upgrade", "head") `
        -WorkingDirectory (Join-Path $RepoRoot "infrastructure\annot_migrations") | Out-Null
}

function Write-FrontendRuntimeConfig {
    Write-Step "Writing frontend runtime configuration"

    $config = [ordered]@{
        dataServiceUrl = "http://localhost:8002"
        annotationServiceUrl = "http://localhost:8001"
        vectorTileServiceUrl = "http://localhost:8003"
        executorServiceUrl = "http://localhost:8004"
        tileServiceUrl = "http://localhost:8005"
        aiGatewayUrl = "http://localhost:8006"
    }
    $json = $config | ConvertTo-Json -Depth 4
    $content = "window.RSMARKING_CONFIG = $json;`n"
    Set-Content -LiteralPath (Join-Path $RepoRoot "client\runtime-config.js") -Value $content -Encoding UTF8
}

function Test-PortOpen {
    param([int]$Port)

    $client = New-Object System.Net.Sockets.TcpClient

    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)

        if (-not $async.AsyncWaitHandle.WaitOne(500)) {
            return $false
        }

        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Test-HttpOk {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        return ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400)
    }
    catch {
        return $false
    }
}

function Wait-FrontendReady {
    param([int]$TimeoutSeconds = 90)

    $url = "http://localhost:8002/client/index.html"
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk -Url $url) {
            Write-Ok "Frontend is available at $url"
            return
        }
        Start-Sleep -Seconds 1
    }

    Write-Warn "Frontend did not respond at $url within $TimeoutSeconds seconds. Check data_service logs."
}

function ConvertTo-CmdArgument {
    param([string]$Value)

    if ($Value -notmatch '[\s"]') {
        return $Value
    }

    return '"' + ($Value -replace '"', '\"') + '"'
}

function Join-CmdCommandLine {
    param(
        [string]$FilePath,
        [string[]]$ArgumentList
    )

    return (@($FilePath) + $ArgumentList | ForEach-Object { ConvertTo-CmdArgument $_ }) -join " "
}

function Wait-Port {
    param(
        [string]$Name,
        [int]$Port,
        [int]$TimeoutSeconds = 60
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -Port $Port) {
            Write-Ok "$Name is listening on port $Port"
            return
        }

        Start-Sleep -Seconds 1
    }

    Write-Warn "$Name did not open port $Port within $TimeoutSeconds seconds. Check its log files."
}

function Start-ManagedProcess {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory = $RepoRoot,
        [int]$Port = 0
    )

    $stdout = Join-Path $LogDir "$Name.out.log"
    $stderr = Join-Path $LogDir "$Name.err.log"

    Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue

    $commandLine = Join-CmdCommandLine -FilePath $FilePath -ArgumentList $ArgumentList

    $startArgs = @{
        FilePath = "cmd.exe"
        ArgumentList = @("/d", "/s", "/c", $commandLine)
        WorkingDirectory = $WorkingDirectory
        PassThru = $true
        RedirectStandardOutput = $stdout
        RedirectStandardError = $stderr
    }

    if (-not $VisibleLogs) {
        $startArgs.WindowStyle = "Hidden"
    }

    $proc = Start-Process @startArgs

    Write-Host "    started $Name pid=$($proc.Id)"

    return [pscustomobject]@{
        Name = $Name
        Pid = $proc.Id
        Port = $Port
        Out = $stdout
        Err = $stderr
    }
}

function Test-WorkerReady {
    $args = @($script:PythonLauncher.ArgsPrefix) + @(
        "-m",
        "celery",
        "-A",
        "worker_cluster.app.celery_app",
        "inspect",
        "registered"
    )

    Push-Location $RepoRoot
    $oldErrorActionPreference = $ErrorActionPreference

    try {
        $ErrorActionPreference = "Continue"
        $output = & $script:PythonLauncher.FilePath @args 2>&1
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    }
    finally {
        $ErrorActionPreference = $oldErrorActionPreference
        Pop-Location
    }

    return ($exitCode -eq 0 -and (($output -join "`n") -match "worker_cluster.tasks.algorithm.raster_product"))
}

function Wait-WorkerReady {
    param([int]$TimeoutSeconds = 60)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)

    while ((Get-Date) -lt $deadline) {
        if (Test-WorkerReady) {
            Write-Ok "Celery worker registered raster_product task"
            return
        }

        Start-Sleep -Seconds 2
    }

    Write-Warn "Celery worker readiness was not confirmed. Check logs\launch\worker_cluster.err.log."
}

try {
    Set-Location $RepoRoot
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  RSMarking one-click launcher" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Cyan

    Stop-TrackedProcesses

    $script:PythonLauncher = Resolve-PythonLauncher

    Write-Ok "Using Python launcher: $($script:PythonLauncher.Label)"

    $env:PYTHONPATH = "$RepoRoot;$env:PYTHONPATH"

    $env:DATABASE_URL = if ($env:DATABASE_URL) {
        $env:DATABASE_URL
    }
    else {
        "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/rsmarking"
    }

    $env:SYNC_DATABASE_URL = if ($env:SYNC_DATABASE_URL) {
        $env:SYNC_DATABASE_URL
    }
    else {
        "postgresql+psycopg2://rs_admin:rs_password@localhost:5432/rsmarking"
    }

    $env:CELERY_BROKER_URL = if ($env:CELERY_BROKER_URL) {
        $env:CELERY_BROKER_URL
    }
    else {
        "amqp://rs_admin:rs_password@localhost:5672/rsmarking_vhost"
    }

    $env:CELERY_RESULT_BACKEND = if ($env:CELERY_RESULT_BACKEND) {
        $env:CELERY_RESULT_BACKEND
    }
    else {
        "redis://localhost:6379/0"
    }

    $env:RS_PROCESSING_BACKEND = "cluster"
    $env:RS_CLUSTER_REQUIRE_WORKER = "1"
    $env:RS_CLUSTER_FALLBACK = if ($AllowInlineFallback) { "1" } else { "0" }

    if (-not $SkipDocker) {
        Write-Step "Checking Docker"

        Start-DockerDesktopIfNeeded
        $compose = Resolve-DockerComposeCommand
        Write-Ok "Using Docker Compose command: $($compose.Label)"

        Write-Step "Starting PostgreSQL, RabbitMQ, and Redis"

        Invoke-DockerComposeUp `
            -WorkingDirectory (Join-Path $RepoRoot "infrastructure\docker")

        Wait-ContainerHealthy -Name "rsmarking-postgres"
        Wait-ContainerHealthy -Name "rsmarking-rabbitmq"
        Wait-ContainerHealthy -Name "rsmarking-redis"

        Ensure-DatabaseBasics
        Ensure-ExecutorImage
    }

    Run-Migrations
    Write-FrontendRuntimeConfig

    $started = @()

    Write-Step "Starting Celery worker"

    $workerArgs = @($script:PythonLauncher.ArgsPrefix) + @(
        "-m",
        "celery",
        "-A",
        "worker_cluster.app.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=4",
        "-Q",
        "preprocess,index,export"
    )

    $started += Start-ManagedProcess `
        -Name "worker_cluster" `
        -FilePath $script:PythonLauncher.FilePath `
        -ArgumentList $workerArgs

    Write-Step "Starting FastAPI services"

    foreach ($svc in $Services) {
        $args = @($script:PythonLauncher.ArgsPrefix) + @(
            "-m",
            "uvicorn",
            $svc.App,
            "--host",
            "0.0.0.0",
            "--port",
            [string]$svc.Port
        )

        if ($Reload) {
            $args += "--reload"
        }

        $started += Start-ManagedProcess `
            -Name $svc.Name `
            -FilePath $script:PythonLauncher.FilePath `
            -ArgumentList $args `
            -Port $svc.Port
    }

    $started | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $PidFile -Encoding UTF8

    Wait-WorkerReady

    foreach ($svc in $Services) {
        Wait-Port -Name $svc.Name -Port $svc.Port
    }

    Wait-FrontendReady

    Write-Host ""
    Write-Host "RSMarking is launching." -ForegroundColor Green
    Write-Host "Client:        http://localhost:8002/client/index.html"
    Write-Host "Data service:  http://localhost:8002"
    Write-Host "RabbitMQ UI:   http://localhost:15672  (rs_admin / rs_password)"
    Write-Host "Logs:          $LogDir"
    Write-Host "Stop command:  .\stop_rsmarking.ps1"

    if (-not $NoBrowser) {
        Start-Process "http://localhost:8002/client/index.html"
    }
}
catch {
    Write-Host ""
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Check logs in $LogDir if any processes were started." -ForegroundColor Yellow

    if (-not $NoPause) {
        Read-Host "Press Enter to exit"
    }

    exit 1
}

if (-not $NoPause) {
    Read-Host "Press Enter to close this launcher window. Services keep running in the background"
}
