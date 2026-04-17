param(
    [string]$InstallRoot,
    [string]$PseudoHome,
    [string]$PythonBinary,
    [string]$RepoUrl = "https://github.com/Panniantong/agent-reach.git",
    [switch]$RefreshRepo
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-DefaultVendorRoot {
    $userRoot = Join-Path "D:\Users" $env:USERNAME
    return Join-Path $userRoot ".codex\vendor"
}

function Find-PythonBinary {
    param([string]$ExplicitPath)

    $candidates = @()
    if ($ExplicitPath) {
        $candidates += $ExplicitPath
    }
    foreach ($envName in @("AGENT_REACH_PYTHON_BINARY", "AGENT_REACH_FULL_PYTHON", "CODEX_LOCAL_PYTHON")) {
        $envItem = Get-Item "Env:$envName" -ErrorAction SilentlyContinue
        if ($envItem -and $envItem.Value) {
            $candidates += $envItem.Value
        }
    }
    $candidates += "D:\Users\rickylu\.codex\vendor\python312-full\python.exe"

    $accioRoot = Join-Path $env:USERPROFILE "AppData\Roaming\Accio\pre-install"
    if (Test-Path -LiteralPath $accioRoot) {
        $accioCandidates = Get-ChildItem -LiteralPath $accioRoot -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -like "*\python\python.exe" } |
            Sort-Object LastWriteTime -Descending
        foreach ($candidate in $accioCandidates) {
            $candidates += $candidate.FullName
        }
    }

    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $ExplicitPath
}

function Invoke-AgentReachCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Executable,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [Parameter(Mandatory = $true)][hashtable]$Environment,
        [string]$CapturePath
    )

    $previousHome = $env:HOME
    $previousUserProfile = $env:USERPROFILE
    $previousPath = $env:PATH
    try {
        $env:HOME = $Environment.HOME
        $env:USERPROFILE = $Environment.USERPROFILE
        $env:PATH = $Environment.PATH
        if ($CapturePath) {
            & $Executable @Arguments 2>&1 | Set-Content -LiteralPath $CapturePath -Encoding UTF8
        } else {
            & $Executable @Arguments | Out-Host
        }
    } finally {
        $env:HOME = $previousHome
        $env:USERPROFILE = $previousUserProfile
        $env:PATH = $previousPath
    }
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
$PythonBinary = Find-PythonBinary -ExplicitPath $PythonBinary
$toolPathEntries = @(
    (Join-Path $vendorRoot "gh\bin"),
    (Join-Path $vendorRoot "yt-dlp"),
    (Join-Path $vendorRoot "mcporter"),
    (Join-Path $vendorRoot "bird"),
    (Join-Path $vendorRoot "xreach")
) | Where-Object { Test-Path -LiteralPath $_ }
$env:PATH = (($toolPathEntries + @($env:PATH)) -join ';')
Assert-WithinVendor -Path $InstallRoot -VendorRoot $vendorRoot
Assert-WithinVendor -Path $PseudoHome -VendorRoot $vendorRoot
New-Item -ItemType Directory -Force -Path $InstallRoot, $PseudoHome | Out-Null

if (-not (Test-Path -LiteralPath $PythonBinary)) {
    throw "Full Python runtime missing: $PythonBinary"
}

$venvRoot = Join-Path $InstallRoot ".venv"
$repoRoot = Join-Path $InstallRoot "repo"
$stateRoot = Join-Path $InstallRoot ".agent-reach"
$doctorReport = Join-Path $stateRoot "doctor-report.json"
$versionLock = Join-Path $stateRoot "version.lock"
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null

$npmCommand = (Get-Command "npm.cmd" -ErrorAction SilentlyContinue)
if (-not $npmCommand) {
    throw "npm.cmd is required but was not found"
}

if (-not (Test-Path -LiteralPath $repoRoot)) {
    git clone $RepoUrl $repoRoot | Out-Host
} elseif ($RefreshRepo) {
    git -C $repoRoot fetch --all --prune | Out-Host
    git -C $repoRoot pull --ff-only | Out-Host
}

if (-not (Test-Path -LiteralPath $venvRoot)) {
    & $PythonBinary -m venv $venvRoot | Out-Host
}

$venvPython = Join-Path $venvRoot "Scripts\python.exe"
$agentReachExe = Join-Path $venvRoot "Scripts\agent-reach.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    throw "Virtualenv python missing after venv creation: $venvPython"
}

& $venvPython -m pip install --upgrade pip setuptools wheel | Out-Host
& $venvPython -m pip install --upgrade $repoRoot | Out-Host
& $venvPython -m pip install --upgrade "browser-cookie3>=0.19" | Out-Host

if (-not (Test-Path -LiteralPath $agentReachExe)) {
    throw "agent-reach executable missing after install: $agentReachExe"
}

@'
import browser_cookie3
print("browser_cookie3 ok")
'@ | & $venvPython - | Out-Host

$runEnv = @{
    HOME = $PseudoHome
    USERPROFILE = $PseudoHome
    PATH = "$(Join-Path $venvRoot 'Scripts');$env:PATH"
}

Invoke-AgentReachCommand -Executable $agentReachExe -Arguments @("install", "--dry-run") -Environment $runEnv
Invoke-AgentReachCommand -Executable $agentReachExe -Arguments @("install", "--safe") -Environment $runEnv

$requiredBinaries = @("gh", "yt-dlp", "node", "npm.cmd")
foreach ($binary in $requiredBinaries) {
    if (-not (Get-Command $binary -ErrorAction SilentlyContinue)) {
        Write-Host "MISSING: $binary"
        exit 1
    }
}

Invoke-AgentReachCommand -Executable $agentReachExe -Arguments @("doctor") -Environment $runEnv -CapturePath $doctorReport

$commitSha = (git -C $repoRoot rev-parse HEAD).Trim()
$doctorText = Get-Content -LiteralPath $doctorReport -Raw
$xBackend = if ($doctorText -match "xreach") { "xreach" } elseif ($doctorText -match "\bbird\b") { "bird" } else { "" }

@{
    repo = $RepoUrl
    pinned_commit = $commitSha
    pinned_date = (Get-Date).ToUniversalTime().ToString("o")
    x_backend = $xBackend
} | ConvertTo-Json | Set-Content -LiteralPath $versionLock -Encoding UTF8

Write-Host "Agent Reach install wrapper completed."
