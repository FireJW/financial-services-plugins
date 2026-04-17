# Codex Prompt — Unit 5: Obsidian Backflow and Pilot Checkpoint

## Goal

完成试点闭环的最后一公里：将已产出的公众号文章回流到 Obsidian Vault，验证 `sync-article-corpus.mjs` 链路，并产出试点复盘文档。

## Pre-condition

- Unit 2 / 3 / 4 至少产出了 1 篇完成 `article-publish` 的文章包。
- `obsidian-kb-local` 的回流链路可用。
- Obsidian Vault 路径可写：`D:\OneDrive - zn\文档\Obsidian Vault`

## Steps

### Step 1: sync-article-corpus 回流测试

1. 选取 Unit 2、3 或 4 的一个 piece-specific publish 结果作为输入，例如：
  - `signal-02-publish-reuse-result.json`
  - `digest-02-publish-reuse-result.json`
  - `validated-practice-02-publish-reuse-result.json`
2. 先运行 dry-run：

```powershell
node obsidian-kb-local/scripts/sync-article-corpus.mjs --target "<publish-result-path>" --dry-run
```

3. 确认目标路径在 `08-AI知识库` 范围内。
4. dry-run 通过后，实际运行一次。
5. 验证 Vault 中产出的 raw note 契约至少满足：
  - frontmatter 包含 `topic`
  - frontmatter 包含 `source_url`
  - frontmatter 包含 `captured_at` 与 `kb_date`
  - 正文保留 `## Source Map` 段落，而不是把 source mapping 强塞进 frontmatter
6. 分开记录固定文件名兼容状态与 piece-specific 导出状态，不要求人为补 workflow 镜像后再回流。

### Step 2: compile 测试（可选）

如果 provider 配置可用，再运行：

```powershell
node obsidian-kb-local/scripts/sync-article-corpus.mjs --target "<publish-result-path>" --compile
```

如果 provider 不可用，跳过此步并记录原因。

### Step 3: feedback-workflow 仅按需验证

- 默认不执行。
- 只有当要写“某人如何把 frontier 输入转成工作流”的方法论 / 流程复盘稿时，才构建最小请求并验证：
  - 能否清楚分离直接引语 / 总结 / 推断
  - 能否产出可用的 workflow table
- 如果未触发该稿型，只在复盘文档中记录“本轮未使用”。

### Step 4: 试点复盘文档

在 `.tmp\karpathy-second-brain-article\` 下创建 `pilot-checkpoint-w1w2.md`：

```markdown
# 试点复盘 — Week 1-2

## 链路验证状态

| 环节 | 状态 | 备注 |
|------|------|------|
| x-index (CDP) | pass / degraded / fail | |
| x-index (manual) | pass / n/a | |
| article-workflow | pass / fail | |
| article-publish | pass / fail | |
| piece-specific export | pass / fail | |
| wechat-push-draft | untested (人工审核后) | |
| sync-article-corpus | pass / fail | |
| feedback-workflow | untested / available / limited | |

## 产出统计

| 稿型 | 目标 | 实际 | 缺口原因 |
|------|------|------|---------|
| Signal | 1 | | |
| Validated Practice | 1 | | |
| Digest | 0-1 | | |

## 要坚持的规则

1. <从实践中确认有价值的规则>

## 要修改/删减的规则

1. <从实践中发现不可行或过度的规则>
```

### Step 5: 回归测试

优先运行：

```powershell
node obsidian-kb-local/tests/article-corpus.test.mjs
```

如本机 `node --test` 环境稳定，也可以运行：

```powershell
node --test obsidian-kb-local/tests/article-corpus.test.mjs
```

如需要补充更大回归，可再运行：

```powershell
node obsidian-kb-local/tests/run-tests.mjs
```

## Acceptance Criteria

- `sync-article-corpus` 成功将至少 1 篇文章回流到 Vault。
- 回流产出位于 `08-AI知识库` 边界内。
- raw note frontmatter 包含 `topic`、`source_url`、`captured_at`、`kb_date`，且正文保留 `## Source Map`。
- piece-specific workflow 导出状态与固定文件名兼容状态被分开记录。
- 复盘文档完成，且至少识别 1 条要坚持的规则和 1 条要修改的规则。

## Constraints

- 不推送到 WeChat。
- `feedback-workflow` 不作为默认步骤。
