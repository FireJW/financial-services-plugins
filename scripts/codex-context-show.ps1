$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$branch = (& git branch --show-current 2>$null)
if (-not $branch) {
  $branch = "detached-head"
}

$logPath = Join-Path $repoRoot ".context\current\branches\$branch\session.log"

if (-not (Test-Path $logPath)) {
  Write-Output "No session log for branch '$branch'."
  exit 0
}

Get-Content -LiteralPath $logPath
