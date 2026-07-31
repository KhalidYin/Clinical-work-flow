[CmdletBinding()]
param(
    [switch]$SkipSecretPrompt,
    [switch]$SaveEncryptedSecret,
    [switch]$UseEncryptedSecret
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ($SaveEncryptedSecret -and $UseEncryptedSecret) {
    throw "SaveEncryptedSecret and UseEncryptedSecret are mutually exclusive."
}

$wikiRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$runtimePath = [System.IO.Path]::GetFullPath((Join-Path $wikiRoot ".demo-runtime"))
$rootPrefix = $wikiRoot.TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar,
    [System.IO.Path]::AltDirectorySeparatorChar
) + [System.IO.Path]::DirectorySeparatorChar
if (-not $runtimePath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Resolved runtime path is outside the knowledge product root."
}
$encryptedSecretPath = Join-Path $runtimePath "deepseek-api-key.dpapi"

$settings = [ordered]@{
    KNOWLEDGE_ENRICHMENT_PROVIDER_MODE = "live"
    KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_ID = "deepseek-v4-flash-extractor"
    KNOWLEDGE_ENRICHMENT_MODEL_PROFILE_VERSION = "1.0.1"
    KNOWLEDGE_ENRICHMENT_PROMPT_PROFILE_ID = "atomic-candidate"
    KNOWLEDGE_ENRICHMENT_PROMPT_PROFILE_VERSION = "1.1.0"
    KNOWLEDGE_LIVE_MODEL_ENABLED = "true"
    KNOWLEDGE_LIVE_MODEL_PROFILE_ID = "deepseek-v4-flash-extractor"
    KNOWLEDGE_LIVE_MODEL_PROFILE_VERSION = "1.0.1"
    KNOWLEDGE_LIVE_MODEL_ALLOWED_DATA_BOUNDARIES = "external_allowed"
    KNOWLEDGE_LIVE_MODEL_MAX_CALLS = "1"
    KNOWLEDGE_MODEL_ENDPOINT = "https://api.deepseek.com"
}

foreach ($entry in $settings.GetEnumerator()) {
    Set-Item -Path "Env:$($entry.Key)" -Value $entry.Value
}

$secretVariable = "KNOWLEDGE_MODEL_API_KEY"
$secretConfigured = -not [string]::IsNullOrWhiteSpace(
    [Environment]::GetEnvironmentVariable($secretVariable, "Process")
)
$secureValue = $null

if (-not $secretConfigured -and $UseEncryptedSecret) {
    if (-not $IsWindows) {
        throw "The local DPAPI handoff is supported only on Windows."
    }
    if (-not (Test-Path -LiteralPath $encryptedSecretPath)) {
        throw "The encrypted DeepSeek secret has not been saved."
    }
    $encryptedValue = Get-Content -LiteralPath $encryptedSecretPath -Raw
    $secureValue = ConvertTo-SecureString $encryptedValue
}

if (-not $secretConfigured -and $null -eq $secureValue -and -not $SkipSecretPrompt) {
    $secureValue = Read-Host "DeepSeek API key (hidden)" -AsSecureString
}

if (-not $secretConfigured -and $null -ne $secureValue) {
    $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        $plainValue = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
        if ([string]::IsNullOrWhiteSpace($plainValue)) {
            throw "DeepSeek API key cannot be empty."
        }
        Set-Item -Path "Env:$secretVariable" -Value $plainValue
        $secretConfigured = $true
    } finally {
        if ($secretPointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
        }
        $plainValue = $null
    }
}

if ($SaveEncryptedSecret) {
    if (-not $IsWindows) {
        throw "The local DPAPI handoff is supported only on Windows."
    }
    if (-not $secretConfigured) {
        throw "A DeepSeek API key is required before saving the encrypted handoff."
    }
    if ($null -eq $secureValue) {
        $processValue = [Environment]::GetEnvironmentVariable($secretVariable, "Process")
        $secureValue = ConvertTo-SecureString $processValue -AsPlainText -Force
        $processValue = $null
    }
    New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
    $encryptedValue = ConvertFrom-SecureString $secureValue
    [System.IO.File]::WriteAllText(
        $encryptedSecretPath,
        $encryptedValue,
        [System.Text.UTF8Encoding]::new($false)
    )
    $encryptedValue = $null
}

$secureValue = $null
Write-Host "DeepSeek live model environment configured for this PowerShell process."
Write-Host "profile=deepseek-v4-flash-extractor@1.0.1 model=deepseek-v4-flash"
Write-Host "endpoint=https://api.deepseek.com boundary=external_allowed max_calls=1"
Write-Host "secret=$($secretConfigured ? 'configured' : 'not configured')"
Write-Host "encrypted_handoff=$($SaveEncryptedSecret ? 'saved' : ($UseEncryptedSecret ? 'loaded' : 'unchanged'))"
