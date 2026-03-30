param(
    [switch]$AutoFix,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Paths
)

function Get-EnvInt {
    param(
        [string]$Name,
        [int]$DefaultValue
    )

    $rawValue = [System.Environment]::GetEnvironmentVariable($Name)
    if ([string]::IsNullOrWhiteSpace($rawValue)) {
        return $DefaultValue
    }
    return [int]$rawValue
}

$MaxStagedFiles = Get-EnvInt -Name "CODEX_MAX_STAGED_FILES" -DefaultValue 250
$MaxStagedChurn = Get-EnvInt -Name "CODEX_MAX_STAGED_CHURN" -DefaultValue 100000
$MaxBinaryFiles = Get-EnvInt -Name "CODEX_MAX_STAGED_BINARIES" -DefaultValue 25
$MaxStagedFileBytes = [int64](Get-EnvInt -Name "CODEX_MAX_STAGED_FILE_BYTES" -DefaultValue 50000000)

$BlockedPrefixes = @(
    ".tmp/",
    ".tmp-",
    "tmp-"
)

$BlockedDirNames = @(
    "blob_storage",
    "cache",
    "cache_data",
    "code cache",
    "gpucache",
    "graphitedawncache",
    "grshadercache",
    "indexeddb",
    "local storage",
    "service worker",
    "session storage",
    "shadercache"
)

$BlockedFileNames = @(
    "cookies",
    "cookies-journal",
    "favicons",
    "history",
    "history-journal",
    "login data",
    "network action predictor",
    "shortcuts",
    "top sites",
    "transportsecurity",
    "visited links",
    "web data"
)

$BrowserSessionHints = @(
    "browser-session",
    "cdp",
    "chrome-profile",
    "chrome-session",
    "edge-profile",
    "edge-session",
    "headless",
    "playwright"
)

$TempImageSuffixes = @(".gif", ".jpg", ".jpeg", ".png", ".webp")
$DbSuffixes = @(".db", ".ldb", ".sqlite", ".sqlite3")

function Normalize-RepoPath {
    param([string]$Path)
    if ($null -eq $Path) {
        return ""
    }
    return $Path.Replace("\", "/").Trim()
}

function Get-GitOutput {
    param([string[]]$GitArgs)
    $output = & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed"
    }
    return $output
}

