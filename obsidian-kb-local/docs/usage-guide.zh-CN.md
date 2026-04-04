# Obsidian AI 知识库使用指南

> as of 2026-04-04

这份 guide 不是部署文档，而是“已经部署好了以后，到底怎么用”的说明。

如果你现在打开了 Obsidian，已经能看到 `08-AI知识库` 下面的内容，但不知道怎么让 LLM 继续总结、编译、补双链、增强知识库，就看这一份。

## 一句话先讲明白

这套系统里：

- Obsidian 是前端和浏览器
- `08-AI知识库/10-raw/` 是原始资料层
- `08-AI知识库/20-wiki/` 是 LLM 编译后的结构化知识层
- `08-AI知识库/30-views/` 是 Dataview 和巡检视图
- 真正调用 LLM 的地方，不在 Obsidian 按钮里，而在 `obsidian-kb-local/` 这套 CLI 控制平面里

也就是说，你在 Obsidian 里“看”和“组织”，真正的“让 AI 干活”，是在终端里跑脚本，或者让我直接替你跑这些脚本。

## 目录结构怎么理解

### `08-AI知识库/00-控制台`

这是控制台和操作说明区。

建议你先看：

- `08-AI知识库/00-控制台/KB Home.md`
- `08-AI知识库/00-控制台/Runbooks/`

### `08-AI知识库/10-raw`

这里放原始资料，不放最终结论。

常见 lane：

- `web`: 网页、文章、Web Clipper 导入内容
- `manual`: 你手工记录的想法、访谈、摘录
- `articles`: 你之前生成过的公众号文章语料
- `books`: 外部 EPUB 书库的路径索引
- `papers`: 论文
- `repos`: 仓库、项目、代码资料

### `08-AI知识库/20-wiki`

这是机器维护的知识层，主要分成：

- `concepts`
- `entities`
- `sources`
- `syntheses`

你可以把它理解为：LLM 把 raw 原料“编译”成更适合查询、串联、回看的知识节点。

### `08-AI知识库/30-views`

这是巡检和回看层。

当前重点看：

- `00-KB Dashboard.md`
- `01-Stale Notes.md`
- `02-Open Questions.md`
- `03-Sources by Topic.md`

## 你到底在哪调用 LLM

核心答案：在 `obsidian-kb-local` 目录下，通过脚本调用。

最关键的脚本是：

- `scripts/compile-source.mjs`

它支持两种典型方式：

1. 按 topic 编译一批 queued raw notes
2. 按文件路径编译一篇具体 raw note

### 只预览，不真正调用 LLM

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --topic \"LLM Knowledge Bases\" --dry-run"
```

这个模式会把 prompt 打出来，让你先看 AI 将会如何理解和编译，不会真正写入 wiki。

### 真正调用 LLM 执行编译

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --topic \"LLM Knowledge Bases\" --execute"
```

或者指定单篇 raw note：

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --file \"08-AI知识库/10-raw/web/你的资料.md\" --execute"
```

执行成功后，脚本会做几件事：

- 调用当前配置的 LLM provider
- 把结果写进 `20-wiki`
- 把 raw note 状态更新为 `compiled`
- 自动补跑双链重建，更新相关 note 的 `## Related`

## Codex 和 Obsidian 现在是什么关系

可以把它理解成：

- Obsidian 负责展示 Vault
- `obsidian-kb-local` 负责“控制”和“编译”
- Codex 负责帮你驱动这套控制平面

也就是说，我这边不是直接在 Obsidian UI 里点按钮，而是通过这些脚本去：

- 读 raw
- 调 LLM
- 写 wiki
- 跑 health check
- 重建 Related links

所以你以后最省心的用法其实是两种：

1. 你自己在终端里执行这些脚本
2. 你在对话里直接让我做，例如“把这批 raw 编译成 wiki”“同步历史文章到 Obsidian 并补双链”

## LLM provider 是怎么绑定的

这套知识库默认不单独维护一套 provider，而是直接复用 Codex 配置。

脚本默认读取：

- `C:\Users\rickylu\.codex\config.toml`
- `C:\Users\rickylu\.codex\auth.json`

也支持环境变量覆盖：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `OPENAI_MODEL`

这意味着：

- 如果你用 `ccswitch` 切换了 `.codex/config.toml`
- 下次 `compile-source --execute` 会自动跟着新的 provider / model / base URL 走
- 不需要再给 Obsidian KB 单独配一套 LLM 参数

这就是你前面希望建立的“Codex 和 Obsidian CLI 的绑定关系”。

## 你现在最常用的 6 个动作

### 1. 先做环境检查

```powershell
cmd /c "cd obsidian-kb-local && npm run doctor"
```

它会检查：

- Vault path
- machine root
- Obsidian Desktop
- Obsidian CLI 是否注册
- Codex LLM provider 是否可用

截至 2026-04-04，这个终端里的实际结果是：

- Vault 正常
- Machine root 正常
- Desktop app 检测正常
- Obsidian command entrypoint 已检测到
- LLM provider 正常

当前这台机器上，`doctor` 已能识别到 Obsidian 命令入口。

你可以把下面两种结果都视为可用：

- 检测到 `registered shim`
- 检测到 `desktop executable fallback`

前者表示系统里有更标准的 CLI/shim 入口，后者表示控制平面直接使用桌面可执行文件作为命令入口。

这两种模式都可以正常驱动 raw / wiki / 双链流程。

如果你以后又看到 `not found`，再按下面两步排查：

1. 彻底重开一个新终端
2. 再跑一次 `npm run doctor`

