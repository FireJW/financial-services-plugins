param(
  [string]$SourceRoot = ".",
  [string]$BackupRoot,
  [switch]$IncludeGit,
  [switch]$ExcludeTmp,
  [switch]$MirrorLatest,
  [switch]$ZipSnapshot
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

if (-not $BackupRoot) {
  $homeRoot = if ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath("UserProfile") }
  $BackupRoot = Join-Path $homeRoot ("repo-safety-backups\{0}" -f $repoName)
}

$BackupRoot = Resolve-TargetPath -PathValue $BackupRoot

if ($BackupRoot.StartsWith($repoRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
  throw "BackupRoot must be outside the repository root. Nested snapshots are not allowed."
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$snapshotRoot = Join-Path $BackupRoot "snapshots"
$snapshotPath = Join-Path $snapshotRoot $timestamp
$latestPath = Join-Path $BackupRoot "latest"

New-Item -ItemType Directory -Force -Path $snapshotPath | Out-Null
$snapshotPath = (Resolve-Path -LiteralPath $snapshotPath).Path

if ($MirrorLatest) {
  New-Item -ItemType Directory -Force -Path $latestPath | Out-Null
  $latestPath = (Resolve-Path -LiteralPath $latestPath).Path
}

$excludeDirs = New-Object System.Collections.Generic.List[string]
if (-not $IncludeGit) {
  $excludeDirs.Add((Join-Path $repoRoot ".git"))
}
if ($ExcludeTmp) {
  Get-ChildItem -LiteralPath $repoRoot -Directory -Force -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -eq ".tmp" -or $_.Name -like ".tmp-*" -or $_.Name -like "tmp-*" } |
    ForEach-Object { [void]$excludeDirs.Add($_.FullName) }
}

foreach ($badDir in (Get-UnreadableDirectories -Root $repoRoot)) {
  [void]$excludeDirs.Add($badDir)
}

Invoke-RobocopySafe -From $repoRoot -To $snapshotPath -ExcludeDirs @($excludeDirs)

if ($MirrorLatest) {
  Invoke-RobocopySafe -From $repoRoot -To $latestPath -ExcludeDirs @($excludeDirs)
}

$gitHead = $null
try {
  $gitHead = (& git -C $repoRoot rev-parse HEAD 2>$null)
  if (-not $gitHead) {
    $gitHead = $null
  }
} catch {
  $gitHead = $null
}

$manifest = [pscustomobject]@{
  created_at = (Get-Date).ToString("o")
  source_root = $repoRoot
  snapshot_path = $snapshotPath
  latest_path = $(if ($MirrorLatest) { $latestPath } else { $null })
  include_git = [bool]$IncludeGit
  exclude_tmp = [bool]$ExcludeTmp
  git_head = $gitHead
}

$manifestPath = Join-Path $snapshotPath "snapshot-manifest.json"
$manifest | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8

$zipPath = $null
if ($ZipSnapshot) {
  $zipPath = Join-Path $BackupRoot ("{0}-{1}.zip" -f $repoName, $timestamp)
  if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
  }
  Compress-Archive -LiteralPath $snapshotPath -DestinationPath $zipPath -CompressionLevel Optimal
}

Write-Output ("Snapshot created: {0}" -f $snapshotPath)
Write-Output ("Manifest: {0}" -f $manifestPath)
if ($MirrorLatest) {
  Write-Output ("Latest mirror: {0}" -f $latestPath)
}
if ($zipPath) {
  Write-Output ("Zip archive: {0}" -f $zipPath)
}
