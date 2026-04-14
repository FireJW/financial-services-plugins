param(
  [string]$CanonicalRepo = "D:\Users\rickylu\dev\financial-services-plugins",
  [string]$TargetRoot = "D:\Users\rickylu\dev",
  [switch]$Execute
)

$ErrorActionPreference = "Stop"

function Invoke-RobocopySafe {
  param(
    [string]$From,
    [string]$To
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

  $output = & robocopy @arguments 2>&1
  if ($LASTEXITCODE -gt 7) {
    $tail = ($output | Select-Object -Last 40 | Out-String).Trim()
    throw ("robocopy failed with exit code {0}`n{1}" -f $LASTEXITCODE, $tail)
  }
}

function Write-Marker {
  param(
    [string]$Destination,
    [string]$LineName,
    [string[]]$SourcePaths
  )

  $marker = Join-Path $Destination ".mainline-source.txt"
  $content = @(
    ("Created at: {0}" -f (Get-Date).ToString("o")),
    ("Canonical repo: {0}" -f $CanonicalRepo),
    ("Mainline: {0}" -f $LineName),
    "Source paths:"
  ) + ($SourcePaths | ForEach-Object { "- $_" })
  $content | Set-Content -LiteralPath $marker -Encoding utf8
}

if (-not (Test-Path -LiteralPath $CanonicalRepo)) {
  throw "Canonical repo does not exist: $CanonicalRepo"
}

$mainlines = @(
  @{
    Name = "financial-services-docs"
    Sources = @(
      "README.md",
      "CLAUDE.md",
      "AGENTS.md",
      "CODEX_DEVELOPMENT_FLOW.md",
      ".claude",
      ".context",
      "docs"
    )
  },
  @{
    Name = "financial-services-stock"
    Sources = @(
      "financial-analysis",
      "equity-research",
      "partner-built",
      "private-equity",
      "wealth-management",
      "china-portal-adapter",
      "apps",
      "build_comps_liquid_cooling.py",
      "build_comps_phosphate.py",
      "build_comps_power_grid.py",
      "build_comps_tungsten.py",
      "build_dcf_000969.py",
      "build_dcf_002379.py",
      "build_dcf_002837.py",
      "build_dcf_600078.py",
      "build_dcf_600089.py",
      "build_dcf_601600.py",
      "scripts",
      "tests",
      "examples"
    )
  },
  @{
    Name = "financial-services-obsidian"
    Sources = @(
      "obsidian-kb-local"
    )
  }
)

if (-not $Execute) {
  Write-Output ("Canonical repo: {0}" -f $CanonicalRepo)
  Write-Output ("Target root: {0}" -f $TargetRoot)
  Write-Output ""
  Write-Output "Planned mainline directories:"
  foreach ($line in $mainlines) {
    Write-Output ("- {0}" -f (Join-Path $TargetRoot $line.Name))
    foreach ($source in $line.Sources) {
      Write-Output ("  - from {0}" -f $source)
    }
  }
  Write-Output ""
  Write-Output "Dry run only. To execute, run:"
  Write-Output ".\scripts\promote-mainlines.ps1 -Execute"
  exit 0
}

foreach ($line in $mainlines) {
  $destination = Join-Path $TargetRoot $line.Name
  New-Item -ItemType Directory -Force -Path $destination | Out-Null

  foreach ($source in $line.Sources) {
    $sourcePath = Join-Path $CanonicalRepo $source
    if (-not (Test-Path -LiteralPath $sourcePath)) {
      continue
    }

    if ((Get-Item -LiteralPath $sourcePath).PSIsContainer) {
      $destPath = Join-Path $destination $source
      New-Item -ItemType Directory -Force -Path $destPath | Out-Null
      Invoke-RobocopySafe -From $sourcePath -To $destPath
    } else {
      Copy-Item -LiteralPath $sourcePath -Destination (Join-Path $destination ([IO.Path]::GetFileName($sourcePath))) -Force
    }
  }

  Write-Marker -Destination $destination -LineName $line.Name -SourcePaths $line.Sources
  Write-Output ("Mainline prepared: {0}" -f $destination)
}
