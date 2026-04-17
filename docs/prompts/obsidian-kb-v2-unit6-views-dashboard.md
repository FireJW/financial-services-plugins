# Codex Prompt — Unit 6: Dataview Views and Dashboard

> **Depends on**: Unit 3 (Bootstrap Namespace) must be complete. Unit 5 (Compile Pipeline) recommended but not required.

## Context

You are working in the `obsidian-kb-local` companion repo at:
```
C:\Users\rickylu\.gemini\antigravity\scratch\financial-services-plugins\obsidian-kb-local\
```

The Vault is at `D:\OneDrive - zn\文档\Obsidian Vault`, config.machineRoot = `08-AI知识库`.

The current dashboard (`30-views/00-KB Dashboard.md`) was created by `bootstrap-plan.mjs` with basic Dataview queries using `captured_at` and `compiled_at` for sorting. The v2 plan adds:
- `kb_date` field (Dataview-native `YYYY-MM-DD` format) for reliable date comparisons
- Three additional view notes: Stale Notes, Open Questions, Sources by Topic
- All date comparisons should use `kb_date` instead of string-formatted `captured_at`/`compiled_at`

## Task

### Part A — Update dashboard in bootstrap-plan.mjs

**Modify** the `dashboard()` function in `obsidian-kb-local/src/bootstrap-plan.mjs` to use `kb_date` for sorting and add richer queries:

```js
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
```

### Part B — Create additional view notes

These notes should be added to the `notes` array in `buildBootstrapPlan()`:

**Add** to the notes array in `bootstrap-plan.mjs`:

```js
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
}
```

**Add** the corresponding functions:

```js
function staleNotesView(root) {
  return `# Stale Notes

Wiki notes that haven't been updated in 30+ days.

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

Wiki notes still in draft state, awaiting human review.

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
```

### Part C — Update KB Home links

**Modify** the `kbHome()` function in `bootstrap-plan.mjs` to add links to the new views:

Add these links to the `## Links` section:
```markdown
- [[08-AI知识库/30-views/01-Stale Notes|Stale Notes]]
- [[08-AI知识库/30-views/02-Open Questions|Open Questions]]
- [[08-AI知识库/30-views/03-Sources by Topic|Sources by Topic]]
```

## Acceptance Criteria

1. Dashboard uses `kb_date` for sorting (not `captured_at`/`compiled_at`)
2. Dashboard includes a stats summary query
3. `01-Stale Notes.md` created with 30-day stale threshold for wiki, 14-day for raw
4. `02-Open Questions.md` created with draft review_state filter
5. `03-Sources by Topic.md` created with GROUP BY topic queries
6. All Dataview queries use `kb_date` for date comparisons (Dataview parses this natively)
7. KB Home links updated to include new views
8. `cmd /c "cd obsidian-kb-local && node tests/run-tests.mjs"` passes

## Safety Constraints

- These are Obsidian view notes (read-only Dataview queries) — no data mutation
- All notes are within `08-AI知识库/30-views/` — boundary safe
- Do NOT modify existing notes in `10-raw/` or `20-wiki/`
