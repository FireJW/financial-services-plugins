param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Paths
)

if ($Paths.Count -eq 0) {
    Write-Error "Specify explicit paths. Do not use this wrapper as a broad 'git add .' replacement."
    exit 1
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$scrubScript = Join-Path $PSScriptRoot "git-scrub-staged-runtime-artifacts.ps1"

Push-Location $repoRoot
try {
    & git add -- @Paths
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $scrubScript
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    & git diff --cached --stat
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
