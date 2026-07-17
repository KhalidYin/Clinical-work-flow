param(
    [string]$StudiesRoot = "",
    [int]$Port = 8788,
    [switch]$NoBrowser,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workflowRoot = Join-Path $repoRoot "clinical-workflow"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = "python"
$url = "http://127.0.0.1:$Port/workbench/"

if (-not (Test-Path -LiteralPath $workflowRoot)) {
    throw "clinical-workflow folder not found under $repoRoot"
}

if (Test-Path -LiteralPath $venvPython) {
    $python = $venvPython
}

if ($StudiesRoot) {
    $resolvedStudiesRoot = (Resolve-Path -LiteralPath $StudiesRoot).Path
    $env:CLINICAL_STUDIES_ROOT = $resolvedStudiesRoot
    Write-Host "Using CLINICAL_STUDIES_ROOT=$resolvedStudiesRoot"
} else {
    Remove-Item Env:\CLINICAL_STUDIES_ROOT -ErrorAction SilentlyContinue
    Write-Host "Using default clinical-studies folder under repository root."
}

Push-Location -LiteralPath $workflowRoot
try {
    & $python -c "from src.application_api.app import create_app; create_app(); print('Study Console preflight OK')"
} finally {
    Pop-Location
}

if ($CheckOnly) {
    Write-Host "CheckOnly complete. Study Console can be started with: .\start-study-console.ps1"
    exit 0
}

$existing = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Clinical Study Console already appears to be listening on $url"
    Write-Host "Owning process id: $($existing.OwningProcess)"
    if (-not $NoBrowser) {
        Start-Process $url
    }
    exit 0
}

Write-Host "Starting Clinical Study Console on $url"
Write-Host "This PowerShell window keeps the local API running. Press Ctrl+C to stop."
if (-not $NoBrowser) {
    Start-Process $url
}

Set-Location -LiteralPath $workflowRoot
& $python -m uvicorn "src.application_api.app:create_app" --factory --host 127.0.0.1 --port $Port
