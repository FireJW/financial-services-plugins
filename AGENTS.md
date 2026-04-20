# Financial Services Plugins

This is a marketplace of Codex Cowork plugins for financial services
professionals. Each subdirectory is a standalone plugin.

## Repository Structure

```text
|-- investment-banking/  # Investment banking productivity
```

## Plugin Structure

Each plugin follows this layout:

```text
plugin-name/
|-- .Codex-plugin/plugin.json   # Plugin manifest (name, description, version)
|-- commands/                   # Slash commands (.md files)
|-- skills/                     # Knowledge files for specific tasks
|-- hooks/                      # Event-driven automation
|-- mcp/                        # MCP server integrations
`-- .Codex/                     # User settings (*.local.md)
```

## Key Files

- `marketplace.json`: Marketplace manifest - registers all plugins with source paths
- `plugin.json`: Plugin metadata - name, description, version, and component discovery settings
- `commands/*.md`: Slash commands invoked as `/plugin:command-name`
- `skills/*/SKILL.md`: Detailed knowledge and workflows for specific tasks
- `*.local.md`: User-specific configuration (gitignored)
- `mcp-categories.json`: Canonical MCP category definitions shared across plugins

## Development Workflow

1. Edit markdown files directly - changes take effect immediately
2. Test commands with `/plugin:command-name` syntax
3. Skills are invoked automatically when their trigger conditions match

## Dual-Track Task Classification

Every task must be classified before execution.

Use `Simple` only when all of the following are true:

- fewer than 3 files change
- the work stays in one repo
- no live data, API, login state, or browser session is needed
- no workflow asset is added or changed
- one local check or one quick manual inspection is enough
- the goal and output shape are already clear

Use `Complex` when any of those conditions fail.

If uncertain, classify as `Complex`.

If a simple task grows beyond those bounds, stop and escalate:

1. record why it escalated
2. build a context pack
3. check `routing-index.md`
4. load related docs and KB assets
5. restate verification before continuing


## Capability-First Routing

Before using generic browsing, web search, or ad hoc scraping, always route
through the repository's native capability surface first.

Routing order:

1. scan `commands/` for a task-specific entrypoint
2. read the matching `skills/*/SKILL.md` and runtime helpers under `scripts/`
3. use the task-specific workflow if it exists
4. only fall back to generic browser automation (`browse`, `playwright`) or
   public web scraping when no signed-session or task-specific workflow exists

For platform-specific requests, do not start with public-page scraping if the
repo already contains a signed-session or authenticated workflow.

## Classic Case Routing

When a request matches a recurring case pattern, do not improvise the workflow
from scratch. Read the case router first:

- `financial-analysis/skills/classic-case-router/SKILL.md`

Then pick the nearest case file and follow its native route:

- latest event verification
- X post evidence extraction
- macro shock chain mapping
- evidence to article
- workflow improvement loop

Use the case router before broad tool selection when the user is effectively
asking for a repeated workflow we have already handled.

## Product / Design Feedback Workflow Routing

When a request is about any of the following, treat it as a feedback-to-
iteration workflow task and use the repo's native workflow first:

- collect interviews, talks, podcasts, or public posts from a product or
  design leader and convert them into an operating workflow
- reconstruct how a team uses AI to digest user feedback, support tickets,
  customer calls, social posts, or research notes
- turn messy feedback into product priorities, design principles, weekly briefs,
  or research-preview iteration loops
- separate direct quotes from host summaries and inference before drawing a
  process conclusion

### Native Routing Order

1. `financial-analysis/commands/feedback-workflow.md`
2. `financial-analysis/skills/feedback-iteration-workflow/SKILL.md`
3. if the request also depends on moving facts or fresh source collection,
   read `financial-analysis/skills/autoresearch-info-index/SKILL.md`
4. only fall back to generic browser automation or broad web search after the
   native route has been checked

### Non-Negotiable Rules

- always stamp the output with an exact `as of` date
- separate `direct quote`, `direct-ish`, `summary`, and `inference only`
- do not upgrade host recap material into direct quotes
- do not claim a fixed SOP when the public evidence only supports a partial
  reconstruction
- do not let AI-synthesis steps replace the human judgment node in the
  workflow

### X / Twitter Routing

For X post and thread collection, prefer:

1. `/x-index`
2. `browser_session.strategy = "remote_debugging"` on Windows
3. `browser_session.strategy = "cookie_file"` only as fallback

Do not start with public X page scraping when `x-index` plus a signed browser
session can be used.

Additional Windows defaults for X session handling:

- reuse the last successful X workflow in the current workspace or continuing
  thread before bootstrapping a fresh login-state path
- prefer opening a new Edge window in the user's existing signed-in profile
  when visible search/capture is enough
- do not close the user's current Edge windows or pages by default just to get
  login state
- only use a close-and-relaunch remote-debug path after the user explicitly
  approves that interruptive step

## A-Share Event-Driven Research Defaults

When the user asks for any of the following, treat it as an A-share
event-driven research task and use the repo's native research workflows first:

- which China stocks benefit or suffer from war, oil, gas, shipping, tariff,
  sanction, or policy shocks
- why one or more stocks stopped following a commodity or index
- compare 2+ stocks under the same macro event
- combine business model, sector chain, valuation, and technical/chart context
- assess whether a move is headline-driven, earnings-driven, or just a theme

### Native Routing Order

For these tasks, use this routing order before generic browsing:

1. `financial-analysis/skills/autoresearch-info-index/SKILL.md`
   - use first when facts are moving quickly, the user asks for `latest`,
     `today`, `currently`, or the event depends on news flow
2. `financial-analysis/skills/macro-shock-analysis/SKILL.md`
   - use for war, commodity spikes, sanctions, shipping disruption, inflation
     shocks, and policy shocks
3. `equity-research/commands/sector.md` plus
   `equity-research/skills/sector-overview/SKILL.md`
   - use to map the value chain, market structure, and where value accrues
4. `equity-research/commands/earnings.md` plus
   `equity-research/skills/earnings-analysis/SKILL.md`
   - use when the debate depends on latest earnings, guidance, margins, cash
     flow, or company announcements
5. `equity-research/commands/model-update.md` plus
   `equity-research/skills/model-update/SKILL.md`
   - use when the user asks whether the shock changes earnings power,
     sensitivity, rerating logic, or target-price logic
6. `equity-research/commands/screen.md` plus
   `equity-research/skills/idea-generation/SKILL.md`
   - use to screen direct beneficiaries, second-order beneficiaries, and likely
     false positives
7. `equity-research/commands/catalysts.md` and
   `equity-research/commands/morning-note.md`
   - use for event timelines, near-term catalyst calendars, and reaction checks
8. `financial-analysis/skills/comps-analysis/SKILL.md`
   - use when the user asks for relative valuation, peer premium/discount, or
     cross-company comparison
9. `financial-analysis/skills/dcf-model/SKILL.md`
   - use when the user explicitly asks for intrinsic value, fair value, or a
     model-backed entry range

Only fall back to generic browser automation or public web search after the
repo's native research path has been checked.

### Latest-Data Rules

- Always stamp the analysis with an exact `as of` date.
- For words like `latest`, `today`, `recent`, `current`, or `still`, verify the
  true latest data and quote exact dates.
- Separate `confirmed`, `likely`, and `inference only`.
- For event-driven work, separate `physical disruption` from `risk premium`.
- Do not write `oil up therefore stock up`; show the transmission path.

### Subagent Default For Stock/Event Analysis

If the task covers 2+ stocks, or one macro shock plus multiple industry links,
default to parallel subagents.

Preferred split:

1. local thread
   - define the shock in one line
   - verify one anchor fact with an absolute date
   - classify each company by value-chain position before waiting on agents
2. subagent A
   - verify the live event tape, public announcements, and benchmark moves
3. subagent B
   - research the first stock group or the direct beneficiaries
4. subagent C
   - research the second stock group or the likely false beneficiaries /
     cost-takers
5. optional subagent D
   - valuation, chart/technical overlay, or article/image extraction

Do not wait idle for subagents if the framing work can continue locally.

### Non-Negotiable Research Rules

- Anchor all time-sensitive claims to absolute dates.
- Separate `confirmed`, `likely`, and `inference only`.
- Never write `oil up = all energy-chain stocks benefit`.
- Classify every company before concluding:
  1. upstream producer / resource owner
  2. oilfield service / equipment / order-cycle company
  3. domestic substitution / energy-security beneficiary
  4. downstream material maker / cost taker
- Separate:
  1. first-round price effect
  2. second-round margin or order effect
  3. third-round policy, liquidity, or valuation effect
- Split stock behavior into:
  1. headline trade
  2. earnings-transmission check
  3. position unwind or re-rating
- If a company is a downstream processor or materials maker, explicitly test
  whether higher input costs hurt before calling it a beneficiary.
- If a stock has decoupled from the benchmark, explain whether the break comes
  from fundamentals, timing lag, policy, financing, disclosure, or positioning.
- If technical/chart analysis is included, treat it as an overlay after
  business model and earnings transmission are established, not as the primary
  proof.

### Universal Analysis Template

Use this default structure unless the user requests a different format.

1. `One-line judgment`
   - one sentence only, state the main conclusion
2. `Current state`
   - confirmed facts
   - unresolved facts
   - exact data cutoff date
3. `Shock or driver in one line`
   - what changed
   - when it changed
   - which benchmark matters most
4. `Company classification`
   - what each company actually does
   - where it sits in the chain
5. `Transmission chain`
   - event -> benchmark -> industry pass-through -> company economics ->
     market pricing
6. `Why the stock is or is not following the driver`
   - separate theme trading from true earnings transmission
7. `Benefit vs damage verdict`
   - direct beneficiary
   - indirect or lagged beneficiary
   - mixed / conditional
   - likely harmed
8. `Horizon split`
   - `0-72h`
   - `1-4w`
   - `1-3m`
9. `What changes the view`
   - invalidation triggers
   - upgrade triggers
10. `Sources`
    - official filings first
    - then primary or high-quality news sources

### Recommended Default Tables

Always prefer practical tables over loose prose. Use at least the first two by
default.

**1. Fact board**

| Item | Latest reading | Exact date | Source | Confidence |
|------|----------------|------------|--------|------------|

**2. Core comparison table**

| Stock | Core business | Chain position | First sensitivity factor | Benefit or damage | Conclusion |
|------|---------------|----------------|--------------------------|-------------------|------------|

**3. Logic-chain table**

| Step | Key question | If true | If false |
|------|--------------|---------|----------|

**4. Trading horizon table**

| Horizon | What the market is trading | Fundamentals or sentiment | Signals to monitor |
|---------|-----------------------------|---------------------------|--------------------|

### Recommended Reusable Templates

#### Template A: Macro Shock -> Beneficiaries / Losers

Use when the user asks which stocks benefit from or are harmed by an event.

Required sections:

1. shock in one line
2. physical disruption vs risk premium
3. benchmark that actually matters
4. beneficiary chain
5. loser chain
6. false-beneficiary check
7. scenario table
8. watch items

#### Template B: Multi-Stock Comparison Under One Event

Use when comparing 2+ stocks under one macro or sector driver.

Required sections:

1. business model snapshot for each stock
2. chain position comparison
3. why each stock did or did not move with the driver
4. direct vs indirect vs mixed classification
5. best expression vs worst expression of the theme

#### Template C: Single-Stock Deep Dive

Use when the user wants one company's business model, outlook, valuation, and
event sensitivity.

Required sections:

1. business model
2. revenue and profit drivers
3. key debate
4. event sensitivity
5. earnings / valuation check
6. bull / base / bear path

#### Template D: Three-Stage Trading Map

Use when the user asks for entry ranges, support levels, or a practical
trading plan around a catalyst.

Required structure:

1. `pre-confirmation zone`
   - only partial position or watchlist
   - focus on whether the event broadens or fades
2. `confirmation zone`
   - add only if price action and fundamental transmission align
   - define the signals that confirm the thesis
3. `exhaustion / unwind zone`
   - trim if only narrative remains while earnings proof is absent
   - state what a failed trade looks like

When giving entry ideas, clearly label them as:

- `theme entry`
- `fundamental confirmation entry`
- `risk-control / invalidation level`

### Preferred Final Answer Order

1. conclusion first
2. what changed and why it matters now
3. transmission chain
4. company-by-company judgment
5. what is already priced vs not yet priced
6. trading / valuation read-through
7. risks, invalidation, and what to watch next

### Preliminary Mode

When the factual layer is still moving:

- label items as `confirmed`, `likely`, or `too early to call`
- avoid fake precision on probabilities or target prices
- state which new facts would upgrade or downgrade the view

### Default Writing Standard

For Chinese stock analysis in this repo:

- write plain, direct Chinese
- do not hide uncertainty
- do not overuse jargon if a simpler description is available
- prefer `why` and `how the money moves` over slogan-style market language
- if the user says `latest` or uses relative dates like `today`, restate the
  conclusion with an exact date

## Worktree & File Ownership Rules

- Codex sandbox users (`CodexSandboxOffline`, `CodexSandboxOnline`) run under a
  different Windows identity than the repo owner (`rickylu`). Files and
  directories they create are owned by the sandbox account, which triggers git's
  `safe.directory` protection for any later session running as `rickylu`.
- **Do not create git worktrees** (`git worktree add`) from a Codex sandbox
  session. Instead, produce patch files (`git format-patch`) and let the user or
  a `rickylu`-owned session apply them.
- If a task requires an isolated branch, create the branch in the existing repo
  (`git branch` / `git checkout -b`) rather than adding a new worktree. Branch
  creation does not produce ownership-mismatched directories.
- If a worktree is absolutely necessary, the Codex agent must call
  `takeown /f <path> /r /d y` and `icacls <path> /grant rickylu:F /t`
  immediately after creation so subsequent sessions can operate on it.
- All git commands that touch the worktree or index must run **serially** — never
  in parallel. Parallel git operations on the same worktree produce misleading
  status snapshots and can corrupt the index.

## Git Safety Rules

- Before any delete, cleanup, move, rename, rollback, codemod, or batch file
  rewrite, create a git-inclusive external snapshot first with
  `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/repo-snapshot.ps1 -BackupRoot "D:\Users\rickylu\repo-safety-backups\financial-services-plugins" -MirrorLatest -IncludeGit`.
- Treat `D:\Users\rickylu\repo-safety-backups\financial-services-plugins\` and
  any mirrored snapshot output as read-only during normal development. Do not
  stage, edit, prune, or delete backup contents unless the user explicitly asks
  to manage backups.
- Any file-affecting operation must have a dry-run or preview phase first.
  Surface the exact candidate file list before execution for delete, cleanup,
  move, rename, rollback, or bulk writes.
- If a tool lacks `--dry-run`, `-WhatIf`, or preview mode, stop and produce an
  equivalent candidate report before executing the real write or delete step.
- Never stage `.tmp/`, `.tmp-*`, root-level `tmp-*`, browser session/profile
  data, screenshots, caches, or database files unless the user explicitly asks
  to version them.
- Large staged diffs can make Codex unstable on startup because the app
  inspects staged changes when opening the workspace. Treat unexpectedly large
  staging areas as a failure condition, not a cleanup task for later.
- Before any commit or broad `git add`, inspect `git status --short` and
  `git diff --cached --stat`. If the staged scope is wider than intended, stop
  and clean the index first.
- Prefer targeted `git add <path>` over `git add .` or `git add -A` in this
  repository.
- For manual staging or CLI-assisted staging, prefer
  `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/git-stage-safe.ps1 <path>...`
  so blocked runtime artifacts are scrubbed from the index immediately after
  `git add`.
- If another tool stages files directly, run
  `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/git-scrub-staged-runtime-artifacts.ps1`
  before doing anything else. Treat any staged `.tmp` content as a stop
  condition.
- If a runtime artifact needs to be kept for tests or examples, move it under a
  stable non-temp path such as `examples/` or `tests/fixtures/` instead of
  `.tmp/`.
- Keep the execution order strict: backup -> dry-run preview -> targeted
  execute -> post-change verification.
