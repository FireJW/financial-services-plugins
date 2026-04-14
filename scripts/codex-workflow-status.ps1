param(
  [switch]$SkipCheckpointRefresh
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

function Get-RepoRelativePath {
  param(
    [string]$BasePath,
    [string]$TargetPath
  )

  $normalizedBase = [System.IO.Path]::GetFullPath($BasePath).TrimEnd('\', '/')
  $normalizedTarget = [System.IO.Path]::GetFullPath($TargetPath)

  if ($normalizedTarget.StartsWith($normalizedBase, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $normalizedTarget.Substring($normalizedBase.Length).TrimStart('\', '/')
  }

  return $normalizedTarget
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

$checkpointArgs = @{ PassThru = $true }
if ($SkipCheckpointRefresh) {
  $checkpointArgs.SkipWrite = $true
}

$checkpointState = & $checkpointScript @checkpointArgs
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
$branchActivePlanPointerPath = Join-Path $statusDir "active-plan.txt"
$fallbackPlanPath = Join-Path $repoRoot ".claude\plan\repo-codex-flow-followups.md"
$planPath = $null
$handoffPath = Join-Path $repoRoot ".claude\handoff\repo-codex-flow-current.md"
$historyPath = Join-Path $repoRoot ".context\history\commits.md"
$latestSummaryPath = Join-Path $repoRoot ".context\history\latest-summary.md"
$storyLoopScript = Join-Path $repoRoot "scripts\runtime\auto-story-loop.mjs"

New-Item -ItemType Directory -Force -Path $statusDir | Out-Null

$lastSessionBlock = Get-LastSessionBlock -Path $sessionLogPath
$activePlanRelativePath = $null
if (Test-Path -LiteralPath $branchActivePlanPointerPath) {
  $candidateRelativePath = (Get-Content -LiteralPath $branchActivePlanPointerPath -Encoding UTF8 | Select-Object -First 1).Trim()
  if ($candidateRelativePath) {
    $candidatePlanPath = if ([System.IO.Path]::IsPathRooted($candidateRelativePath)) {
      $candidateRelativePath
    } else {
      Join-Path $repoRoot $candidateRelativePath
    }
    if (Test-Path -LiteralPath $candidatePlanPath) {
      $planPath = (Resolve-Path -LiteralPath $candidatePlanPath).Path
      $activePlanRelativePath = Get-RepoRelativePath -BasePath $repoRoot -TargetPath $planPath
    }
  }
}
if (-not $planPath -and (Test-Path -LiteralPath $fallbackPlanPath)) {
  $planPath = (Resolve-Path -LiteralPath $fallbackPlanPath).Path
  $activePlanRelativePath = Get-RepoRelativePath -BasePath $repoRoot -TargetPath $planPath
}
$planLabel = if ($activePlanRelativePath) { $activePlanRelativePath } else { "-" }
$handoffLabel = if (Test-Path $handoffPath) { ".claude/handoff/repo-codex-flow-current.md" } else { "-" }
$historyLabel = if (Test-Path $historyPath) { ".context/history/commits.md" } else { "-" }
$latestSummaryLabel = if (Test-Path $latestSummaryPath) { ".context/history/latest-summary.md" } else { "-" }
$commitCheckpointLabel = [string]$checkpointState.checkpoint_label
$storyLoopInfo = $null
$storyLoopLabel = "-"
$storyLoopCommand = ".\scripts\codex-story-loop.ps1"
$storyLoopStatusCommand = ".\scripts\codex-story-loop.ps1 -StatusOnly"
$sessionLogLabel = if (Test-Path $sessionLogPath) {
  ".context/current/branches/$branch/session.log"
} else {
  "-"
}

if (Test-Path -LiteralPath $storyLoopScript) {
  try {
    $storyLoopRaw = & node $storyLoopScript --status-only --json 2>$null
    if ($LASTEXITCODE -eq 0 -and $storyLoopRaw) {
      $storyLoopInfo = ($storyLoopRaw -join "`n") | ConvertFrom-Json
      if ($storyLoopInfo.autoAction -eq "eligible_plan_detected") {
        $storyLoopLabel = "eligible-plan"
      } elseif ($storyLoopInfo.status) {
        $storyLoopState = [string]$storyLoopInfo.status.state
        $storyLoopTitle = [string](($storyLoopInfo.status.activeStory | Select-Object -ExpandProperty title -ErrorAction SilentlyContinue))
        $storyLoopLabel = if ($storyLoopTitle) {
          "$storyLoopState :: $storyLoopTitle"
        } else {
          $storyLoopState
        }
      }
    }
  } catch {
    $storyLoopInfo = $null
    $storyLoopLabel = "-"
  }
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
  "| Story loop | $storyLoopLabel |",
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

if ($storyLoopInfo -and ($storyLoopInfo.autoAction -ne "no_candidate" -or $storyLoopInfo.context.reason -in @("active_plan_has_no_runnable_story", "active_plan_not_story_loop_ready"))) {
  $lines += @(
    "## Story Loop",
    ""
  )

  if ($storyLoopInfo.autoAction -eq "eligible_plan_detected") {
    $lines += "- Status: eligible plan detected but no loop exists yet."
    $lines += "- Plan: $([string]$storyLoopInfo.context.planPath)"
    $lines += "- Suggested loop id: $([string]$storyLoopInfo.context.loopId)"
    $lines += "- Start command: $storyLoopCommand -PlanFile ""$([string]$storyLoopInfo.context.planPath)"" -LoopId ""$([string]$storyLoopInfo.context.loopId)"""
    $lines += ""
  } elseif ($storyLoopInfo.context.reason -eq "active_plan_not_story_loop_ready") {
    $lines += "- Status: the active plan exists, but it is not story-loop-ready yet."
    $lines += "- Plan: $([string]$storyLoopInfo.context.planPath)"
    $lines += "- Next step: add a real `## Implementation Units` section with runnable `### [ ]` units."
    $lines += ""
  } elseif ($storyLoopInfo.context.reason -eq "active_plan_has_no_runnable_story") {
    $lines += "- Status: the active plan exists, but it does not have runnable implementation units yet."
    $lines += "- Plan: $([string]$storyLoopInfo.context.planPath)"
    $lines += "- Next step: replace template example blocks with real `### [ ]` units before starting the story loop."
    $lines += ""
  } elseif ($storyLoopInfo.status) {
    $storyLoopStatus = $storyLoopInfo.status
    $activeStoryTitle = [string](($storyLoopStatus.activeStory | Select-Object -ExpandProperty title -ErrorAction SilentlyContinue))
    $activeStoryStatus = [string](($storyLoopStatus.activeStory | Select-Object -ExpandProperty status -ErrorAction SilentlyContinue))
    $latestRunPath = [string]$storyLoopStatus.latestRunPath
    $lines += "- State: $([string]$storyLoopStatus.state)"
    $lines += "- Loop dir: $([string]$storyLoopStatus.loopDir)"
    if ($activeStoryTitle) {
      $lines += "- Current story: $activeStoryStatus / $activeStoryTitle"
    }
    if ($latestRunPath) {
      $lines += "- Latest run: $latestRunPath"
    }
    if ([string]$storyLoopStatus.state -eq "waiting_for_git_gate") {
      $lines += "- Next action: $storyLoopCommand -LoopDir ""$([string]$storyLoopStatus.loopDir)"" -ConfirmGitReady"
    } elseif ([string]$storyLoopStatus.state -ne "complete") {
      $lines += "- Next action: $storyLoopCommand -LoopDir ""$([string]$storyLoopStatus.loopDir)"""
    }
    $lines += ""
  }
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
  $lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 30 -HandoffPath .\.claude\handoff\repo-codex-flow-current.md"
} else {
  $lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-refresh.ps1 -Count 30 -SkipHandoff"
}
if (Test-Path $handoffPath) {
  $lines += "Get-Content .\.claude\handoff\repo-codex-flow-current.md"
}
if (Test-Path $planPath) {
  $planRelativeForResume = Get-RepoRelativePath -BasePath $repoRoot -TargetPath $planPath
  $lines += ("Get-Content .\{0}" -f $planRelativeForResume.Replace("/", "\"))
}
if ($storyLoopInfo) {
  $lines += $storyLoopStatusCommand
  if ($storyLoopInfo.status) {
    $loopDirValue = [string]$storyLoopInfo.status.loopDir
    if ($loopDirValue) {
      if ([string]$storyLoopInfo.status.state -eq "waiting_for_git_gate") {
        $lines += ("{0} -LoopDir ""{1}"" -ConfirmGitReady" -f $storyLoopCommand, $loopDirValue)
      } elseif ([string]$storyLoopInfo.status.state -ne "complete") {
        $lines += ("{0} -LoopDir ""{1}""" -f $storyLoopCommand, $loopDirValue)
      }
    }
  } elseif ($storyLoopInfo.autoAction -eq "eligible_plan_detected") {
    $lines += ("{0} -PlanFile ""{1}"" -LoopId ""{2}""" -f $storyLoopCommand, [string]$storyLoopInfo.context.planPath, [string]$storyLoopInfo.context.loopId)
  }
}
if (Test-Path $historyPath) {
  $lines += "Get-Content .\.context\history\commits.md"
  $lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-commit-history-sync.ps1 -Count 30"
}
if (Test-Path $latestSummaryPath) {
  $lines += "Get-Content .\.context\history\latest-summary.md"
  $lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-release-summary.ps1 -Count 30"
}
$lines += "& 'C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe' -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-workflow-status.ps1"
$lines += '```'
$lines += ""

Write-Utf8Bom -Path $statusPath -Lines $lines

$lines | Write-Output
Write-Output ""
Write-Output ('Status file: {0}' -f $statusPath)
