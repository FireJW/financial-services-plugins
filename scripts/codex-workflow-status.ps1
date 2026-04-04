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

function Get-LastSessionBlock {
  param(
    [string]$Path
  )

  if (-not (Test-Path $Path)) {
    return $null
  }

  $lines = Get-Content -LiteralPath $Path -Encoding UTF8
  $headerIndexes = @()
  for ($i = 0; $i -lt $lines.Count; $i += 1) {
    if ($lines[$i] -like '## *') {
      $headerIndexes += $i
    }
  }

  if ($headerIndexes.Count -eq 0) {
    return $null
  }

  $startIndex = $headerIndexes[$headerIndexes.Count - 1]
  $block = $lines[$startIndex..($lines.Count - 1)] | Where-Object { $_ -ne "" }
  return $block
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
$checkpointScript = Join-Path $PSScriptRoot "codex-commit-checkpoint.ps1"
if (-not (Test-Path -LiteralPath $checkpointScript)) {
  throw "Missing commit checkpoint script: $checkpointScript"
}

$checkpointState = & $checkpointScript -PassThru
if (-not $checkpointState) {
  throw "Commit checkpoint refresh failed."
}

$branch = [string]$checkpointState.branch
$statusLines = @(& git status --short)
if ($LASTEXITCODE -ne 0) {
  throw "git status failed."
}

$worktreeState = if ($statusLines.Count -eq 0) { "clean" } else { "dirty" }
$stagedCount = 0
$modifiedCount = 0
$untrackedCount = 0

foreach ($line in $statusLines) {
  if ($line.Length -lt 2) {
    continue
  }

  $indexStatus = $line.Substring(0, 1)
  $worktreeStatus = $line.Substring(1, 1)

  if ($indexStatus -ne " " -and $indexStatus -ne "?") {
    $stagedCount += 1
  }

  if ($worktreeStatus -ne " ") {
    if ($indexStatus -eq "?" -and $worktreeStatus -eq "?") {
      $untrackedCount += 1
    } else {
      $modifiedCount += 1
    }
  }
}

$sessionLogPath = Join-Path $repoRoot ".context\current\branches\$branch\session.log"
$statusDir = Join-Path $repoRoot ".context\current\branches\$branch"
$statusPath = Join-Path $statusDir "status.md"
$planPath = Join-Path $repoRoot ".claude\plan\repo-codex-flow-followups.md"
$handoffPath = Join-Path $repoRoot ".claude\handoff\repo-codex-flow-current.md"
$historyPath = Join-Path $repoRoot ".context\history\commits.md"
$latestSummaryPath = Join-Path $repoRoot ".context\history\latest-summary.md"

New-Item -ItemType Directory -Force -Path $statusDir | Out-Null

$lastSessionBlock = Get-LastSessionBlock -Path $sessionLogPath
$planLabel = if (Test-Path $planPath) { ".claude/plan/repo-codex-flow-followups.md" } else { "-" }
$handoffLabel = if (Test-Path $handoffPath) { ".claude/handoff/repo-codex-flow-current.md" } else { "-" }
$historyLabel = if (Test-Path $historyPath) { ".context/history/commits.md" } else { "-" }
$latestSummaryLabel = if (Test-Path $latestSummaryPath) { ".context/history/latest-summary.md" } else { "-" }
$commitCheckpointLabel = [string]$checkpointState.checkpoint_label
$sessionLogLabel = if (Test-Path $sessionLogPath) {
  ".context/current/branches/$branch/session.log"
} else {
  "-"
}

$lines = @(
  "# Codex Workflow Status",
  "",
  "## Snapshot",
  "",
  "| Item | Value |",
  "|------|-------|",
  "| Branch | $branch |",
  "| Worktree | $worktreeState |",
  "| Staged entries | $stagedCount |",
  "| Modified entries | $modifiedCount |",
  "| Untracked entries | $untrackedCount |",
  "| Latest commit | $([string]$checkpointState.short_commit) |",
  "| Latest commit date | $([string]$checkpointState.committed_at) |",
  "| Latest commit summary | $([string]$checkpointState.commit_summary) |",
  "| Active plan | $planLabel |",
  "| Active handoff | $handoffLabel |",
  "| Commit history | $historyLabel |",
  "| Latest summary | $latestSummaryLabel |",
  "| Local commit checkpoint | $commitCheckpointLabel |",
  "| Durable history coverage | $([string]$checkpointState.durable_history_coverage) |",
  "| Durable history head | $([string]$checkpointState.durable_history_head) |",
  "| Commits ahead of durable history | $([string]$checkpointState.commits_ahead_of_durable_history) |",
  "| Session log | $sessionLogLabel |",
  ""
)

if ($lastSessionBlock) {
  $lines += @(
    "## Latest Session Note",
    ""
  )
  $lines += $lastSessionBlock
  $lines += ""
}

if ($statusLines.Count -gt 0) {
  $lines += @(
    "## Git Status",
    "",
    '```text'
  )
  $lines += $statusLines
  $lines += @(
    '```',
    ""
  )
}

$lines += "## Resume Commands"
$lines += ""
$lines += '```powershell'
$lines += ("Set-Location '{0}'" -f $repoRoot)
$lines += "git status --short"
$lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-checkpoint.ps1"
$lines += ".\scripts\codex-workflow-status.ps1"
$lines += ("Get-Content .\.context\current\branches\{0}\status.md" -f $branch)
$lines += ("Get-Content .\.context\current\branches\{0}\latest-commit.md" -f $branch)
if (Test-Path $handoffPath) {
  $lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 5 -HandoffPath .\.claude\handoff\repo-codex-flow-current.md"
} else {
  $lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 5 -SkipHandoff"
}
if (Test-Path $handoffPath) {
  $lines += "Get-Content .\.claude\handoff\repo-codex-flow-current.md"
}
if (Test-Path $planPath) {
  $lines += "Get-Content .\.claude\plan\repo-codex-flow-followups.md"
}
if (Test-Path $historyPath) {
  $lines += "Get-Content .\.context\history\commits.md"
  $lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-sync.ps1 -Count 5"
}
if (Test-Path $latestSummaryPath) {
  $lines += "Get-Content .\.context\history\latest-summary.md"
  $lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-release-summary.ps1 -Count 5"
}
$lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1"
$lines += '```'
$lines += ""

Write-Utf8Bom -Path $statusPath -Lines $lines

$lines | Write-Output
Write-Output ""
Write-Output ('Status file: {0}' -f $statusPath)
