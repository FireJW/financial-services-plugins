Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

param(
    [string]$InstallRoot,
    [string]$PseudoHome,
    [switch]$Clean
)

function Get-DefaultVendorRoot {
    $userRoot = Join-Path "D:\Users" $env:USERNAME
    return Join-Path $userRoot ".codex\vendor"
}

function Assert-WithinVendor {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$VendorRoot
    )
    $resolvedPath = [System.IO.Path]::GetFullPath($Path)
    $resolvedVendor = [System.IO.Path]::GetFullPath($VendorRoot)
    if (-not $resolvedPath.StartsWith($resolvedVendor, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to touch path outside vendor root: $resolvedPath"
    }
}

$vendorRoot = Get-DefaultVendorRoot
$InstallRoot = if ($InstallRoot) { $InstallRoot } else { Join-Path $vendorRoot "agent-reach" }
$PseudoHome = if ($PseudoHome) { $PseudoHome } else { Join-Path $vendorRoot "agent-reach-home" }
Assert-WithinVendor -Path $InstallRoot -VendorRoot $vendorRoot
Assert-WithinVendor -Path $PseudoHome -VendorRoot $vendorRoot

$signals = @()
$agentReachExe = Join-Path $InstallRoot ".venv\Scripts\agent-reach.exe"
$repoRoot = Join-Path $InstallRoot "repo"
$versionLock = Join-Path $InstallRoot ".agent-reach\version.lock"

if ((Test-Path -LiteralPath $PseudoHome) -and -not (Test-Path -LiteralPath $InstallRoot)) {
    $signals += "pseudo_home_without_install_root"
}
if ((Test-Path -LiteralPath $InstallRoot) -and -not (Test-Path -LiteralPath $agentReachExe)) {
    $signals += "install_root_without_agent_reach_binary"
}
if ((Test-Path -LiteralPath $repoRoot) -and -not (Test-Path -LiteralPath $versionLock)) {
    $signals += "repo_present_without_version_lock"
}

if ($Clean) {
    foreach ($target in @($InstallRoot, $PseudoHome)) {
        if (Test-Path -LiteralPath $target) {
            Remove-Item -LiteralPath $target -Recurse -Force
        }
    }
}

@{
    install_root = $InstallRoot
    pseudo_home = $PseudoHome
    clean = [bool]$Clean
    partial = [bool]($signals.Count -gt 0)
    signals = $signals
} | ConvertTo-Json
