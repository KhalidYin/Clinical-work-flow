param(
    [int]$Port = 8792,
    [switch]$Headed,
    [switch]$KeepArtifacts
)

# Local development acceptance only; this is not a regulatory/GxP validation.
# Every browser write targets a disposable StudiesRoot under .tmp/workbench-e2e.

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$workflowRoot = Join-Path $repoRoot "clinical-workflow"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { "python" }
$baseUrl = "http://127.0.0.1:$Port"
$sessionName = "clinical-workbench-$([guid]::NewGuid().ToString('N'))"
$e2eBase = Join-Path $repoRoot ".tmp\workbench-e2e"
$runRoot = Join-Path $e2eBase $sessionName
$studiesRoot = Join-Path $runRoot "clinical-studies"
$stdoutLog = Join-Path $runRoot "application-api.stdout.log"
$stderrLog = Join-Path $runRoot "application-api.stderr.log"
$successStudyId = "SAMPLE-AE-E2E"
$inputStudyId = "SAMPLE-AE-INPUT-E2E"
$server = $null
$succeeded = $false
$oldStudiesRoot = $env:CLINICAL_STUDIES_ROOT

function Write-Utf8File {
    param([string]$Path, [string]$Content)
    $parent = Split-Path -Parent $Path
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    Set-Content -LiteralPath $Path -Value $Content -Encoding utf8 -NoNewline
}

function New-E2eStudy {
    param(
        [string]$StudyId,
        [switch]$InvalidHash
    )
    $study = Join-Path $studiesRoot $StudyId
    $source = Join-Path $study "input\edc\ae.csv"
    $csv = @"
STUDYID,Subject,RecordPosition,AETERM,AESTDAT,AEENDAT,AESEV_STD,AESER_STD,AEREL_STD,AEACN_STD,AEOUT_STD,AETERM_PT,AETERM_SOC,AETERM_CoderDictName,AETERM_CoderDictVersion
$StudyId,S001,1,Headache,01 JAN 2026,02 JAN 2026,MILD,N,NOT RELATED,NONE,RECOVERED,Headache,Nervous system disorders,MedDRA,27.0
$StudyId,S001,2,Nausea,03 JAN 2026,04 JAN 2026,MODERATE,N,RELATED,DOSE NOT CHANGED,RECOVERED,Nausea,Gastrointestinal disorders,MedDRA,27.0
"@
    Write-Utf8File -Path $source -Content $csv
    $sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    $registeredHash = if ($InvalidHash) { "0" * 64 } else { $sourceHash }
    Write-Utf8File -Path (Join-Path $study "project.yaml") -Content @"
study_id: "$StudyId"
synthetic_only: true
standards:
  sdtmig_version: "3.4"
"@
    Write-Utf8File -Path (Join-Path $study "source-inventory.yaml") -Content @"
inventory_id: "workbench-e2e-$StudyId"
status: "test"
synthetic_only: true
sources:
  - path: "input/edc/ae.csv"
    source_type: "edc_csv_dataset"
    format: "csv"
    role: "ae_source_data"
    sha256: "$registeredHash"
"@
    return [pscustomobject]@{
        StudyPath = $study
        SourcePath = $source
        SourceHash = $sourceHash
    }
}

function Invoke-AgentBrowser {
    param([string[]]$Arguments)
    & agent-browser @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "agent-browser failed: agent-browser $($Arguments -join ' ')"
    }
}

