param()

$repoRoot = Split-Path -Parent $PSScriptRoot
$guardScript = Join-Path $repoRoot ".githooks\check_staged_artifacts.ps1"

if (-not (Test-Path $guardScript)) {
    throw "Missing guard script: $guardScript"
}

& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $guardScript -AutoFix
exit $LASTEXITCODE
