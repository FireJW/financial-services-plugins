param(
  [Parameter(Mandatory = $true)]
  [string]$Path
)

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
$branch = (& git branch --show-current 2>$null)
if (-not $branch) {
  $branch = "main"
}

$resolvedPlanPath = if ([System.IO.Path]::IsPathRooted($Path)) {
  (Resolve-Path -LiteralPath $Path).Path
} else {
  (Resolve-Path -LiteralPath (Join-Path $repoRoot $Path)).Path
}

if (-not ($resolvedPlanPath.EndsWith(".md"))) {
  throw "Active plan must point to a markdown file."
}

$relativePlanPath = Get-RepoRelativePath -BasePath $repoRoot -TargetPath $resolvedPlanPath
$activePlanDir = Join-Path $repoRoot ".context\current\branches\$branch"
$activePlanPath = Join-Path $activePlanDir "active-plan.txt"

New-Item -ItemType Directory -Force -Path $activePlanDir | Out-Null
Set-Content -LiteralPath $activePlanPath -Value $relativePlanPath -Encoding UTF8

Write-Output $resolvedPlanPath
Write-Output ""
Write-Output ("Active plan registered: {0}" -f $relativePlanPath)
Write-Output ('Story loop shortcut: .\scripts\codex-story-loop.ps1 -Current')
