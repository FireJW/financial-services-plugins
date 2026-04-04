import { formatIso8601Tz } from "./frontmatter.mjs";

export function buildBootstrapPlan(config) {
  const root = config.machineRoot;
  const now = formatIso8601Tz(new Date());
  const today = now.slice(0, 10);

  const directories = [
    root,
    `${root}/00-控制台`,
    `${root}/00-控制台/Pilot Topics`,
    `${root}/00-控制台/Runbooks`,
    `${root}/10-raw`,
    `${root}/10-raw/web`,
    `${root}/10-raw/manual`,
    `${root}/10-raw/repos`,
    `${root}/10-raw/papers`,
    `${root}/20-wiki`,
    `${root}/20-wiki/concepts`,
    `${root}/20-wiki/entities`,
    `${root}/20-wiki/sources`,
    `${root}/20-wiki/syntheses`,
    `${root}/30-views`,
    `${root}/90-ops`,
    `${root}/90-ops/contracts`,
    `${root}/90-ops/logs`,
    `${root}/90-ops/manifests`,
    `${root}/90-ops/migration`,
    `${root}/90-ops/prompts`
  ];

  const notes = [
    {
      path: `${root}/00-控制台/KB Home.md`,
      content: kbHome(config)
    },
    {
      path: `${root}/00-控制台/Runbooks/Codex-Obsidian CLI 使用说明.md`,
      content: usageRunbook(config)
    },
    {
      path: `${root}/00-控制台/Pilot Topics/Karpathy LLM Knowledge Bases.md`,
      content: pilotTopic(now, today)
    },
    {
      path: `${root}/10-raw/README.md`,
      content: rawReadme()
    },
    {
      path: `${root}/20-wiki/README.md`,
      content: wikiReadme()
    },
    {
      path: `${root}/30-views/00-KB Dashboard.md`,
      content: dashboard(root)
    },
    {
      path: `${root}/30-views/01-Stale Notes.md`,
      content: staleNotesView(root)
    },
    {
      path: `${root}/30-views/02-Open Questions.md`,
      content: openQuestionsView(root)
    },
    {
      path: `${root}/30-views/03-Sources by Topic.md`,
      content: sourcesByTopicView(root)
    },
    {
      path: `${root}/90-ops/contracts/raw-note.md`,
      content: rawContract()
    },
    {
      path: `${root}/90-ops/contracts/wiki-note.md`,
      content: wikiContract()
    },
    {
      path: `${root}/90-ops/manifests/topic-registry.md`,
      content: topicRegistry(now)
    }
  ];

  return { directories, notes };
}

function kbHome(config) {
  return `# KB Home

## Purpose

这个区域是机器优先写入区，用于承载 Karpathy 风格的本地知识库流程。

## Write Boundary

- Vault: \`${config.vaultName}\`
- Machine root: \`${config.machineRoot}\`
- 默认不改动 \`00-07\` 目录

## Core Flow

1. 原始资料进入 \`10-raw\`
2. Codex 通过 Obsidian CLI 编译到 \`20-wiki\`
3. 通过 \`30-views\` 做检索、巡检和回看

## Common Commands

\`\`\`powershell
cmd /c npm run doctor
cmd /c npm run bootstrap-vault
cmd /c npm run write-smoke
cmd /c npm run obsidian -- search query="Karpathy"
\`\`\`

## Rollback Procedure

如果需要回滚机器生成的内容：

1. 运行 \`cmd /c "cd obsidian-kb-local && node scripts/rollback.mjs --dry-run"\` 查看会删除哪些文件
2. 确认后运行 \`cmd /c "cd obsidian-kb-local && node scripts/rollback.mjs --execute"\`
3. rollback 只删除 \`managed_by: codex\` 的文件，不碰 \`managed_by: human\`
4. rollback 不会改动 \`${config.machineRoot}\` 之外的任何文件

## Links

- [[${config.machineRoot}/10-raw/README|10-raw 说明]]
- [[${config.machineRoot}/20-wiki/README|20-wiki 说明]]
- [[${config.machineRoot}/30-views/00-KB Dashboard|KB Dashboard]]
- [[${config.machineRoot}/30-views/01-Stale Notes|Stale Notes]]
- [[${config.machineRoot}/30-views/02-Open Questions|Open Questions]]
- [[${config.machineRoot}/30-views/03-Sources by Topic|Sources by Topic]]
- [[${config.machineRoot}/90-ops/contracts/raw-note|raw contract]]
- [[${config.machineRoot}/90-ops/contracts/wiki-note|wiki contract]]
`;
}

function usageRunbook(config) {
  return `# Codex-Obsidian CLI 使用说明

## Boundaries

- Vault path: \`${config.vaultPath}\`
- Vault name: \`${config.vaultName}\`
- Machine root: \`${config.machineRoot}\`

## Preferred Call Pattern

优先通过 companion repo 里的封装脚本调用 CLI：

\`\`\`powershell
cmd /c npm run obsidian -- help
cmd /c npm run obsidian -- read path="${config.machineRoot}/00-控制台/KB Home.md"
cmd /c npm run obsidian -- search query="知识库"
\`\`\`

## When To Use Raw CLI

只有在封装脚本缺少你要的功能时，才直接写底层 \`obsidian\` 命令。

## Safety Rules

- 默认只写 \`${config.machineRoot}\`
- 先读后写
- 大范围改写前先跑 smoke
`;
}

