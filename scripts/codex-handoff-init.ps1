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

$templatePath = Join-Path $repoRoot ".context\templates\handoff-template.md"
if (-not (Test-Path $templatePath)) {
  throw "Missing handoff template at $templatePath"
}

$safeName = $Name.Trim().ToLower() -replace "[^a-z0-9\-]+", "-"
$safeName = $safeName.Trim("-")
if (-not $safeName) {
  throw "Handoff name must contain at least one alphanumeric character."
}

$targetDir = Join-Path $repoRoot ".claude\handoff"
$targetPath = Join-Path $targetDir "$safeName.md"
if (Test-Path $targetPath) {
  throw "Handoff already exists: $targetPath"
}

$content = Get-Content -Raw -LiteralPath $templatePath -Encoding UTF8
$content = $content.Replace("<task-name>", $safeName)
$content = $content.Replace("<branch>", $branch)
$content = $content.Replace("C:\path\to\repo", $repoRoot)

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Set-Content -LiteralPath $targetPath -Value $content -Encoding UTF8

$refreshScript = Join-Path $repoRoot "scripts\codex-handoff-refresh.ps1"
if (Test-Path $refreshScript) {
  & $refreshScript -Path $targetPath | Out-Null
}

Write-Output $targetPath
