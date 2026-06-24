$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
$targetScript = Join-Path $scriptDir "gt7_meter.py"
$requirementsFile = Join-Path $scriptDir "requirements.txt"

if (-not (Test-Path $venvPython)) {
    Write-Error ".venv not found. Please create a virtual environment first."
}

if (-not (Test-Path $targetScript)) {
    Write-Error "gt7_meter.py not found."
}

# Restore pip if missing
$ErrorActionPreference = 'Continue'
& $venvPython -m pip --version 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[setup] Restoring pip..."
    & $venvPython -m ensurepip --upgrade
}

# Install missing packages from requirements.txt
& $venvPython -c "import Crypto, dotenv" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    if (-not (Test-Path $requirementsFile)) {
        Write-Error "requirements.txt not found."
    }
    Write-Host "[setup] Installing required packages..."
    & $venvPython -m pip install -r $requirementsFile 2>&1 | ForEach-Object { $_.ToString() }
}

# Kill existing gt7_meter.py processes to avoid port conflict
$existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match '^python(\.exe)?$' -and
        $_.CommandLine -match [regex]::Escape($targetScript)
    } |
    Select-Object -ExpandProperty ProcessId -Unique

foreach ($procId in $existing) {
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

# Launch gt7_meter.py
Write-Host "[run] Starting: $venvPython $targetScript"
& $venvPython $targetScript
