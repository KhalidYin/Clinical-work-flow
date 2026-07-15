param(
    [string]$RepoRoot = $PSScriptRoot,
    [string]$Python = "",
    [string]$HostAddress = "127.0.0.1",
    [int]$Port = 8790,
    [switch]$NoBrowser,
    [switch]$CheckOnly,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$resolvedRepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$reviewPanelSrc = Join-Path $resolvedRepoRoot "review-panel\src"
$reviewPanelCli = Join-Path $reviewPanelSrc "review_panel\cli.py"
$venvPython = Join-Path $resolvedRepoRoot ".venv\Scripts\python.exe"

if ($HostAddress -ne "127.0.0.1") {
    throw "Review Panel is loopback-only. Use -HostAddress 127.0.0.1."
}

if (-not (Test-Path -LiteralPath $reviewPanelCli)) {
    throw "Cannot find Review Panel source at: $reviewPanelCli"
}

if ([string]::IsNullOrWhiteSpace($Python)) {
    if (Test-Path -LiteralPath $venvPython) {
        $Python = $venvPython
    }
    else {
        $Python = "python"
    }
}

if ([string]::IsNullOrWhiteSpace($env:PYTHONPATH)) {
    $env:PYTHONPATH = $reviewPanelSrc
}
else {
    $env:PYTHONPATH = "$reviewPanelSrc;$env:PYTHONPATH"
}

$url = "http://$HostAddress`:$Port/"
$commonArgs = @("--repo-root", $resolvedRepoRoot, "--host", $HostAddress, "--port", $Port.ToString())
$checkArgs = @("-m", "review_panel", "check") + $commonArgs
$serveArgs = @("-m", "review_panel", "serve") + $commonArgs

if ($DryRun) {
    Write-Host "Review Panel quick start dry run"
    Write-Host "Repo root : $resolvedRepoRoot"
    Write-Host "Python    : $Python"
    Write-Host "PYTHONPATH: $reviewPanelSrc"
    Write-Host "Check     : $Python $($checkArgs -join ' ')"
    Write-Host "Serve     : $Python $($serveArgs -join ' ')"
    Write-Host "URL       : $url"
    exit 0
}

Write-Host "[Review Panel] Preflight: checking runtime dependencies..."
& $Python -c "import fastapi, jsonschema, pydantic, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Missing Review Panel dependencies. From repo root, run: .\.venv\Scripts\python -m pip install -e `".\review-panel[dev]`""
    exit $LASTEXITCODE
}

Write-Host "[Review Panel] Preflight: checking schema and trusted queues..."
& $Python @checkArgs
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if ($CheckOnly) {
    exit 0
}

Write-Host "[Review Panel] Starting loopback server: $url"
Write-Host "[Review Panel] Press Ctrl+C in this terminal to stop."

if (-not $NoBrowser) {
    try {
        Start-Process $url
    }
    catch {
        Write-Warning "Could not open browser automatically. Open $url manually."
    }
}

& $Python @serveArgs
exit $LASTEXITCODE
