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
    throw "解析后的演示运行目录超出知识产品根目录。"
}

$envPath = Join-Path $runtimePath "demo.env"
$adminMarkerPath = Join-Path $runtimePath "admin.initialized"
$composePath = Join-Path $wikiRoot "compose.yaml"
$composeProject = "clinical-knowledge-demo"

function New-RandomSecret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [System.Convert]::ToHexString($bytes).ToLowerInvariant()
}

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & docker compose `
        --project-name $composeProject `
        --env-file $envPath `
        --file $composePath `
        @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose 命令执行失败：$($Arguments -join ' ')"
    }
}

# 先升级既有环境文件，否则旧 Compose 项目甚至无法执行 down/reset。
if (Test-Path -LiteralPath $envPath) {
    $existingEnvLines = @(Get-Content -LiteralPath $envPath)
    if (-not ($existingEnvLines | Where-Object {
        $_ -match '^KNOWLEDGE_RUNTIME_CONSUMER_SECRET='
    })) {
        "KNOWLEDGE_RUNTIME_CONSUMER_SECRET=$(New-RandomSecret)" |
            Add-Content -LiteralPath $envPath -Encoding utf8NoBOM
    }
}

if ($Reset) {
    if (Test-Path -LiteralPath $envPath) {
        Invoke-Compose down --volumes --remove-orphans
    }
    if (Test-Path -LiteralPath $runtimePath) {
        Remove-Item -LiteralPath $runtimePath -Recurse -Force
    }
}

New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null

if (-not (Test-Path -LiteralPath $envPath)) {
    @(
        "KNOWLEDGE_POSTGRES_PASSWORD=$(New-RandomSecret)"
        "KNOWLEDGE_DOCUMENT_WORKER_SERVICE_ACCOUNT_ID=svc-demo-document"
        "KNOWLEDGE_ENRICHMENT_WORKER_SERVICE_ACCOUNT_ID=svc-demo-enrichment"
        "KNOWLEDGE_RELEASE_WORKER_SERVICE_ACCOUNT_ID=svc-demo-release"
        "P12_DOCUMENT_WORKER_TOKEN=$(New-RandomSecret)"
        "P12_ENRICHMENT_WORKER_TOKEN=$(New-RandomSecret)"
        "P12_RELEASE_WORKER_TOKEN=$(New-RandomSecret)"
        "KNOWLEDGE_RUNTIME_CONSUMER_SECRET=$(New-RandomSecret)"
        "KNOWLEDGE_ORGANIZATION_NAME=临床知识平台"
    ) | Set-Content -LiteralPath $envPath -Encoding utf8NoBOM
}

# P13 以前生成的 demo.env 没有独立 Workflow consumer 凭据；原位升级时只补这一项。
$envLines = @(Get-Content -LiteralPath $envPath)
if (-not ($envLines | Where-Object { $_ -match '^KNOWLEDGE_RUNTIME_CONSUMER_SECRET=' })) {
    "KNOWLEDGE_RUNTIME_CONSUMER_SECRET=$(New-RandomSecret)" |
        Add-Content -LiteralPath $envPath -Encoding utf8NoBOM
}

$initialAdminPassword = $null
Push-Location $wikiRoot
try {
    Invoke-Compose up --build -d --wait --wait-timeout 240 postgres migration

    if (-not (Test-Path -LiteralPath $adminMarkerPath)) {
        $initialAdminPassword = New-RandomSecret
        $initialAdminPassword | & docker compose `
            --project-name $composeProject `
            --env-file $envPath `
            --file $composePath `
            run --rm -T admin-bootstrap
        if ($LASTEXITCODE -ne 0) {
            throw "无法创建本地管理员。"
        }
        "created" | Set-Content -LiteralPath $adminMarkerPath -Encoding ascii
    }

    Invoke-Compose up --build -d --wait --wait-timeout 240
} finally {
    Pop-Location
}

$candidateReady = $false
for ($attempt = 1; $attempt -le 60; $attempt += 1) {
    $candidateCount = & docker compose `
        --project-name $composeProject `
        --env-file $envPath `
        --file $composePath `
        exec -T postgres psql -U knowledge -d knowledge -Atc `
        "select count(*) from knowledge_candidates;"
    if ($LASTEXITCODE -eq 0 -and [int]$candidateCount -ge 1) {
        $candidateReady = $true
        break
    }
    Start-Sleep -Seconds 1
}
if (-not $candidateReady) {
    throw "平台已启动，但异步富化 Worker 未生成知识候选。"
}

Write-Host "临床知识台账已就绪：http://localhost:4173/app.html#/candidates"
if ($null -ne $initialAdminPassword) {
    Write-Host "初始管理员用户名：admin"
    Write-Host "一次性临时密码：$initialAdminPassword"
    Write-Host "请立即登录并修改密码；该密码未写入任何文件。"
} else {
    Write-Host "管理员 admin 已存在，请使用此前修改后的密码登录。"
}
Write-Host "使用 -Reset 仅删除 clinical-knowledge-demo 卷并重新生成演示数据。"
