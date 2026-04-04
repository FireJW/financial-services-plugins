param(
  [Parameter(Mandatory = $true)]
  [string]$Path
)

function Write-Utf8BomText {
  param(
    [string]$Path,
    [string]$Content
  )

  $encoding = New-Object System.Text.UTF8Encoding($true)
  [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$repoRoot = (Resolve-Path -LiteralPath $repoRoot).Path

$targetPath = $Path
if (-not [System.IO.Path]::IsPathRooted($targetPath)) {
  $targetPath = Join-Path $repoRoot $targetPath
}

if (-not (Test-Path $targetPath)) {
  throw "Missing handoff file: $targetPath"
}

$targetPath = (Resolve-Path -LiteralPath $targetPath).Path

$branch = (& git branch --show-current 2>$null)
if (-not $branch) {
  $branch = "detached-head"
}

$statusLines = @(& git status --short)
if ($LASTEXITCODE -ne 0) {
  throw "git status failed."
}

$statusText = if ($statusLines.Count -eq 0) {
  "(clean)"
} else {
  $statusLines -join [Environment]::NewLine
}

$content = Get-Content -Raw -LiteralPath $targetPath -Encoding UTF8

$metaPattern = '(?s)<!-- codex:handoff-meta:start -->.*?<!-- codex:handoff-meta:end -->'
$gitStatusPattern = '(?s)<!-- codex:handoff-git-status:start -->.*?<!-- codex:handoff-git-status:end -->'

if (-not [regex]::IsMatch($content, $metaPattern)) {
  throw "Missing handoff meta marker block in $targetPath"
}

if (-not [regex]::IsMatch($content, $gitStatusPattern)) {
  throw "Missing handoff git status marker block in $targetPath"
}

$timestamp = Get-Date -Format o

$metaReplacement = @(
  '<!-- codex:handoff-meta:start -->',
  "- Last updated: $timestamp",
  "- Branch: $branch",
  "- Working directory: $repoRoot",
  '<!-- codex:handoff-meta:end -->'
) -join [Environment]::NewLine

$gitStatusReplacement = @(
  '<!-- codex:handoff-git-status:start -->',
  '```text',
  $statusText,
  '```',
  '<!-- codex:handoff-git-status:end -->'
) -join [Environment]::NewLine

$content = [regex]::Replace(
  $content,
  $metaPattern,
  [System.Text.RegularExpressions.MatchEvaluator]{
    param($match)
    $metaReplacement
  }
)

$content = [regex]::Replace(
  $content,
  $gitStatusPattern,
  [System.Text.RegularExpressions.MatchEvaluator]{
    param($match)
    $gitStatusReplacement
  }
)

$content = [regex]::Replace($content, '(?:\r?\n)+\z', "`r`n")

Write-Utf8BomText -Path $targetPath -Content $content
Write-Output $targetPath