### 2. 导入网页或手工资料到 raw

网页资料推荐先用 Obsidian Web Clipper，或者手工把内容整理成 raw note 放到：

- `08-AI知识库/10-raw/web/`
- `08-AI知识库/10-raw/manual/`

如果你要用脚本入口：

```powershell
cmd /c "cd obsidian-kb-local && npm run ingest-web -- --url \"https://example.com/article\" --topic \"LLM Knowledge Bases\""
```

### 3. 让 LLM 总结并编译 raw -> wiki

最常用的就是：

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --file \"08-AI知识库/10-raw/web/你的资料.md\" --execute"
```

或者批量按 topic：

```powershell
cmd /c "cd obsidian-kb-local && node scripts/compile-source.mjs --topic \"Karpathy\" --execute"
```

编译后你就去 Obsidian 里看：

- `08-AI知识库/20-wiki/concepts/`
- `08-AI知识库/20-wiki/entities/`
- `08-AI知识库/20-wiki/sources/`
- `08-AI知识库/20-wiki/syntheses/`

### 4. 把历史公众号文章同步进语料库

如果你想把之前产出的公众号文章，持续作为“新语料库”喂给这套知识库，用这条链路：

```powershell
cmd /c "cd obsidian-kb-local && npm run sync-article-corpus -- --dry-run --limit 20"
cmd /c "cd obsidian-kb-local && npm run sync-article-corpus -- --limit 5"
cmd /c "cd obsidian-kb-local && npm run sync-article-corpus -- --limit 3 --compile"
```

含义分别是：

- `--dry-run`: 只看会导入哪些文章
- 不带 `--compile`: 只导入到 raw 层
- 带 `--compile`: 导入后立刻调用 LLM 编译成 wiki

这一步是“持续增强文章生成效果”的关键输入之一，因为它会把你自己已经产出的文章重新纳入知识图谱，而不是让它们散落在别处。

### 5. 把本地 EPUB 书库纳入 raw 层

这条链路不会复制 `.epub` 本体进 Vault，而是只做“外部路径索引”。

默认扫描：

- `D:\下载`
- `D:\桌面书单`

常用命令：

```powershell
cmd /c "cd obsidian-kb-local && npm run import-epub-library -- --dry-run"
cmd /c "cd obsidian-kb-local && npm run import-epub-library"
cmd /c "cd obsidian-kb-local && npm run import-epub-library -- --status queued"
```

解释：

- 默认更偏“建立书目索引”，不复制本体
- `books/` raw note 会保存绝对路径、URI、修改时间、大小等信息
- 带 `--status queued` 时，这批书籍条目会进入后续可编译队列

这非常适合大书库场景，因为不会把 Vault 和仓库变得又大又重。

### 6. 重建双链和巡检健康状态

重建 `## Related`：

```powershell
cmd /c "cd obsidian-kb-local && npm run rebuild-links"
```

跑健康检查：

```powershell
cmd /c "cd obsidian-kb-local && npm run health-check"
```

它会帮你发现：

- orphan wiki
- stale wiki
- missing source
- contract violations
- dedup conflicts

## 你说的“强化学习完善整个知识库”，在这里具体是什么意思

这里更准确的说法，不是“在本地重新训练模型”，而是“持续反馈增强知识库和生成流程”。

这套系统里的增强循环是：

1. 新资料进入 `10-raw`
2. LLM 用当前 `.codex` provider 进行编译
3. wiki 节点被补全、去重、重写、串联
4. `## Related` 自动更新
5. Dashboard / Stale Notes / Open Questions 帮你发现薄弱环节
6. 你继续补 raw，或者让我继续增量编译

所以这里的“强化”主要来自三类反馈：

- 新 raw 资料持续进入
- 编译结果持续反哺 wiki 结构
- 双链和健康检查持续暴露缺口

不是 RL 训练，而是 KB workflow 的持续迭代增强。

## 推荐日常工作流

如果你想把它真正变成日常系统，我建议按这个顺序来：

1. 新网页或新想法先进入 `10-raw`
2. 值得沉淀的主题，运行 `compile-source --execute`
3. 去 `20-wiki` 看机器新生成的概念、实体和来源节点
4. 去 `30-views` 看有没有 stale / missing source / open questions
5. 定期跑 `sync-article-corpus --compile` 把历史文章喂回来
6. 定期跑 `import-epub-library` 把新书目纳入索引
7. 定期跑 `rebuild-links` 和 `health-check`

## 什么时候在 Obsidian 里做，什么时候让我来做

适合在 Obsidian 里做的事：

- 浏览 raw 和 wiki
- 看图谱、Dataview、Dashboard
- 手工记一条想法或摘录
- 回看某个主题已经沉淀了什么

适合让我或终端脚本来做的事：

- 批量导入 raw
- 调用 LLM 编译 raw -> wiki
- 同步公众号历史文章
- 导入 EPUB 索引
- 重建双链
- 健康检查、去重、回滚

如果你懒得记命令，以后直接对我说这些就行：

- “把这篇 raw 编译成 wiki”
- “把最近 10 篇文章同步到 Obsidian，并顺手编译”
- “把书库重新扫描成 raw index”
- “给我重建一下这套知识库的双链”
- “跑一次 health check，告诉我哪里缺资料”

## 最后一个最实用的判断标准

如果你的目标是“看资料”，进 Obsidian。  
如果你的目标是“让 AI 生成、总结、编译、补链”，进 `obsidian-kb-local` 的脚本入口，或者直接让我替你执行。
