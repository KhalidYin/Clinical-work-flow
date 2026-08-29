param(
    [ValidateSet("start", "build", "verify", "stop")]
    [string]$Action = "start"
)

$ErrorActionPreference = "Stop"
$ProjectName = "clinical-p17-poc"
$ProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$ComposeFile = Join-Path $ProjectRoot "compose.p17-poc.yaml"
$RuntimeRoot = [IO.Path]::GetFullPath(
    (Join-Path $ProjectRoot ".poc-assets\p17-full-stack-runtime")
)
$EnvironmentFile = Join-Path $RuntimeRoot ".env"
$ReceiptFile = Join-Path $RuntimeRoot "receipt.json"
$AssetFile = Join-Path $ProjectRoot ".poc-assets\ich-e9\E9_Guideline.pdf"

function Invoke-P17Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    & docker compose `
        --project-name $ProjectName `
        --file $ComposeFile `
        --env-file $EnvironmentFile `
        @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "P17 Compose command failed with exit code $LASTEXITCODE"
    }
}

function Assert-RuntimePath {
    $assetRoot = [IO.Path]::GetFullPath((Join-Path $ProjectRoot ".poc-assets"))
    $prefix = $assetRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + `
        [IO.Path]::DirectorySeparatorChar
    if (-not $RuntimeRoot.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing P17 runtime cleanup outside the local .poc-assets directory"
    }
}

function New-LocalSecret {
    return ([Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N"))
}

if ($Action -eq "start") {
    if (-not (Test-Path -LiteralPath $AssetFile -PathType Leaf)) {
        throw "Validated ICH E9 asset is missing: $AssetFile"
    }
    $existing = & docker ps -a `
        --filter "label=com.docker.compose.project=$ProjectName" `
        --format "{{.Names}}"
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to inspect Docker for the P17 project"
    }
    if ($existing) {
        throw "P17 project already exists; run the stop action before starting again"
    }
    if (Test-Path -LiteralPath $EnvironmentFile) {
        throw "P17 local runtime receipt already exists; run the stop action first"
    }
    New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    $runtimePathForCompose = $RuntimeRoot.Replace("\", "/")
    @(
        "P17_POC_POSTGRES_PASSWORD=$(New-LocalSecret)"
        "P17_POC_RUNTIME_CONSUMER_SECRET=$(New-LocalSecret)"
        "P17_POC_RUNTIME_DIR=$runtimePathForCompose"
        "P17_POC_API_PORT=8798"
        "P17_POC_FRONTEND_PORT=4183"
    ) | Set-Content -LiteralPath $EnvironmentFile -Encoding utf8NoBOM

    Invoke-P17Compose up -d --build --wait
    if (-not (Test-Path -LiteralPath $ReceiptFile -PathType Leaf)) {
        throw "P17 fixture completed without a local credential receipt"
    }
    Write-Host "P17 isolated browser POC is ready: http://127.0.0.1:4183/app.html"
    Write-Host "Browser users: p17.curator, p17.reviewer, p17.release-manager"
    Write-Host "Local-only passwords are stored in: $ReceiptFile"
    exit 0
}

if (-not (Test-Path -LiteralPath $EnvironmentFile -PathType Leaf)) {
    throw "P17 runtime is not initialized; run the start action first"
}

if ($Action -eq "build") {
    Invoke-P17Compose run --rm --no-deps fixture `
        python scripts/p17_full_stack_fixture.py build `
        --receipt /runtime/receipt.json
    exit 0
}

if ($Action -eq "verify") {
    Invoke-P17Compose run --rm --no-deps fixture `
        python scripts/p17_full_stack_fixture.py verify `
        --receipt /runtime/receipt.json
    exit 0
}

Assert-RuntimePath
Invoke-P17Compose down --volumes --remove-orphans
if (Test-Path -LiteralPath $RuntimeRoot) {
    Remove-Item -LiteralPath $RuntimeRoot -Recurse -Force
}
Write-Host "P17 isolated containers, volumes, and local credential receipt were removed."
