param(
    [string]$StudiesRoot = "",
    [int]$Port = 8788
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$workflowRoot = Join-Path $repoRoot "clinical-workflow"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = "python"

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

Write-Host "Starting Clinical Study Console on http://127.0.0.1:$Port/console/"
Set-Location -LiteralPath $workflowRoot
& $python -m uvicorn "src.application_api.app:create_app" --factory --host 127.0.0.1 --port $Port
