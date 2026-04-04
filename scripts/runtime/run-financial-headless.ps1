[CmdletBinding()]
param(
  [string]$Config = "",
  [string]$Profile = "",
  [switch]$AllPlugins,
  [switch]$IncludePartnerBuilt,
  [string[]]$PluginDir = @(),
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CliArgs = @()
)

$ErrorActionPreference = "Stop"

function Resolve-RepoPath {
  param([string]$RepoRoot, [string]$MaybeRelativePath)

  if ([string]::IsNullOrWhiteSpace($MaybeRelativePath)) {
    return $null
  }

  if ([System.IO.Path]::IsPathRooted($MaybeRelativePath)) {
    return [System.IO.Path]::GetFullPath($MaybeRelativePath)
  }

  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $MaybeRelativePath))
}

function Get-TaskProfilesConfig {
  param([string]$RepoRoot)

  $profilesPath = Join-Path $RepoRoot "scripts\runtime\task-profiles.json"
  if (-not (Test-Path -LiteralPath $profilesPath)) {
    return $null
  }

  return Get-Content -Raw -LiteralPath $profilesPath | ConvertFrom-Json
}

$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$runtimeRoot = Join-Path $repoRoot "vendor\claude-code-recovered"
$cliPath = Join-Path $runtimeRoot "dist\cli.js"

if (-not (Test-Path -LiteralPath $cliPath)) {
  Write-Error @"
Recovered runtime is not built yet.

Expected:
  $cliPath

Next steps:
  1. cd $runtimeRoot
  2. npm install
  3. npm run build
"@
  exit 1
}

$pluginDirs = New-Object System.Collections.Generic.List[string]

foreach ($defaultDir in @("financial-analysis", "equity-research")) {
  $pluginDirs.Add((Join-Path $repoRoot $defaultDir))
}

if ($AllPlugins) {
  foreach ($extraDir in @("investment-banking", "private-equity", "wealth-management")) {
    $pluginDirs.Add((Join-Path $repoRoot $extraDir))
  }
}

if ($IncludePartnerBuilt) {
  foreach ($partnerDir in @("partner-built\lseg", "partner-built\spglobal", "partner-built\goldmansachs")) {
    $pluginDirs.Add((Join-Path $repoRoot $partnerDir))
  }
}

if ($Config) {
  $configPath = Resolve-RepoPath -RepoRoot $repoRoot -MaybeRelativePath $Config
  if (-not (Test-Path -LiteralPath $configPath)) {
    Write-Error "Config file not found: $configPath"
    exit 1
  }

  $configJson = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json

  if ($configJson.pluginDirs) {
    foreach ($configDir in $configJson.pluginDirs) {
      $resolved = Resolve-RepoPath -RepoRoot $repoRoot -MaybeRelativePath ([string]$configDir)
      if ($resolved) {
        $pluginDirs.Add($resolved)
      }
    }
  }

  if ($configJson.cliArgs) {
    $CliArgs = @($configJson.cliArgs) + $CliArgs
  }
}

foreach ($customDir in $PluginDir) {
  $resolved = Resolve-RepoPath -RepoRoot $repoRoot -MaybeRelativePath $customDir
  if ($resolved) {
    $pluginDirs.Add($resolved)
  }
}

$taskProfilesConfig = Get-TaskProfilesConfig -RepoRoot $repoRoot
$profileConfig = $null
if ($Profile) {
  if (-not $taskProfilesConfig) {
    Write-Error "Task profiles file not found under scripts/runtime/task-profiles.json"
    exit 1
  }

  $profileProperty = $taskProfilesConfig.profiles.PSObject.Properties | Where-Object { $_.Name -eq $Profile } | Select-Object -First 1
  if (-not $profileProperty) {
    $availableProfiles = $taskProfilesConfig.profiles.PSObject.Properties.Name -join ", "
    Write-Error "Unknown profile '$Profile'. Available profiles: $availableProfiles"
    exit 1
  }

  $profileConfig = $profileProperty.Value
}

$resolvedPluginDirs = @()
foreach ($dir in $pluginDirs) {
  if (Test-Path -LiteralPath $dir) {
    if ($resolvedPluginDirs -notcontains $dir) {
      $resolvedPluginDirs += $dir
    }
  } else {
    Write-Warning "Skipping missing plugin directory: $dir"
  }
}

$defaultCliArgs = if ($taskProfilesConfig -and $taskProfilesConfig.baseCliArgs) {
  @($taskProfilesConfig.baseCliArgs)
} else {
  @("--bare", "--strict-mcp-config")
}

$profileCliArgs = @()
if ($profileConfig) {
  $appendSystemPromptFile = Resolve-RepoPath -RepoRoot $repoRoot -MaybeRelativePath ([string]$profileConfig.appendSystemPromptFile)
  if ($appendSystemPromptFile) {
    $profileCliArgs += "--append-system-prompt-file"
    $profileCliArgs += $appendSystemPromptFile
  }

  if ($profileConfig.defaultCliArgs) {
    $profileCliArgs += @($profileConfig.defaultCliArgs)
  }
}

$forwardArgs = @($cliPath)
$forwardArgs += $defaultCliArgs
foreach ($dir in $resolvedPluginDirs) {
  $forwardArgs += "--plugin-dir"
  $forwardArgs += $dir
}
$forwardArgs += $profileCliArgs
$forwardArgs += $CliArgs

Push-Location $runtimeRoot
try {
  & node @forwardArgs
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
