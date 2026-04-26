<#
.SYNOPSIS
    Clean workflow artifacts from .tmp/ directories older than N days.

.DESCRIPTION
    Removes only known workflow output patterns (article drafts, topic discovery,
    test runs, diagnostics, etc.) that are older than the specified age.
    Does NOT touch environment dirs (venvs, backups, cookie caches, codex state).

.PARAMETER DaysOld
    Minimum age in days. Directories modified more recently are kept. Default: 3.

.PARAMETER DryRun
    Show what would be deleted without actually deleting.

.PARAMETER RepoRoot
    Repository root. Default: script's grandparent directory.

.EXAMPLE
    .\clean-tmp-artifacts.ps1 -DryRun
    .\clean-tmp-artifacts.ps1 -DaysOld 7
    .\clean-tmp-artifacts.ps1
#>
param(
    [int]$DaysOld = 3,
    [switch]$DryRun,
    [string]$RepoRoot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
}

# --- Known workflow artifact patterns (prefix match on directory name) ---
$workflowPrefixes = @(
    "article-"
    "topic-"
    "hot-topic"
    "cn-macro-"
    "live-"
    "wechat-"
    "toutiao-"
    "xiaohongshu-"
    "xhs-"
    "test-stock-watch-"
    "test-review-gate"
    "agent-reach"
    "google-news-"
    "benchmark-"
    "reddit-"
    "social-"
    "style-corpus-"
    "canonical-snapshot-"
    "macro-note-"
    "market-intelligence-"
    "month-end-shortlist-"
    "scan-cn-"
    "skill-creator-"
    "iran-"
    "trump-"
    "us-iran-"
    "career-ops-"
    "pb-flow-"
    "platform-index-"
    "debug-publish-"
    "claude-code-article-"
    "last30days-"
    "x-index"
    "x-query-"
    "x-market-"
    "ai-frontier-"
    "geopolitics-"
    "openclaw-"
    "wf-debug-"
    "gs-quant-"
    "tradingagents-user-"
    "tradingagents-pilot-"
    "opencli-"
)

# --- Directories to NEVER touch ---
$protectedPatterns = @(
    "*-venv"
    "*-backup*"
    "edge-cookie-*"
    "remote-*"
    "gstack-*"
    "codex-*"
    "tradingagents-operator-*"
    "reports"
    "local-tail-*"
)

function Test-IsWorkflowArtifact {
    param([string]$Name)
    foreach ($prefix in $workflowPrefixes) {
        if ($Name.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Test-IsProtected {
    param([string]$Name)
    foreach ($pattern in $protectedPatterns) {
        if ($Name -like $pattern) {
            return $true
        }
    }
    return $false
}

$cutoff = (Get-Date).AddDays(-$DaysOld)
$tmpDirs = @(
    Join-Path $RepoRoot ".tmp"
    Join-Path $RepoRoot "financial-analysis\.tmp"
)

$totalFreed = 0
$totalRemoved = 0
$totalSkipped = 0

foreach ($tmpDir in $tmpDirs) {
    if (-not (Test-Path $tmpDir)) { continue }

    $label = $tmpDir.Replace($RepoRoot, "").TrimStart("\", "/")
    Write-Host "`n=== $label ===" -ForegroundColor Cyan

    # Process subdirectories
    Get-ChildItem -Path $tmpDir -Directory | ForEach-Object {
        $dir = $_
        $name = $dir.Name
        $lastWrite = $dir.LastWriteTime

        if (Test-IsProtected $name) {
            Write-Host "  SKIP (protected): $name" -ForegroundColor DarkGray
            $totalSkipped++
            return
        }

        if (-not (Test-IsWorkflowArtifact $name)) {
            Write-Host "  SKIP (unknown):   $name" -ForegroundColor DarkGray
            $totalSkipped++
            return
        }

        if ($lastWrite -gt $cutoff) {
            Write-Host "  SKIP (recent):    $name  [$($lastWrite.ToString('yyyy-MM-dd'))]" -ForegroundColor Yellow
            $totalSkipped++
            return
        }

        $size = (Get-ChildItem -Recurse -File $dir.FullName -ErrorAction SilentlyContinue |
                 Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round(($size / 1MB), 1)

        if ($DryRun) {
            Write-Host "  WOULD DELETE:     $name  [$($lastWrite.ToString('yyyy-MM-dd')), ${sizeMB}MB]" -ForegroundColor Magenta
        } else {
            Remove-Item -Recurse -Force $dir.FullName
            Write-Host "  DELETED:          $name  [$($lastWrite.ToString('yyyy-MM-dd')), ${sizeMB}MB]" -ForegroundColor Green
        }
        $totalFreed += $size
        $totalRemoved++
    }

    # Process loose files (not in subdirectories)
    Get-ChildItem -Path $tmpDir -File | ForEach-Object {
        $file = $_
        if ($file.LastWriteTime -gt $cutoff) {
            $totalSkipped++
            return
        }
        $sizeMB = [math]::Round(($file.Length / 1MB), 1)
        if ($DryRun) {
            Write-Host "  WOULD DELETE:     $($file.Name)  [$($file.LastWriteTime.ToString('yyyy-MM-dd')), ${sizeMB}MB]" -ForegroundColor Magenta
        } else {
            Remove-Item -Force $file.FullName
            Write-Host "  DELETED:          $($file.Name)  [$($file.LastWriteTime.ToString('yyyy-MM-dd')), ${sizeMB}MB]" -ForegroundColor Green
        }
        $totalFreed += $file.Length
        $totalRemoved++
    }
}

$freedMB = [math]::Round(($totalFreed / 1MB), 1)
Write-Host "`n--- Summary ---" -ForegroundColor Cyan
Write-Host "  Removed: $totalRemoved items ($freedMB MB)"
Write-Host "  Skipped: $totalSkipped items (protected / unknown / recent)"
if ($DryRun) {
    Write-Host "  (DRY RUN - nothing was actually deleted)" -ForegroundColor Yellow
}
