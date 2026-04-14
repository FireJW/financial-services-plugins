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

## Product / Design Feedback Workflow Routing

When the task is about product or design feedback operations, use the repo's
native route before generic browsing:

1. `financial-analysis/commands/feedback-workflow.md`
2. `financial-analysis/skills/feedback-iteration-workflow/SKILL.md`
3. if facts are moving or freshness matters, also read
   `financial-analysis/skills/autoresearch-info-index/SKILL.md`

Use this route when the user wants interviews, podcasts, talks, support logs,
customer calls, social posts, or research notes turned into a workflow, SOP,
priorities brief, or iteration cadence.

Hard rules:

- anchor claims to exact dates
- separate direct quote, summary, and inference
- never upgrade host summary material into verbatim quote
- never present AI synthesis as a replacement for product or design judgment

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

## Workspace Safety

- Do not use `.gemini/antigravity/scratch/` as the canonical home for this repo.
- The canonical working copy for this repo should be:
  - `D:\Users\rickylu\dev\financial-services-plugins`
- WSL remains optional, but if used, keep the canonical repo inside the Linux filesystem, not `/mnt/c/...`.
- Do not change the user's active C-drive Codex home/config unless they explicitly ask for a Codex configuration migration.
- Before risky recovery or agent-heavy work, run:
  - `.\scripts\check-workspace-safety.ps1`
  - `.\scripts\repo-snapshot.ps1 -BackupRoot "D:\Users\rickylu\repo-safety-backups\financial-services-plugins" -MirrorLatest -IncludeGit`
- To prepare a stable non-scratch working copy, use:
  - `.\scripts\prepare-safe-workspace.ps1 -TargetRoot "D:\Users\rickylu\dev" -IncludeGit -IncludeTmp -Execute`
- To lift the main lines into focused sibling workspaces, use:
  - `.\scripts\promote-mainlines.ps1 -Execute`
- Full guidance lives in:
  - `docs/runtime/workspace-safety.md`

## Large File Handling Rules

> **Hard Rule**: 行数超过 400 行的代码文件或大型文件，会导致模型调用卡住（token 溢出、写入超时、上下文截断等）。**严禁一口气写入或提交所有内容。**

### 必须遵守的操作规范

1. **拆分为多次步骤（Incremental Steps）**
   - 将大文件的创建/修改拆分为多个独立的、可验证的步骤
   - 每次写入/编辑控制在 **200-300 行以内**
   - 每步完成后验证结果再进行下一步

2. **使用 Sub-agents 并行处理**
   - 对于独立的代码模块，使用 `Agent` 工具分派给子代理并行完成
   - 每个子代理负责一个明确的、范围有限的子任务
   - 子代理完成后，主代理负责整合和验证

3. **禁止的操作**
   - ❌ 一次性 `Write` 超过 400 行的完整文件
   - ❌ 一次性 `Edit` 涉及超过 300 行变更的大范围替换
   - ❌ 在单个 `git commit` 中包含未经分步验证的大量新增代码

4. **推荐的工作流程**
   ```
   Step 1: 创建文件骨架（imports、类/函数签名、导出）
   Step 2: 逐个填充核心函数实现
   Step 3: 添加辅助函数和工具方法
   Step 4: 补充错误处理和边界情况
   Step 5: 验证完整性并提交
   ```

5. **适用场景**
   - 新建大型源代码文件
   - 大规模重构现有文件
   - 批量生成配置文件、测试文件
   - 任何预估产出超过 400 行的任务
