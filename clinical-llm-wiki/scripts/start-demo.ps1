[CmdletBinding()]
param(
    [switch]$Reset
)

$ErrorActionPreference = "Stop"
$wikiRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$runtimePath = [System.IO.Path]::GetFullPath((Join-Path $wikiRoot ".demo-runtime"))
$rootPrefix = $wikiRoot.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
if (-not $runtimePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Resolved demo runtime path is outside the knowledge product root."
}

$envPath = Join-Path $runtimePath "demo.env"
$identitiesPath = Join-Path $runtimePath "identities.json"
$accessPath = Join-Path $runtimePath "access.json"
$composeProject = "clinical-knowledge-demo"

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [System.Convert]::ToHexString($bytes).ToLowerInvariant()
}

if ($Reset) {
    if (Test-Path -LiteralPath $envPath) {
        & docker compose `
            --project-name $composeProject `
            --env-file $envPath `
            --file (Join-Path $wikiRoot "compose.yaml") `
            down --volumes --remove-orphans
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to stop the existing demo Compose project."
        }
    }
    if (Test-Path -LiteralPath $runtimePath) {
        Remove-Item -LiteralPath $runtimePath -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $envPath)) {
    New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
    $authorToken = New-RandomSecret
    $reviewerToken = New-RandomSecret
    $postgresPassword = New-RandomSecret
    $documentToken = New-RandomSecret
    $enrichmentToken = New-RandomSecret
    $releaseToken = New-RandomSecret

    $identityBundle = [ordered]@{
        version = 1
        issuer = "local://p12-demo"
        identities = @(
            [ordered]@{
                token = $authorToken
                userId = "usr-demo-author"
                subject = "demo-author"
                displayName = "Demo Author"
                email = "author@example.test"
                roles = @("knowledge_curator")
            },
            [ordered]@{
                token = $reviewerToken
                userId = "usr-demo-reviewer"
                subject = "demo-reviewer"
                displayName = "Demo Reviewer"
                email = "reviewer@example.test"
                roles = @("reviewer")
            }
        )
    }
    $identityBundle | ConvertTo-Json -Depth 8 |
        Set-Content -LiteralPath $identitiesPath -Encoding utf8NoBOM
    [ordered]@{
        author = [ordered]@{
            displayName = "Demo Author"
            token = $authorToken
        }
        reviewer = [ordered]@{
            displayName = "Demo Reviewer"
            token = $reviewerToken
        }
    } | ConvertTo-Json -Depth 5 |
        Set-Content -LiteralPath $accessPath -Encoding utf8NoBOM

    @(
        "KNOWLEDGE_POSTGRES_PASSWORD=$postgresPassword"
        "KNOWLEDGE_DOCUMENT_WORKER_SERVICE_ACCOUNT_ID=svc-demo-document"
        "KNOWLEDGE_ENRICHMENT_WORKER_SERVICE_ACCOUNT_ID=svc-demo-enrichment"
        "KNOWLEDGE_RELEASE_WORKER_SERVICE_ACCOUNT_ID=svc-demo-release"
        "P12_DOCUMENT_WORKER_TOKEN=$documentToken"
        "P12_ENRICHMENT_WORKER_TOKEN=$enrichmentToken"
        "P12_RELEASE_WORKER_TOKEN=$releaseToken"
        "KNOWLEDGE_ORGANIZATION_NAME=Clinical Knowledge Demo"
    ) | Set-Content -LiteralPath $envPath -Encoding utf8NoBOM
}

$identities = Get-Content -LiteralPath $identitiesPath -Raw | ConvertFrom-Json
$author = $identities.identities |
    Where-Object { $_.roles -contains "knowledge_curator" } |
    Select-Object -First 1
if ($null -eq $author) {
    throw "The demo identity bundle has no knowledge curator."
}

Push-Location $wikiRoot
try {
    & docker compose `
        --project-name $composeProject `
        --env-file $envPath `
        --file (Join-Path $wikiRoot "compose.yaml") `
        up --build -d --wait --wait-timeout 240
    if ($LASTEXITCODE -ne 0) {
        throw "The demo Compose stack did not become healthy."
    }
} finally {
    Pop-Location
}

$candidateUrl = "http://127.0.0.1:8788/api/prerelease/v1/candidates"
$headers = @{ Authorization = "Bearer $($author.token)" }
$candidateReady = $false
for ($attempt = 1; $attempt -le 60; $attempt += 1) {
    try {
        $response = Invoke-RestMethod -Uri $candidateUrl -Headers $headers -Method Get
        if ($response.data.total -ge 1) {
            $candidateReady = $true
            break
        }
    } catch {
        # The bounded poll covers API startup and the independent enrichment worker.
    }
    Start-Sleep -Seconds 1
}
if (-not $candidateReady) {
    throw "The API became healthy, but no worker-produced Candidate appeared."
}

Write-Host "Knowledge Ledger is ready at http://localhost:4173/app.html#/candidates"
Write-Host "Local access identities are stored in .demo-runtime/access.json (not printed)."
Write-Host "Use -Reset to remove only the clinical-knowledge-demo volumes and regenerate data."
