param(
  [Parameter(Mandatory = $true)]
  [string]$Summary,

  [string]$Decision,
  [string]$Reason,
  [string]$Risk,
  [string]$Alternatives
)

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$branch = (& git branch --show-current 2>$null)
if (-not $branch) {
  $branch = "detached-head"
}

$logDir = Join-Path $repoRoot ".context\current\branches\$branch"
$logPath = Join-Path $logDir "session.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$timestamp = Get-Date -Format o
$lines = @(
  "## $timestamp",
  "**Summary**: $Summary"
)

if ($Decision) {
  $lines += "**Decision**: $Decision"
}
if ($Reason) {
  $lines += "**Reason**: $Reason"
}
if ($Alternatives) {
  $lines += "**Alternatives**: $Alternatives"
}
if ($Risk) {
  $lines += "**Risk**: $Risk"
}

$lines += ""

Add-Content -LiteralPath $logPath -Value $lines -Encoding UTF8
Write-Output $logPath
