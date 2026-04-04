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
$branch = (& git branch --show-current 2>$null)
if (-not $branch) {
  $branch = "detached-head"
}

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

$commitRecord = (& git log -1 "--date=iso-strict" "--pretty=format:%H%x1f%h%x1f%aI%x1f%s")
if ($LASTEXITCODE -ne 0) {
  throw "git log failed."
}

$commitFields = $commitRecord -split [char]0x1f, 4
$shortCommit = if ($commitFields.Count -ge 2) { $commitFields[1] } else { "" }
$committedAt = if ($commitFields.Count -ge 3) { $commitFields[2] } else { "" }
$commitSummary = if ($commitFields.Count -ge 4) { $commitFields[3] } else { "" }

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
  "| Latest commit | $shortCommit |",
  "| Latest commit date | $committedAt |",
  "| Latest commit summary | $commitSummary |",
  "| Active plan | $planLabel |",
  "| Active handoff | $handoffLabel |",
  "| Commit history | $historyLabel |",
  "| Latest summary | $latestSummaryLabel |",
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
$lines += ".\scripts\codex-workflow-status.ps1"
$lines += ("Get-Content .\.context\current\branches\{0}\status.md" -f $branch)
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
