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

function Escape-MarkdownCell {
  param(
    [string]$Value
  )

  if ($null -eq $Value) {
    return ""
  }

  return $Value.Replace("|", "\|").Replace("`r", " ").Replace("`n", " ")
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path
$jsonlPath = Join-Path $repoRoot ".context\history\commits.jsonl"
$summaryPath = Join-Path $repoRoot ".context\history\latest-summary.md"

if (-not (Test-Path $jsonlPath)) {
  throw "Missing commit history file: $jsonlPath"
}

$entries = New-Object System.Collections.Generic.List[object]
$lines = Get-Content -LiteralPath $jsonlPath -Encoding UTF8
foreach ($line in $lines) {
  if (-not $line.Trim()) {
    continue
  }

  $entries.Add(($line | ConvertFrom-Json))
  if ($entries.Count -ge $Count) {
    break
  }
}

$enrichedEntries = @(
  $entries | Where-Object {
    $_.context_id -or $_.decisions -or $_.bugs -or $_.risk
  }
)

$summaryLines = @(
  "# Recent Commit Summary",
  "",
  "Generated from `commits.jsonl`.",
  "",
  "## Snapshot",
  "",
  "| Item | Value |",
  "|------|-------|",
  ("| Selected commits | {0} |" -f $entries.Count),
  ("| Enriched commits | {0} |" -f $enrichedEntries.Count),
  "",
  "## Recent Commits",
  "",
  "| Date | Commit | Summary | Context Id |",
  "|------|--------|---------|------------|"
)

foreach ($entry in $entries) {
  $dateLabel = ""
  if ($entry.committed_at) {
    $dateLabel = ([string]$entry.committed_at -split "T", 2)[0]
  }

  $summaryLines += (
    "| {0} | {1} | {2} | {3} |" -f
    (Escape-MarkdownCell $dateLabel),
    (Escape-MarkdownCell ([string]$entry.short_commit)),
    (Escape-MarkdownCell ([string]$entry.summary)),
    (Escape-MarkdownCell ([string]$entry.context_id))
  )
}

$summaryLines += ""
$summaryLines += "## Enriched Notes"
$summaryLines += ""

if ($enrichedEntries.Count -eq 0) {
  $summaryLines += "No enriched commit rows in the selected window."
} else {
  $summaryLines += "| Commit | Decisions | Bugs | Risk |"
  $summaryLines += "|--------|-----------|------|------|"

  foreach ($entry in $enrichedEntries) {
    $summaryLines += (
      "| {0} | {1} | {2} | {3} |" -f
      (Escape-MarkdownCell ([string]$entry.short_commit)),
      (Escape-MarkdownCell ([string]$entry.decisions)),
      (Escape-MarkdownCell ([string]$entry.bugs)),
      (Escape-MarkdownCell ([string]$entry.risk))
    )
  }
}

$summaryLines += ""

Write-Utf8Bom -Path $summaryPath -Lines $summaryLines
Write-Output $summaryPath
