param(
  [Parameter(Mandatory = $true)]
  [string]$Commit,

  [string]$ContextId,
  [string]$Decisions,
  [string]$Bugs,
  [string]$Risk
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

function Render-CommitMarkdown {
  param(
    [object[]]$Entries
  )

  $lines = @(
    '# Commit Decision History',
    '',
    'Canonical store: `commits.jsonl`',
    '',
    '| Date | Context Id | Commit | Summary | Decisions | Bugs | Risk |',
    '|------|------------|--------|---------|-----------|------|------|'
  )

  foreach ($entry in $Entries) {
    $dateLabel = ""
    if ($entry.committed_at) {
      $dateLabel = ([string]$entry.committed_at -split "T", 2)[0]
    }

    $lines += (
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

  return $lines
}

$updatedFields = @(
  "ContextId",
  "Decisions",
  "Bugs",
  "Risk"
) | Where-Object { $PSBoundParameters.ContainsKey($_) }

if ($updatedFields.Count -eq 0) {
  throw "Specify at least one field to update: -ContextId, -Decisions, -Bugs, or -Risk."
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
$historyDir = Join-Path $repoRoot ".context\history"
$jsonlPath = Join-Path $historyDir "commits.jsonl"
$markdownPath = Join-Path $historyDir "commits.md"

if (-not (Test-Path $jsonlPath)) {
  throw "Missing commit history file: $jsonlPath"
}

$entries = New-Object System.Collections.Generic.List[object]
$matchedIndex = -1
$lines = Get-Content -LiteralPath $jsonlPath -Encoding UTF8
for ($i = 0; $i -lt $lines.Count; $i += 1) {
  $line = $lines[$i]
  if (-not $line.Trim()) {
    continue
  }

  $entry = $line | ConvertFrom-Json
  $entries.Add($entry)

  if ($entry.commit -eq $Commit -or $entry.short_commit -eq $Commit) {
    $matchedIndex = $entries.Count - 1
  }
}

if ($matchedIndex -lt 0) {
  throw "Commit '$Commit' was not found in $jsonlPath. Run codex-commit-history-sync.ps1 with a larger -Count first."
}

$targetEntry = $entries[$matchedIndex]
if ($PSBoundParameters.ContainsKey("ContextId")) {
  $targetEntry.context_id = $ContextId
}
if ($PSBoundParameters.ContainsKey("Decisions")) {
  $targetEntry.decisions = $Decisions
}
if ($PSBoundParameters.ContainsKey("Bugs")) {
  $targetEntry.bugs = $Bugs
}
if ($PSBoundParameters.ContainsKey("Risk")) {
  $targetEntry.risk = $Risk
}

$jsonLines = @()
foreach ($entry in $entries) {
  $jsonLines += ($entry | ConvertTo-Json -Compress -Depth 4)
}
Write-Utf8NoBom -Path $jsonlPath -Lines $jsonLines

$markdownLines = Render-CommitMarkdown -Entries $entries
Write-Utf8Bom -Path $markdownPath -Lines $markdownLines

Write-Output $jsonlPath
Write-Output $markdownPath
