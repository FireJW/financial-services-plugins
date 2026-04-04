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

- `node scripts/compile-source.mjs --execute` 默认读取 `C:\Users\rickylu\.codex\config.toml` 和 `C:\Users\rickylu\.codex\auth.json`
- 如果你用 `ccswitch` 切换 `.codex/config.toml`，下一次编译会自动跟随新的 `model`、`model_provider`、`wire_api` 和 `base_url`
- 如有需要，仍可用环境变量覆盖：`CODEX_HOME`、`CODEX_CONFIG_PATH`、`CODEX_AUTH_PATH`、`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`
- `cmd /c npm run doctor` 现在会同时检查 Obsidian CLI 和 Codex provider 是否就绪

## Real Compile Flow

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --topic \"LLM Knowledge Bases\" --execute"
```

成功时，脚本会调用当前 `.codex` 指向的 Responses API，解析返回的 JSON 数组，写入 wiki note，并把 raw note 标记为 `compiled`。

失败时，脚本会把 raw note 标记为 `error`，并把错误追加到 `logs/compile-errors-YYYY-MM-DD.jsonl`。
