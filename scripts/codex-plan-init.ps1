param(
  [Parameter(Mandatory = $true)]
  [string]$Name
)

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$branch = (& git branch --show-current 2>$null)
if (-not $branch) {
  $branch = "main"
}

$templatePath = Join-Path $repoRoot ".claude\plan\TEMPLATE.md"
if (-not (Test-Path $templatePath)) {
  throw "Missing plan template at $templatePath"
}

$safeName = $Name.Trim().ToLower() -replace "[^a-z0-9\-]+", "-"
$safeName = $safeName.Trim("-")
if (-not $safeName) {
  throw "Plan name must contain at least one alphanumeric character."
}

$targetDir = Join-Path $repoRoot ".claude\plan"
$targetPath = Join-Path $targetDir "$safeName.md"
if (Test-Path $targetPath) {
  throw "Plan already exists: $targetPath"
}
$activePlanDir = Join-Path $repoRoot ".context\current\branches\$branch"
$activePlanPath = Join-Path $activePlanDir "active-plan.txt"
$relativePlanPath = ".claude\plan\$safeName.md"

$content = Get-Content -Raw -LiteralPath $templatePath -Encoding UTF8
$content = $content.Replace("<task-name>", $safeName)
$content = $content.Replace("<branch>", $branch)
$content = $content.Replace("C:\path\to\repo", $repoRoot)
$content = $content.Replace(
  "- Local checkpoint note:",
  '- Local checkpoint note: refresh `scripts/codex-commit-checkpoint.ps1` before trusting versioned durable history when local HEAD matters.'
)

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
New-Item -ItemType Directory -Force -Path $activePlanDir | Out-Null
Set-Content -LiteralPath $targetPath -Value $content -Encoding UTF8
Set-Content -LiteralPath $activePlanPath -Value $relativePlanPath -Encoding UTF8

Write-Output $targetPath
Write-Output ""
Write-Output ("Active plan registered: {0}" -f $relativePlanPath)
Write-Output ('Story loop shortcut: .\scripts\codex-story-loop.ps1 -Current')
