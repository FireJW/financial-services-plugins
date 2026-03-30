# Financial Services Plugins

This is a marketplace of Claude Cowork plugins for financial services professionals. Each subdirectory is a standalone plugin.

## Repository Structure

```
├── investment-banking/  # Investment banking productivity
```

## Plugin Structure

Each plugin follows this layout:
```
plugin-name/
├── .claude-plugin/plugin.json   # Plugin manifest (name, description, version)
├── commands/                    # Slash commands (.md files)
├── skills/                      # Knowledge files for specific tasks
├── hooks/                       # Event-driven automation
├── mcp/                         # MCP server integrations
└── .claude/                     # User settings (*.local.md)
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

## Capability-First Routing

Before using generic browsing, web search, or ad hoc scraping, always route through
the repository's native capability surface first.

Routing order:

1. scan `commands/` for a task-specific entrypoint
2. read the matching `skills/*/SKILL.md` and runtime helpers under `scripts/`
3. use the task-specific workflow if it exists
4. only fall back to generic browser automation (`browse`, `playwright`) or public web scraping when no signed-session or task-specific workflow exists

For platform-specific requests, do not start with public-page scraping if the repo
already contains a signed-session or authenticated workflow.

### X / Twitter Routing

For X post and thread collection, prefer:

1. `/x-index`
2. `browser_session.strategy = "remote_debugging"` on Windows
3. `browser_session.strategy = "cookie_file"` only as fallback

Do not start with public X page scraping when `x-index` plus a signed browser
session can be used.

## Git Safety Rules

- Never stage `.tmp/`, `.tmp-*`, root-level `tmp-*`, browser session/profile data, screenshots, caches, or database files unless the user explicitly asks to version them.
- Large staged diffs can make Codex unstable on startup because the app inspects staged changes when opening the workspace. Treat unexpectedly large staging areas as a failure condition, not a cleanup task for later.
- Before any commit or broad `git add`, inspect `git status --short` and `git diff --cached --stat`. If the staged scope is wider than intended, stop and clean the index first.
- Prefer targeted `git add <path>` over `git add .` or `git add -A` in this repository.
- For manual staging or CLI-assisted staging, prefer `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\git-stage-safe.ps1 <path>...` so blocked runtime artifacts are scrubbed from the index immediately after `git add`.
- If another tool stages files directly, run `C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\git-scrub-staged-runtime-artifacts.ps1` before doing anything else. Treat any staged `.tmp` content as a stop condition.
- If a runtime artifact needs to be kept for tests or examples, move it under a stable non-temp path such as `examples/` or `tests/fixtures/` instead of `.tmp/`.

## Codex Workflow

Repository-level Codex workflow guidance now lives in:

- `CODEX_DEVELOPMENT_FLOW.md`
- `.context/prefs/coding-style.md`
- `.context/prefs/workflow.md`
- `.context/prefs/review-checklist.md`

Logging helpers:

- `scripts/codex-context-log.ps1`
- `scripts/codex-context-show.ps1`
- `scripts/codex-plan-init.ps1`
- `scripts/codex-review-init.ps1`
- `scripts/codex-handoff-init.ps1`
- `scripts/codex-handoff-refresh.ps1`

Keep runtime output in `.tmp/` and durable workflow knowledge in `.context/`.
When a task changes process, architecture, or handoff expectations, log the decision instead of relying on chat memory alone.
For Windows CLI continuation, use explicit commands like
`C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\codex-plan-init.ps1 -Name "task-name"`
instead of assuming `pwsh` is available.
