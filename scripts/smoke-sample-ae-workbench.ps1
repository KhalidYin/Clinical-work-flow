param(
    [int]$Port = 8788,
    [switch]$KeepServer
)

# API preflight only. This script does not operate the browser and is not a
# work-to-end UI acceptance test. Use e2e-sample-ae-workbench.ps1 for that.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$workflowRoot = Join-Path $repoRoot "clinical-workflow"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = "python"
$baseUrl = "http://127.0.0.1:$Port"
$tmpRoot = Join-Path $repoRoot ".tmp"
$stdoutLog = Join-Path $tmpRoot "sample-ae-workbench-smoke.stdout.log"
$stderrLog = Join-Path $tmpRoot "sample-ae-workbench-smoke.stderr.log"

if (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
}

if (-not (Test-Path -LiteralPath $workflowRoot)) {
    throw "clinical-workflow folder not found under $repoRoot"
}

New-Item -ItemType Directory -Force -Path $tmpRoot | Out-Null
$env:CLINICAL_STUDIES_ROOT = Join-Path $repoRoot "clinical-studies"

Push-Location -LiteralPath $workflowRoot
try {
    $preflight = @'
import importlib.util

missing = [
    name
    for name in ("pandas", "pyreadstat")
    if importlib.util.find_spec(name) is None
]
if missing:
    raise SystemExit(
        "Missing POC runtime dependencies: "
        + ", ".join(missing)
        + '. Run: .\\.venv\\Scripts\\python.exe -m pip install -e ".\\clinical-workflow[dev]"'
    )

from src.application_api.app import create_app

create_app()
print("Application API preflight OK")
print("POC runtime dependency preflight OK")
'@
    & $python -c $preflight
} finally {
    Pop-Location
}

$startedProcess = $null
$existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Reusing existing Application API on $baseUrl"
} else {
    Write-Host "Starting Application API on $baseUrl for smoke check"
    $startedProcess = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "src.application_api.app:create_app", "--factory", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $workflowRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -PassThru
}

try {
    $ready = $false
    for ($i = 0; $i -lt 20; $i++) {
        try {
            Invoke-RestMethod -Uri "$baseUrl/api/v1/studies" -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) {
        throw "Application API did not become ready. See $stderrLog"
    }

    $workbench = Invoke-WebRequest -Uri "$baseUrl/workbench/" -TimeoutSec 10
    if ($workbench.StatusCode -ne 200 -or $workbench.Content -notmatch "Clinical POC Workbench") {
        throw "Workbench shell check failed"
    }

    $studies = Invoke-RestMethod -Uri "$baseUrl/api/v1/studies" -TimeoutSec 10
    if (-not ($studies.studies | Where-Object { $_.study_id -eq "SAMPLE-AE-001" })) {
        throw "SAMPLE-AE-001 not visible from Application API"
    }

    $state = Invoke-RestMethod -Uri "$baseUrl/api/v1/studies/SAMPLE-AE-001/poc-state" -TimeoutSec 10
    if ($state.target_artifact -ne "sdtm_ae_dataset") {
        throw "Unexpected POC target_artifact: $($state.target_artifact)"
    }

    Write-Host "API preflight OK (no browser actions were executed)"
    Write-Host "Workbench: $baseUrl/workbench/"
    Write-Host "Study: $($state.study_id)"
    Write-Host "Run state: $($state.run_state)"
    Write-Host "Active step: $($state.active_step.step_id)"
} finally {
    if ($startedProcess -and -not $KeepServer) {
        Stop-Process -Id $startedProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "Stopped API preflight process $($startedProcess.Id)"
    } elseif ($startedProcess -and $KeepServer) {
        Write-Host "Kept Application API running at $baseUrl with PID $($startedProcess.Id)"
    }
}
