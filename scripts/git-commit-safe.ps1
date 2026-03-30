param(
    [Parameter(Mandatory = $true)]
    [string]$Message,

    [string]$Body = "",

    [switch]$DryRun
)

$repoRoot = Split-Path -Parent $PSScriptRoot
$guardScript = Join-Path $repoRoot ".githooks\check_staged_artifacts.ps1"

if (-not (Test-Path $guardScript)) {
    throw "Missing guard script: $guardScript"
}

Push-Location $repoRoot
try {
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $guardScript
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $stagedPaths = @(& git diff --cached --name-only --diff-filter=ACMR)
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    if ($stagedPaths.Count -eq 0) {
        Write-Error "No staged changes to commit."
        exit 1
    }

    $gitArgs = @("commit")
    if ($DryRun) {
        $gitArgs += "--dry-run"
    } else {
        # The PowerShell guard above already enforced the same staged-artifact checks.
        # This avoids flaky sh.exe hook startup failures on Windows.
        $gitArgs += "--no-verify"
    }

    $gitArgs += @("-m", $Message)
    if (-not [string]::IsNullOrWhiteSpace($Body)) {
        $gitArgs += @("-m", $Body)
    }

    & git @gitArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
