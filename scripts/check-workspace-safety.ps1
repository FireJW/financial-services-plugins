param(
  [string]$Path = ".",
  [switch]$Json
)

$ErrorActionPreference = "Stop"

function Get-RepoRoot {
  param([string]$ResolvedPath)

  try {
    $gitRoot = (& git -C $ResolvedPath rev-parse --show-toplevel 2>$null)
    if ($gitRoot) {
      return (Resolve-Path -LiteralPath $gitRoot).Path
    }
  } catch {
  }

  return $ResolvedPath
}

function Get-WslProbe {
  $result = [ordered]@{
    available = $false
    detail = ""
  }

  try {
    $command = Get-Command wsl.exe -ErrorAction Stop
    $result.available = $true
    try {
      $output = & $command.Source -l -q 2>&1
      if ($LASTEXITCODE -eq 0 -and $output) {
        $result.detail = (($output | ForEach-Object { $_.ToString().Trim() }) -join ", ")
      } elseif ($LASTEXITCODE -ne 0) {
        $result.detail = "wsl.exe is present but distro enumeration is denied from the current shell."
      } elseif ($output) {
        $result.detail = ($output | Out-String).Trim()
      }
    } catch {
      $result.detail = $_.Exception.Message
    }
  } catch {
  }

  return [pscustomobject]$result
}

$resolvedPath = (Resolve-Path -LiteralPath $Path).Path
$repoRoot = Get-RepoRoot -ResolvedPath $resolvedPath
$repoName = Split-Path -Leaf $repoRoot
$userProfile = if ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath("UserProfile") }

$riskReasons = New-Object System.Collections.Generic.List[string]
$riskLevel = "low"

if ($repoRoot -match "\\\.gemini\\antigravity\\scratch(\\|$)") {
  $riskReasons.Add("Repository is inside .gemini scratch, which behaves like a disposable agent workspace.")
  $riskLevel = "critical"
}

if ($repoRoot -match "\\\.codex\\worktrees(\\|$)") {
  $riskReasons.Add("Repository is inside a Codex worktree, which is safer than scratch but still not ideal as the canonical home.")
  if ($riskLevel -eq "low") {
    $riskLevel = "high"
  }
}

if ($repoRoot -match "\\AppData\\Local\\Temp(\\|$)") {
  $riskReasons.Add("Repository is inside a temp directory.")
  $riskLevel = "critical"
}

if ($repoRoot -match "\\\.tmp($|\\)") {
  $riskReasons.Add("Repository path itself includes a temp-style folder.")
  if ($riskLevel -eq "low") {
    $riskLevel = "high"
  }
}

$recommendedWindowsRoot = Join-Path $userProfile "dev"
$recommendedWindowsPath = Join-Path $recommendedWindowsRoot $repoName
$recommendedBackupRoot = Join-Path $userProfile ("repo-safety-backups\{0}" -f $repoName)
$recommendedDDriveRoot = "D:\Users\rickylu\dev"
$recommendedDDrivePath = Join-Path $recommendedDDriveRoot $repoName
$recommendedDBackupRoot = "D:\Users\rickylu\repo-safety-backups\financial-services-plugins"
$wslProbe = Get-WslProbe

$payload = [pscustomobject]@{
  repository = $repoRoot
  repository_name = $repoName
  risk_level = $riskLevel
  reasons = @($riskReasons)
  recommended_windows_path = $recommendedWindowsPath
  recommended_backup_root = $recommendedBackupRoot
  recommended_d_backup_root = $recommendedDBackupRoot
  recommended_d_drive_path = $recommendedDDrivePath
  wsl_available = $wslProbe.available
  wsl_detail = $wslProbe.detail
  recommended_wsl_path = "/home/<linux-user>/dev/$repoName"
}

if ($Json) {
  $payload | ConvertTo-Json -Depth 5
  exit 0
}

Write-Output ("Repository: {0}" -f $payload.repository)
Write-Output ("Risk level: {0}" -f $payload.risk_level)
if ($payload.reasons.Count -gt 0) {
  Write-Output ""
  Write-Output "Why this path is risky:"
  foreach ($reason in $payload.reasons) {
    Write-Output ("- {0}" -f $reason)
  }
}

Write-Output ""
Write-Output "Recommended canonical paths:"
Write-Output ("- Windows: {0}" -f $payload.recommended_windows_path)
Write-Output ("- D drive: {0}" -f $payload.recommended_d_drive_path)
Write-Output ("- WSL: {0}" -f $payload.recommended_wsl_path)
Write-Output ("- Backup root: {0}" -f $payload.recommended_backup_root)
Write-Output ("- D backup root: {0}" -f $payload.recommended_d_backup_root)

if ($payload.wsl_available) {
  Write-Output ""
  if ($payload.wsl_detail) {
    Write-Output ("WSL probe: {0}" -f $payload.wsl_detail)
  } else {
    Write-Output "WSL probe: wsl.exe is available."
  }
}

Write-Output ""
Write-Output "Suggested next commands:"
Write-Output (".\scripts\repo-snapshot.ps1 -BackupRoot `"{0}`" -MirrorLatest -IncludeGit" -f $recommendedDBackupRoot)
Write-Output (".\scripts\prepare-safe-workspace.ps1 -TargetRoot `"{0}`" -IncludeGit -IncludeTmp" -f $recommendedDDriveRoot)