function Wait-ApiReady {
    for ($i = 0; $i -lt 40; $i++) {
        try {
            Invoke-RestMethod -Uri "$baseUrl/api/v1/studies" -TimeoutSec 2 | Out-Null
            return
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    throw "Application API did not become ready. See $stderrLog"
}

function Get-PocState {
    param([string]$StudyId)
    return Invoke-RestMethod -Uri "$baseUrl/api/v1/studies/$StudyId/poc-state" -TimeoutSec 5
}

function Wait-PocState {
    param(
        [string]$StudyId,
        [scriptblock]$Predicate,
        [string]$Description
    )
    for ($i = 0; $i -lt 60; $i++) {
        $state = Get-PocState -StudyId $StudyId
        if (& $Predicate $state) {
            return $state
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Timed out waiting for $Description in $StudyId"
}

function Click-WorkbenchControl {
    param(
        [ValidateSet("button", "tab")][string]$Role,
        [string]$Name
    )
    $container = if ($Name -in @("Run POC", "Retry current step", "Review", "Resume", "Refresh")) {
        ".run-actions"
    } else {
        ".review-submit-bar"
    }
    for ($i = 0; $i -lt 30; $i++) {
        & agent-browser --session $sessionName scrollintoview $container *> $null
        if ($LASTEXITCODE -ne 0) {
            Start-Sleep -Milliseconds 250
            continue
        }
        & agent-browser --session $sessionName find role $Role click --name $Name *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Unable to click $Role '$Name' after bounded retries."
}

function Click-WorkbenchSelector {
    param([string]$Selector)
    for ($i = 0; $i -lt 30; $i++) {
        & agent-browser --session $sessionName scrollintoview $Selector *> $null
        if ($LASTEXITCODE -ne 0) {
            Start-Sleep -Milliseconds 250
            continue
        }
        & agent-browser --session $sessionName click $Selector *> $null
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 250
    }
    throw "Unable to click selector '$Selector' after bounded retries."
}

function Wait-PageText {
    param([string]$Text)
    $jsonText = ConvertTo-Json $Text -Compress
    $condition = "document.body.innerText.includes($jsonText)"
    for ($i = 0; $i -lt 3; $i++) {
        & agent-browser --session $sessionName wait --fn $condition
        if ($LASTEXITCODE -eq 0) {
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Timed out waiting for page text '$Text' after bounded browser-driver retries."
}

function Wait-StudyHeading {
    param([string]$StudyId)
    $condition = "document.querySelector('h1')?.textContent?.trim() === '$StudyId'"
    Invoke-AgentBrowser -Arguments @("--session", $sessionName, "wait", "--fn", $condition)
}

function Wait-PageCondition {
    param([string]$Condition)
    Invoke-AgentBrowser -Arguments @("--session", $sessionName, "wait", "--fn", $Condition)
}

function Approve-CurrentReview {
    Wait-PageText -Text "Approve all required findings"
    Click-WorkbenchControl -Role button -Name "Approve all required findings"
    Click-WorkbenchControl -Role button -Name "Submit DecisionReceipt"
    Wait-PageText -Text "DecisionReceipt 已写入"
}

function Action-IsEnabled {
    param($State, [string]$ActionId)
    return [bool]($State.next_actions | Where-Object { $_.action_id -eq $ActionId -and $_.enabled })
}

if (-not (Get-Command agent-browser -ErrorAction SilentlyContinue)) {
    throw "agent-browser is required. Install it before running the browser E2E."
}
if (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    throw "Port $Port is already in use. Choose another -Port; E2E will not reuse a server with an unknown StudiesRoot."
}

New-Item -ItemType Directory -Force -Path $studiesRoot | Out-Null
$successStudy = New-E2eStudy -StudyId $successStudyId
$inputStudy = New-E2eStudy -StudyId $inputStudyId -InvalidHash
$env:CLINICAL_STUDIES_ROOT = $studiesRoot

try {
    Push-Location -LiteralPath $workflowRoot
    try {
        & $python -c "from src.application_api.app import create_app; create_app(); print('E2E Application API preflight OK')"
        if ($LASTEXITCODE -ne 0) {
            throw "Application API preflight failed"
        }
    } finally {
        Pop-Location
    }

    $server = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "src.application_api.app:create_app", "--factory", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $workflowRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -PassThru
    Wait-ApiReady

    $openArgs = @("--session", $sessionName)
    if ($Headed) { $openArgs += "--headed" }
    $openArgs += @("open", "$baseUrl/workbench/")
    Invoke-AgentBrowser -Arguments $openArgs
    Invoke-AgentBrowser -Arguments @("--session", $sessionName, "select", "select", $successStudyId)
    Wait-StudyHeading -StudyId $successStudyId

    Write-Host "[E2E 1/2] full review-to-canonical flow"
    Click-WorkbenchControl -Role button -Name "Run POC"
    $mappingState = Wait-PocState -StudyId $successStudyId -Description "mapping review blocker" -Predicate {
        param($state)
        $state.run_state -eq "blocked" -and $state.blocker.kind -eq "review"
    }
    $mappingReviewId = $mappingState.blocker.review_id
    Click-WorkbenchSelector -Selector ".stage-rail li:nth-child(1) .stage-node"
    Click-WorkbenchSelector -Selector ".workspace-tabs .workspace-tab:nth-child(2)"
    Wait-PageCondition -Condition "document.querySelector('.evidence-table tbody tr') !== null"
    if ($mappingState.input_check.files[0].row_count -ne 2 -or $mappingState.input_check.files[0].column_count -ne 15) {
        throw "Input Evidence API did not report the expected 2 x 15 fixture shape"
    }
    Click-WorkbenchControl -Role button -Name "Review"
    Approve-CurrentReview
    Wait-PocState -StudyId $successStudyId -Description "mapping resume action" -Predicate {
        param($state)
        Action-IsEnabled -State $state -ActionId "resume"
    } | Out-Null
    Click-WorkbenchControl -Role button -Name "Resume"

    Wait-PocState -StudyId $successStudyId -Description "program review blocker" -Predicate {
        param($state)
        $state.run_state -eq "blocked" -and
            $state.blocker.kind -eq "review" -and
            $state.blocker.review_id -ne $mappingReviewId
    } | Out-Null
    Approve-CurrentReview
    Wait-PocState -StudyId $successStudyId -Description "program resume action" -Predicate {
        param($state)
        Action-IsEnabled -State $state -ActionId "resume"
    } | Out-Null
    Click-WorkbenchControl -Role button -Name "Resume"
    $doneState = Wait-PocState -StudyId $successStudyId -Description "canonical done state" -Predicate {
        param($state)
        $state.run_state -eq "done" -and $state.active_step.step_id -eq "canonical-ae"
    }
    Click-WorkbenchSelector -Selector ".stage-rail li:nth-child(7) .stage-node"
    Click-WorkbenchSelector -Selector ".workspace-tabs .workspace-tab:nth-child(4)"
    Wait-PageText -Text "output/sdtm/datasets/ae.csv"
    if ($doneState.steps.Where({ $_.state -eq "blocked" }).Count -ne 0) {
        throw "Done ledger still contains a blocked step"
    }

    Write-Host "[E2E 2/2] input blocker repair and Retry current step"
    Invoke-AgentBrowser -Arguments @("--session", $sessionName, "select", "select", $inputStudyId)
    Wait-StudyHeading -StudyId $inputStudyId
    Click-WorkbenchControl -Role button -Name "Run POC"
    $inputBlocked = Wait-PocState -StudyId $inputStudyId -Description "source hash input blocker" -Predicate {
        param($state)
        $state.run_state -eq "blocked" -and
            $state.active_step.step_id -eq "input-check" -and
            $state.blocker.kind -eq "input" -and
            $state.blocker.code -eq "source_hash_mismatch"
    }
    Wait-PageText -Text "source_hash_mismatch"
    if ($inputBlocked.steps.Where({ $_.state -eq "blocked" }).Count -ne 1) {
        throw "Input blocker ledger must contain exactly one blocked step"
    }
    $inventoryPath = Join-Path $inputStudy.StudyPath "source-inventory.yaml"
    $inventory = (Get-Content -Raw -LiteralPath $inventoryPath).Replace(("0" * 64), $inputStudy.SourceHash)
    Write-Utf8File -Path $inventoryPath -Content $inventory
    Click-WorkbenchControl -Role button -Name "Retry current step"
    Wait-PocState -StudyId $inputStudyId -Description "mapping review after input retry" -Predicate {
        param($state)
        $state.run_state -eq "blocked" -and
            $state.blocker.kind -eq "review" -and
            $state.active_step.step_id -eq "mapping-spec"
    } | Out-Null

    $screenshotPath = Join-Path $runRoot "workbench-e2e-final.png"
    Invoke-AgentBrowser -Arguments @("--session", $sessionName, "screenshot", $screenshotPath, "--full")
    Invoke-AgentBrowser -Arguments @("--session", $sessionName, "errors")

    $succeeded = $true
    Write-Host "Browser E2E OK"
    Write-Host "Full flow: Run -> Input Evidence -> Mapping Review -> Resume -> Program Review -> Resume -> Canonical Artifact"
    Write-Host "Recovery flow: Input hash blocker -> repair -> Retry current step -> Mapping Review"
} finally {
    & agent-browser --session $sessionName close 2>$null
    if ($server -and -not $server.HasExited) {
        Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    }
    if ($null -eq $oldStudiesRoot) {
        Remove-Item Env:\CLINICAL_STUDIES_ROOT -ErrorAction SilentlyContinue
    } else {
        $env:CLINICAL_STUDIES_ROOT = $oldStudiesRoot
    }

    $safeBase = [IO.Path]::GetFullPath($e2eBase).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $safeRun = [IO.Path]::GetFullPath($runRoot)
    $expectedPrefix = $safeBase + [IO.Path]::DirectorySeparatorChar
    if (-not $safeRun.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean an E2E path outside $safeBase : $safeRun"
    }
    if ($succeeded -and -not $KeepArtifacts) {
        Remove-Item -LiteralPath $safeRun -Recurse -Force
        Write-Host "Disposed E2E StudyRoot: $safeRun"
    } else {
        Write-Host "E2E artifacts retained for inspection: $safeRun"
    }
}