function pilotTopic(now, today) {
  return `---
kb_type: wiki
wiki_kind: synthesis
topic: "Karpathy LLM Knowledge Bases"
compiled_from: []
compiled_at: "${now}"
kb_date: "${today}"
review_state: "draft"
managed_by: "codex"
kb_source_count: 0
dedup_key: "karpathy llm knowledge bases::synthesis::"
---

# Karpathy LLM Knowledge Bases

## Objective

把 Karpathy 提到的 raw -> compiled wiki -> Obsidian frontend -> CLI 操作这一套方法，落到本地 Obsidian Vault。

## Current Questions

- raw 入库的最小标准是什么？
- concept/entity/source/synthesis 四类 wiki 页是否足够？
- 哪些内容应该回写旧目录，哪些应该只留在 \`08-AI知识库\`？
`;
}

function rawReadme() {
  return `# 10-raw

这里存放未经编译的原始资料。

## Lanes

- \`web\`: Web Clipper 或网页文章
- \`manual\`: 手工摘录、访谈记录、想法草稿
- \`repos\`: 仓库摘要与 manifest
- \`papers\`: 论文元信息与摘要

## Rule

raw 层保留原始上下文，不在这里写最终结论。`;
}

function wikiReadme() {
  return `# 20-wiki

这里存放由 Codex 通过 CLI 编译出来的结构化 wiki。

## Kinds

- \`concepts\`
- \`entities\`
- \`sources\`
- \`syntheses\`

## Rule

- 所有 wiki note 必须有来源追踪
- 尽量做增量更新，不制造重复 note
`;
}

function dashboard(root) {
  return `# KB Dashboard

## Stats

\`\`\`dataview
TABLE WITHOUT ID
  length(filter(rows, (r) => r.kb_type = "raw")) AS "Raw",
  length(filter(rows, (r) => r.kb_type = "wiki")) AS "Wiki",
  length(filter(rows, (r) => r.status = "queued")) AS "Queued",
  length(filter(rows, (r) => r.review_state = "draft")) AS "Drafts"
FROM "${root}"
WHERE kb_type
FLATTEN "all" AS group
GROUP BY group
\`\`\`

## Recent Raw

\`\`\`dataview
TABLE source_type, topic, status, kb_date
FROM "${root}/10-raw"
WHERE kb_type = "raw"
SORT kb_date DESC
LIMIT 20
\`\`\`

## Recent Wiki

\`\`\`dataview
TABLE wiki_kind, topic, review_state, kb_date, kb_source_count
FROM "${root}/20-wiki"
WHERE kb_type = "wiki"
SORT kb_date DESC
LIMIT 20
\`\`\`

## Queued for Compilation

\`\`\`dataview
TABLE source_type, topic, kb_date
FROM "${root}/10-raw"
WHERE status = "queued"
SORT kb_date ASC
\`\`\`

## Open Drafts

\`\`\`dataview
TABLE wiki_kind, topic, kb_date
FROM "${root}/20-wiki"
WHERE review_state = "draft"
SORT kb_date DESC
\`\`\`
`;
}

function staleNotesView(root) {
  return `# Stale Notes

Wiki notes that have not been updated in 30+ days.

\`\`\`dataview
TABLE wiki_kind, topic, kb_date, review_state
FROM "${root}/20-wiki"
WHERE kb_type = "wiki" AND kb_date < date(today) - dur(30 days)
SORT kb_date ASC
\`\`\`

## Stale Raw (Queued > 14 days)

\`\`\`dataview
TABLE source_type, topic, kb_date
FROM "${root}/10-raw"
WHERE status = "queued" AND kb_date < date(today) - dur(14 days)
SORT kb_date ASC
\`\`\`
`;
}

function openQuestionsView(root) {
  return `# Open Questions

Wiki notes still in draft state and awaiting human review.

\`\`\`dataview
TABLE wiki_kind, topic, kb_date, kb_source_count
FROM "${root}/20-wiki"
WHERE review_state = "draft" AND kb_type = "wiki"
SORT kb_date DESC
\`\`\`
`;
}

function sourcesByTopicView(root) {
  return `# Sources by Topic

All raw sources grouped by topic.

\`\`\`dataview
TABLE rows.source_type AS "Types", length(rows) AS "Count", min(rows.kb_date) AS "Earliest", max(rows.kb_date) AS "Latest"
FROM "${root}/10-raw"
WHERE kb_type = "raw"
GROUP BY topic
SORT length(rows) DESC
\`\`\`

## Wiki Coverage by Topic

\`\`\`dataview
TABLE rows.wiki_kind AS "Kinds", length(rows) AS "Count", sum(rows.kb_source_count) AS "Total Sources"
FROM "${root}/20-wiki"
WHERE kb_type = "wiki"
GROUP BY topic
SORT length(rows) DESC
\`\`\`
`;
}

function rawContract() {
  return `# Raw Note Contract

## Purpose

给原始资料统一元数据，方便后续编译和追踪。

## Frontmatter Example

\`\`\`yaml
kb_type: raw
source_type: web_article | paper | repo | manual
topic: ""
source_url: ""
captured_at: ""
kb_date: ""
status: queued | compiled | archived | error
managed_by: human
\`\`\`
`;
}

function wikiContract() {
  return `# Wiki Note Contract

## Purpose

给编译后的知识页统一元数据，保证可重编译、可追踪、可审阅。

## Frontmatter Example

\`\`\`yaml
kb_type: wiki
wiki_kind: concept | entity | source | synthesis
topic: ""
compiled_from: []
compiled_at: ""
kb_date: ""
review_state: draft | reviewed
managed_by: codex
kb_source_count: 0
dedup_key: ""
\`\`\`
`;
}

function topicRegistry(now) {
  return `# Topic Registry

Updated: ${now}

| Topic | Status | Primary lane | Notes |
|---|---|---|---|
| Karpathy LLM Knowledge Bases | pilot | web/manual | first bounded pilot |
`;
}
