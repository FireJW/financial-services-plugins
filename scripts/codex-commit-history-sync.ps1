param(
  [ValidateRange(1, 200)]
  [int]$Count = 10
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

function Write-Utf8NoBom {
  param(
    [string]$Path,
    [string[]]$Lines
  )

  $encoding = New-Object System.Text.UTF8Encoding($false)
  $content = if ($Lines.Count -eq 0) {
    ""
  } else {
    ($Lines -join "`n") + "`n"
  }
  [System.IO.File]::WriteAllText($Path, $content, $encoding)
}

function Escape-MarkdownCell {
  param(
    [string]$Value
  )

  if ($null -eq $Value) {
    return ""
  }

  return $Value.Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
}

function Read-ExistingCommitIndex {
  param(
    [string]$Path
  )

  $index = @{}
  if (-not (Test-Path $Path)) {
    return $index
  }

  $lines = Get-Content -LiteralPath $Path -Encoding UTF8
  foreach ($line in $lines) {
    if (-not $line.Trim()) {
      continue
    }

    $entry = $line | ConvertFrom-Json
    if ($entry.commit) {
      $index[$entry.commit] = $entry
    }
  }

  return $index
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
$historyDir = Join-Path $repoRoot ".context\history"
$jsonlPath = Join-Path $historyDir "commits.jsonl"
$markdownPath = Join-Path $historyDir "commits.md"

New-Item -ItemType Directory -Force -Path $historyDir | Out-Null

$existingEntries = Read-ExistingCommitIndex -Path $jsonlPath
$records = @(& git log "-$Count" "--date=iso-strict" "--pretty=format:%H%x1f%h%x1f%aI%x1f%s")
if ($LASTEXITCODE -ne 0) {
  throw "git log failed."
}

$entries = New-Object System.Collections.Generic.List[object]
foreach ($record in $records) {
  if (-not $record) {
    continue
  }

  $fields = $record -split [char]0x1f, 4
  $commitHash = if ($fields.Count -ge 1) { $fields[0] } else { "" }
  $shortCommit = if ($fields.Count -ge 2) { $fields[1] } else { "" }
  $committedAt = if ($fields.Count -ge 3) { $fields[2] } else { "" }
  $summary = if ($fields.Count -ge 4) { $fields[3] } else { "" }

  $existingEntry = $null
  if ($existingEntries.ContainsKey($commitHash)) {
    $existingEntry = $existingEntries[$commitHash]
  }

  $entry = [ordered]@{
    commit = $commitHash
    short_commit = $shortCommit
    committed_at = $committedAt
    summary = $summary
    context_id = if ($existingEntry) { [string]$existingEntry.context_id } else { "" }
    decisions = if ($existingEntry) { [string]$existingEntry.decisions } else { "" }
    bugs = if ($existingEntry) { [string]$existingEntry.bugs } else { "" }
    risk = if ($existingEntry) { [string]$existingEntry.risk } else { "" }
  }

  $entries.Add([pscustomobject]$entry)
}

$jsonLines = @()
foreach ($entry in $entries) {
  $jsonLines += ($entry | ConvertTo-Json -Compress -Depth 4)
}
Write-Utf8NoBom -Path $jsonlPath -Lines $jsonLines

$markdownLines = @(
  '# Commit Decision History',
  '',
  'Canonical store: `commits.jsonl`',
  '',
  '| Date | Context Id | Commit | Summary | Decisions | Bugs | Risk |',
  '|------|------------|--------|---------|-----------|------|------|'
)

foreach ($entry in $entries) {
  $dateLabel = ""
  if ($entry.committed_at) {
    $dateLabel = ($entry.committed_at -split "T", 2)[0]
  }

  $markdownLines += (
    "| {0} | {1} | {2} | {3} | {4} | {5} | {6} |" -f
    (Escape-MarkdownCell $dateLabel),
    (Escape-MarkdownCell ([string]$entry.context_id)),
    (Escape-MarkdownCell ([string]$entry.short_commit)),
    (Escape-MarkdownCell ([string]$entry.summary)),
    (Escape-MarkdownCell ([string]$entry.decisions)),
    (Escape-MarkdownCell ([string]$entry.bugs)),
    (Escape-MarkdownCell ([string]$entry.risk))
  )
}

Write-Utf8Bom -Path $markdownPath -Lines $markdownLines

Write-Output $jsonlPath
Write-Output $markdownPath
