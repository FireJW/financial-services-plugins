# Obsidian KB Local

让 Codex 通过 Obsidian CLI 可靠地操作本地 Obsidian Vault。

## 目标

- 把 Vault 内容面和脚本控制面分开
- 默认只允许机器写入 `08-AI知识库`
- 让 Codex 复用固定命令，而不是每次临时拼 CLI 参数

## 目录

- `config/`: 本地 Vault 配置
- `src/`: CLI 封装与 bootstrap 计划生成
- `scripts/`: 可直接运行的入口脚本
- `templates/`: raw/wiki note 模板
- `tests/`: 不触碰真实 Vault 的本地测试

## 快速开始

1. 复制本地配置：

```powershell
Copy-Item config\vault.local.example.json config\vault.local.json
```

2. 运行环境检查：

```powershell
cmd /c npm run doctor
```

3. 如果 `doctor` 报告 CLI 未注册：

- 打开 Obsidian
- 进入 `Settings -> General`
- 启用 `Command line interface`
- 按提示注册 CLI
- 重新开一个终端窗口

4. 初始化 `08-AI知识库` 命名空间：

```powershell
cmd /c npm run bootstrap-vault
```

如果 CLI 还没注册，但你想先把静态目录和说明文档落到 Vault，可临时使用：

```powershell
node scripts/bootstrap-vault.mjs --filesystem-fallback
```

5. 跑一条真实写入 smoke：

```powershell
cmd /c npm run write-smoke
```

## Codex 绑定方式

Codex 以后优先调用这些命令：

```powershell
cmd /c npm run obsidian -- help
cmd /c npm run obsidian -- search query="Karpathy"
cmd /c npm run obsidian -- read path="08-AI知识库/00-控制台/KB Home.md"
```

更推荐使用仓库内脚本，而不是直接手写底层 CLI：

- `cmd /c npm run doctor`
- `cmd /c npm run bootstrap-vault`
- `cmd /c npm run write-smoke`

## Windows 备注

- 当前环境里 PowerShell 直接执行 `npm` 会被执行策略拦住
- 统一使用 `cmd /c npm ...` 或 `npm.cmd`
- Obsidian CLI 要求桌面端已安装并注册

## Provider Sync

- `node scripts/compile-source.mjs --execute` 默认读取 `%USERPROFILE%\.codex\config.toml` 和 `%USERPROFILE%\.codex\auth.json`
- 如果你用 `ccswitch` 切换 `.codex/config.toml`，下一次编译会自动跟随新的 `model`、`model_provider`、`wire_api` 和 `base_url`
- 如果 `ccswitch` 把 `auth.json` 切成 `auth_mode = "chatgpt"` 且没有 `OPENAI_API_KEY`，官方 OpenAI 路由会自动降级到 `codex exec`
- `chatgpt` 登录态只会给 `openai` 路由兜底，不会自动给 `custom` gateway 补 API key
- 如有需要，仍可用环境变量覆盖：`CODEX_HOME`、`CODEX_CONFIG_PATH`、`CODEX_AUTH_PATH`、`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`
- `cmd /c npm run doctor` 现在会同时检查 Obsidian CLI 和 Codex provider 是否就绪

## Real Compile Flow

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --topic \"LLM Knowledge Bases\" --execute"
```

Live provider diagnostics:

- `cmd /c npm run doctor` prints the current provider route
- `cmd /c npm run doctor:probe` verifies the active route with a real probe
- `auth_mode = "chatgpt"` without `OPENAI_API_KEY` now falls back to `codex exec`
- if `doctor` shows `route:blocked, auth-mode:chatgpt, api-key:missing, chatgpt-session:openai-only`, you are on a custom gateway without a usable API key
- `200` with an empty body is now reported as a gateway compatibility failure

## Codex Thread Capture

Use this when you want to persist a Codex thread outcome into the local
Obsidian KB raw layer and optionally compile it into wiki notes:

```powershell
@'
...final analysis body...
'@ | node scripts/capture-codex-thread.mjs --thread-uri "codex://threads/019d5746-28de-7631-ad1c-d35ca5815b94" --topic "specific topic" --title "2026-04-08 specific title" --source-label "Codex thread capture" --compile --timeout-ms 240000
```

Notes:

- writes to `08-AI知识库/10-raw/manual/`
- `thread-uri` is provenance only; it does not auto-fetch another thread's body
- body comes from stdin or `--body-file`
- if no explicit thread URI is provided, the command falls back to
  `codex://threads/current-thread`
- for reusable research, planning, trading, workflow, or KB content, prefer
  `--compile`

For multiple historical threads, use the batch manifest route:

```powershell
node scripts/init-codex-thread-batch.mjs --output-dir ".tmp-codex-thread-handoff-batch" --thread-id "019d5746-28de-7631-ad1c-d35ca5815b94" --thread-id "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab" --topic "历史 Codex 线程沉淀" --title-prefix "历史线程待整理"
node scripts/capture-codex-thread-batch.mjs --manifest ".\examples\codex-thread-batch.template.json" --compile --timeout-ms 240000
node scripts/verify-codex-thread-capture.mjs --thread-id "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab"
node scripts/reconcile-codex-thread-capture.mjs --output-dir ".tmp-codex-thread-reconcile-smoke" --thread-id "019d4cbd-823e-7ec2-8dd6-cfbd0b7232ab" --thread-id "019d-missing-demo-thread" --topic "历史 Codex 线程补录" --title-prefix "待补录线程"
```

The manifest supports:

- inline `body`
- relative `body_file`
- `thread_uri` or `thread_id`
- per-entry `compile` overrides

The verifier reports whether each thread has:

- matching raw notes
- matching wiki notes
- a captured/missing summary

The live Obsidian view for this workflow is:

- `08-AI知识库/30-views/00-System/08-Codex Thread Capture Status.md`
- `08-AI知识库/30-views/00-System/09-Codex Thread Recovery Queue.md`
- `08-AI知识库/30-views/00-System/10-Codex Thread Audit Log.md`

Refresh it with:

```powershell
node scripts/refresh-wiki-views.mjs
```

The refresh script now defaults to "try Obsidian CLI first, then fall back to
filesystem writes if the CLI stalls or fails". Use `--force-cli` only if you
explicitly want strict CLI-only behavior.

That status view also surfaces the latest `verify` and `reconcile` runs, so
you can audit capture coverage without leaving Obsidian.

For a terminal-side summary of capture / verify / reconcile history, run:

```powershell
node scripts/codex-thread-audit-report.mjs
node scripts/codex-thread-audit-doctor.mjs
```

To archive expired synthetic/demo audit entries into `logs/archive/`:

```powershell
node scripts/backfill-codex-thread-audit-run-ids.mjs
node scripts/backfill-codex-thread-audit-run-ids.mjs --apply
node scripts/prune-codex-thread-audit-logs.mjs --days 7
node scripts/prune-codex-thread-audit-logs.mjs --days 7 --apply
```

The reconciler writes:

- `verification-report.json`
- `missing-manifest.json`
- `bodies/*.md` templates for only the missing threads

成功时，脚本会调用当前 `.codex` 指向的 Responses API，解析返回的 JSON 数组，写入 wiki note，并把 raw note 标记为 `compiled`。

失败时，脚本会把 raw note 标记为 `error`，并把错误追加到 `logs/compile-errors-YYYY-MM-DD.jsonl`。
