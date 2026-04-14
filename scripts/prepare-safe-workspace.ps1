param(
  [string]$SourceRoot = ".",
  [string]$TargetRoot,
  [switch]$IncludeGit,
  [switch]$IncludeTmp,
  [switch]$Execute
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
  param([string]$PathValue)

  $resolved = (Resolve-Path -LiteralPath $PathValue).Path
  try {
    $gitRoot = (& git -C $resolved rev-parse --show-toplevel 2>$null)
    if ($gitRoot) {
      return (Resolve-Path -LiteralPath $gitRoot).Path
    }
  } catch {
  }

  return $resolved
}

function Resolve-TargetPath {
  param([string]$PathValue)

  if ([System.IO.Path]::IsPathRooted($PathValue)) {
    return $PathValue
  }

  return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $PathValue))
}

function Get-UnreadableDirectories {
  param([string]$Root)

  $bad = New-Object System.Collections.Generic.List[string]
  Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match "^tmp[a-z0-9]{7,}$" } |
    ForEach-Object { [void]$bad.Add($_.FullName) }

  Get-ChildItem -LiteralPath $Root -Recurse -Directory -Force -ErrorAction SilentlyContinue |
    ForEach-Object {
      try {
        Get-ChildItem -LiteralPath $_.FullName -Force -ErrorAction Stop | Out-Null
      } catch {
        [void]$bad.Add($_.FullName)
        return
      }

      try {
        Get-Acl -LiteralPath $_.FullName -ErrorAction Stop | Out-Null
      } catch {
        [void]$bad.Add($_.FullName)
      }
    }

  return @($bad | Sort-Object -Unique)
}

function Test-RiskyTarget {
  param([string]$PathValue)

  return (
    $PathValue -match "\\\.gemini\\antigravity\\scratch(\\|$)" -or
    $PathValue -match "\\\.codex\\worktrees(\\|$)" -or
    $PathValue -match "\\AppData\\Local\\Temp(\\|$)"
  )
}

function Invoke-RobocopySafe {
  param(
    [string]$From,
    [string]$To,
    [string[]]$ExcludeDirs
  )

  $arguments = @(
    $From,
    $To,
    "/E",
    "/R:1",
    "/W:1",
    "/COPY:DAT",
    "/DCOPY:DAT",
    "/NFL",
    "/NDL",
    "/NJH",
    "/NJS",
    "/NP"
  )

  if ($ExcludeDirs.Count -gt 0) {
    $arguments += "/XD"
    $arguments += $ExcludeDirs
  }

  $output = & robocopy @arguments 2>&1
  if ($LASTEXITCODE -gt 7) {
    $tail = ($output | Select-Object -Last 40 | Out-String).Trim()
    throw ("robocopy failed with exit code {0}`n{1}" -f $LASTEXITCODE, $tail)
  }
}

$repoRoot = Resolve-RepoRoot -PathValue $SourceRoot
$repoName = Split-Path -Leaf $repoRoot

if (-not $TargetRoot) {
  $TargetRoot = "D:\Users\rickylu\dev"
}

$TargetRoot = Resolve-TargetPath -PathValue $TargetRoot

$targetRepoPath = Join-Path $TargetRoot $repoName

if (Test-RiskyTarget -PathValue $targetRepoPath) {
  throw "Refusing to migrate into another scratch/temp/worktree-style path: $targetRepoPath"
}

$excludeDirs = New-Object System.Collections.Generic.List[string]
if (-not $IncludeGit) {
  $excludeDirs.Add((Join-Path $repoRoot ".git"))
}
if (-not $IncludeTmp) {
  Get-ChildItem -LiteralPath $repoRoot -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq ".tmp" -or $_.Name -like ".tmp-*" -or $_.Name -like "tmp-*" } |
    ForEach-Object { [void]$excludeDirs.Add($_.FullName) }
}

foreach ($badDir in (Get-UnreadableDirectories -Root $repoRoot)) {
  [void]$excludeDirs.Add($badDir)
}

if (-not $Execute) {
  Write-Output ("Source repo: {0}" -f $repoRoot)
  Write-Output ("Target repo: {0}" -f $targetRepoPath)
  Write-Output ("Include .git: {0}" -f ([bool]$IncludeGit))
  Write-Output ("Include .tmp*: {0}" -f ([bool]$IncludeTmp))
  Write-Output ""
  Write-Output "Dry run only. To execute the migration, run:"
  Write-Output (".\scripts\prepare-safe-workspace.ps1 -TargetRoot `"{0}`" {1}{2}-Execute" -f $TargetRoot, $(if ($IncludeGit) { "-IncludeGit " } else { "" }), $(if ($IncludeTmp) { "-IncludeTmp " } else { "" }))
  exit 0
}

New-Item -ItemType Directory -Force -Path $targetRepoPath | Out-Null
Invoke-RobocopySafe -From $repoRoot -To $targetRepoPath -ExcludeDirs @($excludeDirs)

$readmePath = Join-Path $targetRepoPath ".repo-safety-location.txt"
$lines = @(
  ("Created at: {0}" -f (Get-Date).ToString("o")),
  ("Source repo: {0}" -f $repoRoot),
  ("Target repo: {0}" -f $targetRepoPath),
  ("Include .git: {0}" -f ([bool]$IncludeGit)),
  ("Include .tmp*: {0}" -f ([bool]$IncludeTmp))
)
$lines | Set-Content -LiteralPath $readmePath -Encoding utf8

Write-Output ("Safe workspace prepared: {0}" -f $targetRepoPath)
Write-Output ("Marker: {0}" -f $readmePath)
