param(
  [Parameter(Mandatory = $true)]
  [string]$Name
)

$repoRoot = (& git rev-parse --show-toplevel 2>$null)
if (-not $repoRoot) {
  throw "Not inside a git repository."
}

$templatePath = Join-Path $repoRoot ".context\templates\review-report-template.md"
if (-not (Test-Path $templatePath)) {
  throw "Missing review template at $templatePath"
}

$safeName = $Name.Trim().ToLower() -replace "[^a-z0-9\-]+", "-"
$safeName = $safeName.Trim("-")
if (-not $safeName) {
  throw "Review name must contain at least one alphanumeric character."
}

$targetDir = Join-Path $repoRoot ".context\current\reviews"
$targetPath = Join-Path $targetDir "$safeName-review.md"
if (Test-Path $targetPath) {
  throw "Review already exists: $targetPath"
}

$content = Get-Content -Raw -LiteralPath $templatePath -Encoding UTF8
$content = $content.Replace("<task-name>", $safeName)

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Set-Content -LiteralPath $targetPath -Value $content -Encoding UTF8

Write-Output $targetPath
