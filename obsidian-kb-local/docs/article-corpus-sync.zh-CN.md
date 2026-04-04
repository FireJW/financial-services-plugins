# 历史公众号文章同步到 Obsidian

这条链路已经支持把之前产出的公众号文章同步到本地 Obsidian Vault，作为持续扩充的文章语料库，并自动生成一批机器维护的双链关系。

## 目标

- 历史文章进入 `08-AI知识库/10-raw/articles/`
- 保留原文、摘要、关键词、来源映射，供后续文章生成复用
- 可选把文章进一步编译成 wiki notes，沉淀 concepts / entities / sources
- 自动在文章和 wiki note 尾部写入 `## Related` 区块，形成 Obsidian backlink graph
- 编译时直接复用当前 `.codex/config.toml` 与 `.codex/auth.json` 的 LLM provider 配置

## 真实路径

- Vault: `D:\OneDrive - zn\文档\Obsidian Vault`
- Machine root: `08-AI知识库`
- 默认 artifact root: 仓库根目录下的 `.tmp/`

## Provider 绑定

编译脚本默认读取：

- `C:\Users\rickylu\.codex\config.toml`
- `C:\Users\rickylu\.codex\auth.json`

这意味着：

- 如果你用 `ccswitch` 切换 `.codex/config.toml`
- 下次运行编译或同步脚本时，会自动跟着新的 `model`、`model_provider`、`wire_api`、`base_url` 走
- 不需要在 `obsidian-kb-local` 里再维护一套单独 provider 配置

## 推荐命令

先看会导入哪些历史文章：

```powershell
cmd /c "cd obsidian-kb-local && npm run sync-article-corpus -- --dry-run --limit 20"
```

只导入语料，不触发编译：

```powershell
cmd /c "cd obsidian-kb-local && npm run sync-article-corpus -- --limit 5"
```

导入后立即编译成 wiki，并在最后统一重建双链：

```powershell
cmd /c "cd obsidian-kb-local && npm run sync-article-corpus -- --limit 3 --compile"
```

只导入单篇文章：

```powershell
cmd /c "cd obsidian-kb-local && npm run sync-article-corpus -- --target \"C:\path\to\article-publish-result.json\" --compile"
```

## 单独命令

如果你想拆开执行，也可以继续使用原子命令：

```powershell
cmd /c "cd obsidian-kb-local && npm run import-article-corpus -- --limit 5"
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --file \"08-AI知识库/10-raw/articles/你的文章.md\" --execute"
cmd /c "cd obsidian-kb-local && npm run rebuild-links"
```

现在 `compile-source.mjs --execute` 成功后会自动补跑一次 link rebuild，所以单篇编译后通常不需要再手动跑 `rebuild-links`。

## 双链策略

为了避免机器改坏正文，自动双链采用保守策略：

- 不直接改正文段落
- 只在尾部写机器维护区块
- 使用 `[[path/to/note|标题]]` 生成 Obsidian wikilink
- 下次重建时只覆盖机器维护区块，不动人工内容

## 当前限制

- 当前环境里 Obsidian Desktop 已检测到，但 CLI 注册仍显示未命中，所以写入主要走 filesystem fallback
- 这不影响 Vault 写入、文章导入、wiki 编译和双链生成
- 如果 Obsidian CLI 在宿主机上已经注册，但当前终端还没刷新 PATH，重开终端后再跑一次 `cmd /c npm run doctor`

## 建议工作流

1. 每次公众号文章正式产出后，把对应 workflow output 保留在 `.tmp/`
2. 定期执行 `sync-article-corpus --compile`
3. 让新的文章语料进入 raw lane
4. 让高价值文章被编译成概念 note 和实体 note
5. 通过 `## Related` 和 Obsidian 图谱逐步增强知识网
