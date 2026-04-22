param(
  [ValidateSet("auto", "content", "shortlist")]
  [string]$Profile = "auto"
)

$ErrorActionPreference = "Stop"

function Write-Utf8Text {
  param(
    [string]$Path,
    [string]$Content
  )

  $encoding = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Resolve-RepoRoot {
  $repoRoot = (& git rev-parse --show-toplevel 2>$null)
  if (-not $repoRoot) {
    throw "Not inside a git repository."
  }

  return (Resolve-Path -LiteralPath $repoRoot).Path
}

function Resolve-Profile {
  param(
    [string]$RepoRoot,
    [string]$RequestedProfile
  )

  if ($RequestedProfile -ne "auto") {
    return $RequestedProfile
  }

  $repoName = Split-Path -Leaf $RepoRoot
  if ($repoName -ieq "financial-services-plugins-clean") {
    return "shortlist"
  }

  return "content"
}

function New-ClaudeManagedBlock {
  param(
    [string]$ResolvedProfile
  )

  if ($ResolvedProfile -eq "shortlist") {
    return @'
<!-- codex:native-routing:start -->
## Current Status and Direct Usage

Before choosing a workflow in this repo, read:

- `docs/superpowers/notes/2026-04-21-claude-status-and-direct-usage.md`

That note records the currently observed branch/worktree state and the fastest
native entrypoints for shortlist, cache-preheat, macro-health, and X-style
assisted shortlist work.

## Native-First Retrieval Contract

Before using generic web search, public-page scraping, or ad hoc browsing for a
fresh-information task:

1. check `routing-index.md`
2. match the task to a native command or skill
3. use the native route first if one exists

Default routing examples:

- broader multi-channel discovery or upstream augmentation -> `agent-reach-bridge`
- fast current-state note -> `news-index`
- X / Twitter evidence -> `x-index`
- authenticated or dynamic page capture -> `opencli-index`
- topic ranking before drafting -> `hot-topics`
- end-to-end content pipeline -> `article-workflow`
- A-share shortlist generation -> `month-end-shortlist`

Web search is fallback-only unless:

- no native route exists
- the native route cannot reach the needed source
- the user explicitly asks for web-first collection

If fallback is necessary, say which native route was checked and why it was not
enough.

Phrase-match shortcuts:

- "月底短线" / "筛一批月底最有希望涨的" -> `month-end-shortlist`
- "给 shortlist 叠一层宏观判断" -> `macro-health-assisted-shortlist`
- "把 X 风格偏好叠进 shortlist" -> `x-style-assisted-shortlist`
- "先预热 Eastmoney cache" / "减少 bars_fetch_failed" -> `financial-analysis/skills/month-end-shortlist/scripts/preheat_eastmoney_cache.py`
- "给我一个当前态判断" / "最新进展到底怎样" -> `news-index`
- "整理这个 X thread 的证据" -> `x-index`
- "把 Agent Reach 的发现并进当前判断" -> `agent-reach-bridge`
- "这个登录态或动态页面抓一下" -> `opencli-index`

Freshness wording guardrail:

- `latest`, `today`, `recent`, `最新`, `今天`, `近期` do not automatically mean web-first
- first check whether `month-end-shortlist`, `news-index`, `x-index`, `agent-reach-bridge`, `opencli-index`, or `hot-topics` already fit the freshness need
- only jump to generic web search when those native freshness routes do not fit
<!-- codex:native-routing:end -->
'@.Trim()
  }

  return @'
<!-- codex:native-routing:start -->
## Current Status and Direct Usage

Before choosing a workflow in this repo, read:

- `docs/superpowers/notes/2026-04-21-claude-status-and-direct-usage.md`

That note records the currently observed branch/worktree state and the fastest
native entrypoints for hot-topic discovery, news/X indexing, article workflow,
and publishing work.

## Native-First Retrieval Contract

Before using generic web search, public-page scraping, or ad hoc browsing for a
fresh-information task:

1. check `routing-index.md`
2. match the task to a native command or skill
3. use the native route first if one exists

Default routing examples:

- broader multi-channel discovery or upstream augmentation -> `agent-reach-bridge`
- fast current-state note -> `news-index`
- X / Twitter evidence -> `x-index`
- authenticated or dynamic page capture -> `opencli-index`
- topic ranking before drafting -> `hot-topics`
- end-to-end content pipeline -> `article-workflow`

Web search is fallback-only unless:

- no native route exists
- the native route cannot reach the needed source
- the user explicitly asks for web-first collection

If fallback is necessary, say which native route was checked and why it was not
enough.

Phrase-match shortcuts:

- "今天有什么值得写" / "先排热点优先级" -> `hot-topics`
- "给我一个当前态判断" / "最新进展到底怎样" -> `news-index`
- "整理这个 X thread 的证据" -> `x-index`
- "把 Agent Reach 的发现并进当前判断" -> `agent-reach-bridge`
- "这个登录态或动态页面抓一下" -> `opencli-index`
- "直接给我完整成文流程" -> `article-workflow`

Freshness wording guardrail:

- `latest`, `today`, `recent`, `最新`, `今天`, `近期` do not automatically mean web-first
- first check whether `news-index`, `x-index`, `agent-reach-bridge`, `opencli-index`, or `hot-topics` already fit the freshness need
- only jump to generic web search when those native freshness routes do not fit
<!-- codex:native-routing:end -->
'@.Trim()
}

function New-RoutingManagedBlock {
  return @'
<!-- codex:native-routing-fast-map:start -->
## Native Retrieval Fast Map

Generic web search and public scraping are fallback-only when one of the
following native routes fits the task.

- Multi-channel discovery breadth, upstream augmentation, or Agent Reach import
  - Primary path: `financial-analysis/commands/agent-reach-bridge.md`
  - Fallback rule: use web search only if Agent Reach is unavailable or the
    needed source is outside the bridgeable channels
- Fast current-state note with freshness windows and claim ledger
  - Primary path: `financial-analysis/commands/news-index.md`
  - Fallback rule: use web search only if native retrieval cannot cover the
    required source set
- X / Twitter threads, timestamps, screenshots, or reusable evidence packs
  - Primary path: `financial-analysis/commands/x-index.md`
  - Fallback rule: use public X scraping only after native signed-session paths
    are unavailable
- Authenticated or dynamic source capture
  - Primary path: `financial-analysis/commands/opencli-index.md`
  - Fallback rule: use manual browsing only if the page cannot be captured
    through OpenCLI or a stronger native route exists
- Topic ranking before drafting
  - Primary path: `financial-analysis/commands/hot-topics.md`
  - Fallback rule: use generic search only if the source mix is outside the
    configured discovery surface
- End-to-end article pipeline
  - Primary path: `financial-analysis/commands/article-workflow.md`
  - Fallback rule: use ad hoc browsing only when a required upstream source is
    not reachable through `news-index`, `x-index`, `agent-reach-bridge`, or
    `opencli-index`
- A-share shortlist generation or overlay-assisted ranking
  - Primary path: `financial-analysis/commands/month-end-shortlist.md`
  - Fallback rule: use generic search only if the task is truly outside the
    repo's shortlist workflow and no overlay path fits

If a fallback happens, record which native route was checked first and why it
was insufficient.
<!-- codex:native-routing-fast-map:end -->
'@.Trim()
}

function Replace-ManagedSection {
  param(
    [string]$Content,
    [string]$StartMarker,
    [string]$EndMarker,
    [string]$LegacyStartHeading,
    [string]$LegacyEndHeading,
    [string]$Replacement
  )

  $markerPattern = "(?s)$([regex]::Escape($StartMarker)).*?$([regex]::Escape($EndMarker))"
  if ([regex]::IsMatch($Content, $markerPattern)) {
    return [regex]::Replace(
      $Content,
      $markerPattern,
      [System.Text.RegularExpressions.MatchEvaluator]{
        param($match)
        $Replacement
      }
    )
  }

  $legacyPattern = "(?ms)^$([regex]::Escape($LegacyStartHeading))\s*.*?(?=^$([regex]::Escape($LegacyEndHeading))\s*$)"
  if ([regex]::IsMatch($Content, $legacyPattern)) {
    return [regex]::Replace(
      $Content,
      $legacyPattern,
      [System.Text.RegularExpressions.MatchEvaluator]{
        param($match)
        $Replacement
      }
    )
  }

  throw "Unable to locate managed section starting at '$LegacyStartHeading'."
}

function Normalize-TrailingNewline {
  param(
    [string]$Content
  )

  return ([regex]::Replace($Content, '(?:\r?\n)+\z', "`r`n"))
}

$repoRoot = Resolve-RepoRoot
$resolvedProfile = Resolve-Profile -RepoRoot $repoRoot -RequestedProfile $Profile

$claudePath = Join-Path $repoRoot "CLAUDE.md"
$routingPath = Join-Path $repoRoot "routing-index.md"

if (-not (Test-Path -LiteralPath $claudePath)) {
  throw "Missing CLAUDE.md: $claudePath"
}

if (-not (Test-Path -LiteralPath $routingPath)) {
  throw "Missing routing-index.md: $routingPath"
}

$claudeContent = Get-Content -Raw -LiteralPath $claudePath -Encoding UTF8
$routingContent = Get-Content -Raw -LiteralPath $routingPath -Encoding UTF8

$claudeReplacement = New-ClaudeManagedBlock -ResolvedProfile $resolvedProfile
$routingReplacement = New-RoutingManagedBlock

$claudeContent = Replace-ManagedSection `
  -Content $claudeContent `
  -StartMarker "<!-- codex:native-routing:start -->" `
  -EndMarker "<!-- codex:native-routing:end -->" `
  -LegacyStartHeading "## Current Status and Direct Usage" `
  -LegacyEndHeading "## Capability-First Routing" `
  -Replacement ($claudeReplacement + "`r`n")

$routingContent = Replace-ManagedSection `
  -Content $routingContent `
  -StartMarker "<!-- codex:native-routing-fast-map:start -->" `
  -EndMarker "<!-- codex:native-routing-fast-map:end -->" `
  -LegacyStartHeading "## Native Retrieval Fast Map" `
  -LegacyEndHeading "## X post evidence extraction" `
  -Replacement ($routingReplacement + "`r`n")

Write-Utf8Text -Path $claudePath -Content (Normalize-TrailingNewline -Content $claudeContent)
Write-Utf8Text -Path $routingPath -Content (Normalize-TrailingNewline -Content $routingContent)

Write-Output ("Updated native routing blocks for profile '{0}'." -f $resolvedProfile)
Write-Output ("CLAUDE.md: {0}" -f $claudePath)
Write-Output ("routing-index.md: {0}" -f $routingPath)

