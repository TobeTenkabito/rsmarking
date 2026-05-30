param(
    [string]$CondaEnv = "rsmarking",
    [string]$PythonCommand = "python",
    [switch]$SkipInstall,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$LauncherSource = "tools\rsmarking_exe_launcher.py"
$BuildWorkDir = "build\pyinstaller"
$OutputExe = ".\rsmarking.exe"

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

function Invoke-Native {
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

    return @{
        ExitCode = $exitCode
        Output = if ($output) { $output -join "`n" } else { "" }
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

function Resolve-BuildPython {
    $conda = Get-Command conda -ErrorAction SilentlyContinue
    if ($conda) {
        $condaPython = Resolve-CondaPythonExecutable -CondaCommand $conda.Source -EnvName $CondaEnv
        if ($condaPython) {
            return @{
                FilePath = $condaPython
                Label = "$CondaEnv ($condaPython)"
            }
        }

        Write-Warn "Conda env '$CondaEnv' was not found or did not expose python.exe."
    }

    $direct = Get-Command $PythonCommand -ErrorAction SilentlyContinue
    if ($direct) {
        return @{
            FilePath = $direct.Source
            Label = $direct.Source
        }
    }

    Fail "No usable Python was found. Install/activate Conda env '$CondaEnv' or pass -PythonCommand."
}

function Test-PyInstaller {
    param([string]$PythonExe)

    $result = Invoke-Native `
        -FilePath $PythonExe `
        -ArgumentList @("-c", "import PyInstaller; print(PyInstaller.__version__)") `
        -AllowFailure `
        -SuppressOutput

    return @{
        Ok = ($result.ExitCode -eq 0)
        Version = $result.Output.Trim()
    }
}

function Ensure-PyInstaller {
    param([string]$PythonExe)

    $test = Test-PyInstaller -PythonExe $PythonExe
    if ($test.Ok) {
        Write-Ok "PyInstaller is available ($($test.Version))"
        return
    }

    if ($SkipInstall) {
        Fail "PyInstaller is missing. Re-run without -SkipInstall or install it with: $PythonExe -m pip install pyinstaller"
    }

    Write-Step "Installing PyInstaller into the build Python environment"
    Invoke-Native -FilePath $PythonExe -ArgumentList @("-m", "pip", "install", "pyinstaller") | Out-Null

    $test = Test-PyInstaller -PythonExe $PythonExe
    if (-not $test.Ok) {
        Fail "PyInstaller installation did not complete successfully."
    }

    Write-Ok "PyInstaller is available ($($test.Version))"
}

try {
    Set-Location $RepoRoot

    if (-not (Test-Path $LauncherSource)) {
        Fail "Launcher source was not found: $LauncherSource"
    }

    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  RSMarking executable builder" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Cyan

    $python = Resolve-BuildPython
    Write-Ok "Using Python: $($python.Label)"

    Ensure-PyInstaller -PythonExe $python.FilePath

    New-Item -ItemType Directory -Path $BuildWorkDir -Force | Out-Null

    $pyinstallerArgs = @(
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--console",
        "--name",
        "rsmarking",
        "--distpath",
        ".",
        "--workpath",
        $BuildWorkDir,
        "--specpath",
        $BuildWorkDir
    )

    if ($Clean) {
        $pyinstallerArgs += "--clean"
    }

    $pyinstallerArgs += $LauncherSource

    Write-Step "Building rsmarking.exe"
    Invoke-Native -FilePath $python.FilePath -ArgumentList $pyinstallerArgs | Out-Null

    if (-not (Test-Path $OutputExe)) {
        Fail "Build completed without producing $OutputExe"
    }

    Write-Step "Verifying executable wrapper"
    Invoke-Native -FilePath $OutputExe -ArgumentList @("--rsmarking-wrapper-check") | Out-Null

    Write-Ok "Built $OutputExe"
    Write-Host "Double-click rsmarking.exe to launch the full RSMarking workflow."
}
catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
