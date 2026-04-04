param(
  [switch]$PassThru,
  [switch]$SkipWrite
)

function Write-Utf8Bom {
  param(
    [string]$Path,
    [string[]]$Lines
  )

  $encoding = New-Object System.Text.UTF8Encoding($true)
  $content = if ($Lines.Count -eq 0) {
    ""
  } else {
    ($Lines -join "`r`n") + "`r`n"
  }
  [System.IO.File]::WriteAllText($Path, $content, $encoding)
}

function Get-FirstJsonLine {
  param(
    [string]$Path
  )

  if (-not (Test-Path $Path)) {
    return $null
  }

  $lines = Get-Content -LiteralPath $Path -Encoding UTF8
  foreach ($line in $lines) {
    if ($line.Trim()) {
      return ($line | ConvertFrom-Json)
    }
  }

  return $null
}

function Get-DurableHistoryState {
  param(
    [string]$JsonlPath,
    [string]$HeadCommit
  )

  $state = [ordered]@{
    coverage = "missing"
    ahead_count = ""
    short_commit = ""
    summary = ""
  }

  $entry = Get-FirstJsonLine -Path $JsonlPath
  if (-not $entry) {
    return [pscustomobject]$state
  }

  $state.short_commit = [string]$entry.short_commit
  $state.summary = [string]$entry.summary

  if ([string]$entry.commit -eq $HeadCommit) {
    $state.coverage = "synced"
    $state.ahead_count = "0"
    return [pscustomobject]$state
  }

  & git merge-base --is-ancestor ([string]$entry.commit) $HeadCommit 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) {
    $aheadCount = (& git rev-list --count "$([string]$entry.commit)..$HeadCommit" 2>$null)
    $state.coverage = "lagging"
    $state.ahead_count = [string]$aheadCount
    return [pscustomobject]$state
  }

  $state.coverage = "diverged"
  return [pscustomobject]$state
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
$branch = (& git branch --show-current 2>$null)
if (-not $branch) {
  $branch = "detached-head"
}

$commitRecord = (& git log -1 "--date=iso-strict" "--pretty=format:%H%x1f%h%x1f%aI%x1f%s")
if ($LASTEXITCODE -ne 0) {
  throw "git log failed."
}

$commitFields = $commitRecord -split [char]0x1f, 4
$commit = if ($commitFields.Count -ge 1) { $commitFields[0] } else { "" }
$shortCommit = if ($commitFields.Count -ge 2) { $commitFields[1] } else { "" }
$committedAt = if ($commitFields.Count -ge 3) { $commitFields[2] } else { "" }
$commitSummary = if ($commitFields.Count -ge 4) { $commitFields[3] } else { "" }

$statusDir = Join-Path $repoRoot ".context\current\branches\$branch"
$commitCheckpointPath = Join-Path $statusDir "latest-commit.md"
$historyJsonlPath = Join-Path $repoRoot ".context\history\commits.jsonl"
$commitCheckpointLabel = ".context/current/branches/$branch/latest-commit.md"
$refreshCommand = "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 30 -HandoffPath .\.claude\handoff\repo-codex-flow-current.md"

New-Item -ItemType Directory -Force -Path $statusDir | Out-Null

$durableHistoryState = Get-DurableHistoryState -JsonlPath $historyJsonlPath -HeadCommit $commit

$checkpointLines = @(
  "# Latest Commit Checkpoint",
  "",
  "| Item | Value |",
  "|------|-------|",
  "| Branch | $branch |",
  "| Latest commit | $shortCommit |",
  "| Latest commit date | $committedAt |",
  "| Latest commit summary | $commitSummary |",
  "| Durable history coverage | $($durableHistoryState.coverage) |",
  "| Durable history head | $($durableHistoryState.short_commit) |",
  "| Durable history summary | $($durableHistoryState.summary) |",
  "| Commits ahead of durable history | $($durableHistoryState.ahead_count) |",
  "| Refresh command | $refreshCommand |",
  ""
)

if ($durableHistoryState.coverage -eq "lagging") {
  $checkpointLines += "Durable history is a versioned snapshot and currently trails `HEAD`."
  $checkpointLines += "Use the refresh flow after pausing or before handoff to rebuild the durable summary files."
  $checkpointLines += ""
}

if (-not $SkipWrite) {
  Write-Utf8Bom -Path $commitCheckpointPath -Lines $checkpointLines
}

$result = [pscustomobject]@{
  repo_root = $repoRoot
  branch = $branch
  commit = $commit
  short_commit = $shortCommit
  committed_at = $committedAt
  commit_summary = $commitSummary
  checkpoint_path = $commitCheckpointPath
  checkpoint_label = $commitCheckpointLabel
  durable_history_coverage = [string]$durableHistoryState.coverage
  durable_history_head = [string]$durableHistoryState.short_commit
  durable_history_summary = [string]$durableHistoryState.summary
  commits_ahead_of_durable_history = [string]$durableHistoryState.ahead_count
  refresh_command = $refreshCommand
}

if ($PassThru) {
  $result
  return
}

$checkpointLines | Write-Output
Write-Output ""
if ($SkipWrite) {
  Write-Output ("Checkpoint write skipped: {0}" -f $commitCheckpointPath)
} else {
  Write-Output ("Checkpoint file: {0}" -f $commitCheckpointPath)
}
