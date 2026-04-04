param(
  [ValidateRange(1, 200)]
  [int]$Count = 10,

  [string]$HandoffPath = ".\.claude\handoff\repo-codex-flow-current.md",

  [switch]$SkipHandoff
)

$ErrorActionPreference = "Stop"

function Invoke-WorkflowScript {
  param(
    [string]$Label,
    [string]$ScriptPath,
    [hashtable]$Arguments = @{}
  )

  if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "Missing script: $ScriptPath"
  }

  Write-Output ("==> {0}" -f $Label)
  & $ScriptPath @Arguments
  Write-Output ""
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
$scriptsDir = Join-Path $repoRoot "scripts"

$syncScript = Join-Path $scriptsDir "codex-commit-history-sync.ps1"
$summaryScript = Join-Path $scriptsDir "codex-release-summary.ps1"
$checkpointScript = Join-Path $scriptsDir "codex-commit-checkpoint.ps1"
$statusScript = Join-Path $scriptsDir "codex-workflow-status.ps1"
$handoffScript = Join-Path $scriptsDir "codex-handoff-refresh.ps1"

$resolvedHandoffPath = $null
if (-not $SkipHandoff) {
  $candidatePath = $HandoffPath
  if (-not [System.IO.Path]::IsPathRooted($candidatePath)) {
    $candidatePath = Join-Path $repoRoot $candidatePath
  }

  if (Test-Path -LiteralPath $candidatePath) {
    $resolvedHandoffPath = (Resolve-Path -LiteralPath $candidatePath).Path
  } elseif ($PSBoundParameters.ContainsKey("HandoffPath")) {
    throw "Missing handoff file: $candidatePath"
  } else {
    Write-Warning ("Default handoff file not found, skipping refresh: {0}" -f $candidatePath)
  }
}

Invoke-WorkflowScript -Label "Sync commit history" -ScriptPath $syncScript -Arguments @{ Count = $Count }
Invoke-WorkflowScript -Label "Generate recent summary" -ScriptPath $summaryScript -Arguments @{ Count = $Count }
Invoke-WorkflowScript -Label "Refresh local commit checkpoint" -ScriptPath $checkpointScript
Invoke-WorkflowScript -Label "Refresh workflow status" -ScriptPath $statusScript -Arguments @{ SkipCheckpointRefresh = $true }

if ($resolvedHandoffPath) {
  Invoke-WorkflowScript -Label "Refresh handoff" -ScriptPath $handoffScript -Arguments @{ Path = $resolvedHandoffPath }
}

Write-Output "Refresh complete."
Write-Output ("Repository: {0}" -f $repoRoot)
if ($resolvedHandoffPath) {
  Write-Output ("Handoff: {0}" -f $resolvedHandoffPath)
}