function Invoke-Git {
    param([string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed"
    }
}

function Test-BlockedPath {
    param([string]$Path)

    $normalized = Normalize-RepoPath $Path
    $lowered = $normalized.ToLowerInvariant()

    foreach ($prefix in $BlockedPrefixes) {
        if ($lowered.StartsWith($prefix)) {
            return $true
        }
    }

    $parts = $lowered.Split("/", [System.StringSplitOptions]::RemoveEmptyEntries)
    foreach ($part in $parts) {
        if ($part -eq ".tmp" -or $part.StartsWith(".tmp-") -or $part.StartsWith("tmp-")) {
            return $true
        }
        if ($BlockedDirNames -contains $part) {
            return $true
        }
    }

    $name = [System.IO.Path]::GetFileName($lowered)
    if ($BlockedFileNames -contains $name) {
        return $true
    }

    $isBrowserLike = $false
    foreach ($hint in $BrowserSessionHints) {
        if ($lowered.Contains($hint)) {
            $isBrowserLike = $true
            break
        }
    }

    $suffix = [System.IO.Path]::GetExtension($lowered)
    if ($isBrowserLike -and (($TempImageSuffixes -contains $suffix) -or ($DbSuffixes -contains $suffix))) {
        return $true
    }

    return $false
}

function Get-StagedPaths {
    if ($Paths.Count -gt 0) {
        return @($Paths | ForEach-Object { Normalize-RepoPath $_ } | Where-Object { $_ })
    }

    $output = Get-GitOutput @("diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return @($output | ForEach-Object { Normalize-RepoPath $_ } | Where-Object { $_ })
}

function Get-StagedStats {
    $output = Get-GitOutput @("diff", "--cached", "--numstat", "--diff-filter=ACMR", "--no-renames")
    $churn = 0
    $binaryFiles = 0

    foreach ($line in $output) {
        if (-not $line) {
            continue
        }
        $parts = $line -split "`t", 3
        if ($parts.Count -lt 2) {
            continue
        }
        if ($parts[0] -eq "-" -or $parts[1] -eq "-") {
            $binaryFiles += 1
            continue
        }
        $churn += [int]$parts[0] + [int]$parts[1]
    }

    return @{
        Churn = $churn
        BinaryFiles = $binaryFiles
    }
}

function Get-OversizedStagedFiles {
    param(
        [string[]]$RepoPaths,
        [int64]$MaxBytes
    )

    $oversized = @()
    foreach ($repoPath in $RepoPaths) {
        $sizeOutput = & git cat-file -s (":{0}" -f $repoPath) 2>$null
        if ($LASTEXITCODE -ne 0) {
            continue
        }

        $rawSize = @($sizeOutput)[0]
        if ($rawSize -notmatch '^\d+$') {
            continue
        }

        $sizeBytes = [int64]$rawSize
        if ($sizeBytes -gt $MaxBytes) {
            $oversized += [pscustomobject]@{
                Path = $repoPath
                SizeBytes = $sizeBytes
            }
        }
    }

    return $oversized
}

function Unstage-Paths {
    param([string[]]$RepoPaths)

    $normalizedPaths = @($RepoPaths | ForEach-Object { Normalize-RepoPath $_ } | Where-Object { $_ } | Select-Object -Unique)
    if ($normalizedPaths.Count -eq 0) {
        return
    }

    $chunkSize = 50
    for ($i = 0; $i -lt $normalizedPaths.Count; $i += $chunkSize) {
        $chunk = $normalizedPaths[$i..([Math]::Min($i + $chunkSize - 1, $normalizedPaths.Count - 1))]
        Invoke-Git @("reset", "-q", "HEAD", "--") + $chunk
    }
}

try {
    $stagedPaths = Get-StagedPaths
    if ($stagedPaths.Count -eq 0) {
        exit 0
    }

    $blocked = @($stagedPaths | Where-Object { Test-BlockedPath $_ })
    if ($blocked.Count -gt 0) {
        if ($AutoFix) {
            Unstage-Paths -RepoPaths $blocked
            [Console]::Error.WriteLine("pre-commit guard: auto-unstaged blocked runtime artifacts from the index.")
            foreach ($path in $blocked | Select-Object -First 20) {
                [Console]::Error.WriteLine("  - $path")
            }
            if ($blocked.Count -gt 20) {
                [Console]::Error.WriteLine("  - ... and $($blocked.Count - 20) more")
            }
            [Console]::Error.WriteLine("")
            [Console]::Error.WriteLine("Working tree files were kept. Review the remaining staged diff with:")
            [Console]::Error.WriteLine("  git status --short")
            [Console]::Error.WriteLine("  git diff --cached --stat")
            exit 0
        }

        [Console]::Error.WriteLine("pre-commit guard: blocked staged runtime artifacts:")
        foreach ($path in $blocked | Select-Object -First 20) {
            [Console]::Error.WriteLine("  - $path")
        }
        if ($blocked.Count -gt 20) {
            [Console]::Error.WriteLine("  - ... and $($blocked.Count - 20) more")
        }
        [Console]::Error.WriteLine("")
        [Console]::Error.WriteLine("Unstage them before committing. Suggested commands:")
        [Console]::Error.WriteLine("  git restore --staged <path>")
        [Console]::Error.WriteLine("  git restore --staged -- .tmp")
        [Console]::Error.WriteLine("  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/git-scrub-staged-runtime-artifacts.ps1")
        [Console]::Error.WriteLine("Use --no-verify only if you intentionally want these artifacts in git history.")
        exit 1
    }

    $oversizedFiles = @(Get-OversizedStagedFiles -RepoPaths $stagedPaths -MaxBytes $MaxStagedFileBytes)
    if ($oversizedFiles.Count -gt 0) {
        $oversizedPaths = @($oversizedFiles | ForEach-Object { $_.Path })
        if ($AutoFix) {
            Unstage-Paths -RepoPaths $oversizedPaths
            [Console]::Error.WriteLine("pre-commit guard: auto-unstaged oversized staged files from the index.")
            foreach ($entry in $oversizedFiles | Select-Object -First 20) {
                $sizeMb = [math]::Round($entry.SizeBytes / 1MB, 2)
                [Console]::Error.WriteLine("  - $($entry.Path) (${sizeMb} MB)")
            }
            if ($oversizedFiles.Count -gt 20) {
                [Console]::Error.WriteLine("  - ... and $($oversizedFiles.Count - 20) more")
            }
            [Console]::Error.WriteLine("")
            [Console]::Error.WriteLine("Working tree files were kept. Review the remaining staged diff with:")
            [Console]::Error.WriteLine("  git status --short")
            [Console]::Error.WriteLine("  git diff --cached --stat")
            exit 0
        }

        [Console]::Error.WriteLine("pre-commit guard: oversized staged files exceed the safety limit.")
        foreach ($entry in $oversizedFiles | Select-Object -First 20) {
            $sizeMb = [math]::Round($entry.SizeBytes / 1MB, 2)
            $limitMb = [math]::Round($MaxStagedFileBytes / 1MB, 2)
            [Console]::Error.WriteLine("  - $($entry.Path) (${sizeMb} MB > ${limitMb} MB)")
        }
        if ($oversizedFiles.Count -gt 20) {
            [Console]::Error.WriteLine("  - ... and $($oversizedFiles.Count - 20) more")
        }
        [Console]::Error.WriteLine("")
        [Console]::Error.WriteLine("Suggested commands:")
        [Console]::Error.WriteLine("  git restore --staged <path>")
        [Console]::Error.WriteLine("  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/git-scrub-staged-runtime-artifacts.ps1")
        [Console]::Error.WriteLine("Set CODEX_MAX_STAGED_FILE_BYTES to raise or lower the safety threshold if needed.")
        exit 1
    }

    if ($Paths.Count -gt 0) {
        exit 0
    }

    $stats = Get-StagedStats
    if ($stagedPaths.Count -gt $MaxStagedFiles -or $stats.Churn -gt $MaxStagedChurn -or $stats.BinaryFiles -gt $MaxBinaryFiles) {
        [Console]::Error.WriteLine("pre-commit guard: staged diff is unexpectedly large.")
        [Console]::Error.WriteLine(
            "  files=$($stagedPaths.Count) limit=$MaxStagedFiles churn=$($stats.Churn) " +
            "limit=$MaxStagedChurn binary_files=$($stats.BinaryFiles) limit=$MaxBinaryFiles"
        )
        [Console]::Error.WriteLine("")
        [Console]::Error.WriteLine("Review the staged scope before committing:")
        [Console]::Error.WriteLine("  git diff --cached --stat")
        [Console]::Error.WriteLine("  git status --short")
        [Console]::Error.WriteLine("Use --no-verify only if the large commit is intentional.")
        exit 1
    }

    exit 0
}
catch {
    [Console]::Error.WriteLine("pre-commit guard failed: $($_.Exception.Message)")
    exit 1
}
