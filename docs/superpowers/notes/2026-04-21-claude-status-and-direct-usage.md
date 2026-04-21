# Claude Status and Direct Usage

Date: `2026-04-21`
Repo: `D:\Users\rickylu\dev\financial-services-plugins`

## 1. Current Status

- Observed branch: `main`
- Observed upstream state: `main...origin/main [ahead 27]`
- Observed HEAD: `eb0c954 Merge pull request #25 from FireJW/feat/live-snapshot-hardening-round3`
- Observed worktree state: not clean
  - modified:
    - `CLAUDE.md`
  - untracked:
    - `docs/superpowers/notes/2026-04-21-claude-status-and-direct-usage.md`

Historical notes from `2026-04-16` describe this repo as having `.git` damage.
In this session, `git status` and `git log` both worked normally, so the
practical current read is:

- git is currently usable
- local `main` carries unpublished local history
- do not blindly `pull`, `reset`, or rewrite history without checking intent

## 2. What This Repo Is Best For Right Now

Use this repo first when the task is primarily about:

- live hot-topic discovery
- news indexing and refresh
- X / Twitter evidence capture
- article workflow orchestration
- article draft / revise / publish pipeline
- WeChat or Toutiao publication-adjacent workflows
- feedback-to-iteration reconstruction

This repo currently looks like the fresher mainline for the `autoresearch` /
content-pipeline surface.

## 3. Current Active Workstream

The most recent visible work in this repo is centered on live snapshot
hardening and topic discovery quality:

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
- `docs/superpowers/plans/2026-04-21-live-snapshot-hardening-round3-implementation-plan.md`
- `docs/superpowers/plans/2026-04-21-setup-launch-phase2-implementation.md`
- `docs/superpowers/plans/2026-04-21-setup-launch-phase2-quality-upgrade-implementation.md`

If the user asks for shortlist cache-first execution-closure work, prefer the
sister repo `D:\Users\rickylu\dev\financial-services-plugins-clean`, which is
currently carrying that feature branch directly.

## 4. Direct Invocation Map

Start from `routing-index.md` before improvising a workflow.

For direct invocation, prefer these native entrypoints:

### Hot topic discovery

- Command doc:
  `financial-analysis/commands/hot-topics.md`
- Local helper:
  `financial-analysis\skills\autoresearch-info-index\scripts\run_hot_topic_discovery.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Use this when the user asks:

- `现在值得写什么`
- `今天有什么能做成公众号文章的热点`
- `先给我排个热点优先级`

### News indexing

- Command doc:
  `financial-analysis/commands/news-index.md`
- Local helper:
  `financial-analysis\skills\autoresearch-info-index\scripts\run_news_index.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Use this when the user wants a reusable news evidence pack before drafting.

### News refresh

- Command doc:
  `financial-analysis/commands/news-refresh.md`
- Local helper:
  `financial-analysis\skills\autoresearch-info-index\scripts\run_news_refresh.cmd "<existing-result.json>" "<refresh-request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Use this when a prior news result exists and the user wants it refreshed rather
than recollected from scratch.

### X / Twitter evidence capture

- Command doc:
  `financial-analysis/commands/x-index.md`
- Local helper:
  `financial-analysis\skills\autoresearch-info-index\scripts\run_x_index.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`
- Native Python entrypoint:
  `financial-analysis\skills\autoresearch-info-index\scripts\x_index.py`

Use this when the user wants thread evidence, timestamps, normalized post
records, or downstream article-ready X evidence.

### Article workflow

- Command doc:
  `financial-analysis/commands/article-workflow.md`
- Local helper:
  `financial-analysis\skills\autoresearch-info-index\scripts\run_article_workflow.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>] [--draft-mode balanced|image_first|image_only]`

Use this when the user wants the end-to-end content pipeline instead of
manually chaining discovery, draft, and publish steps.

### Article draft

- Command doc:
  `financial-analysis/commands/article-draft.md`
- Local helper:
  `financial-analysis\skills\autoresearch-info-index\scripts\run_article_draft.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>] [--draft-mode balanced|image_first|image_only]`

Use this when topic/evidence already exists and the user only wants draft
generation.

### Article publish

- Command doc:
  `financial-analysis/commands/article-publish.md`
- Local helper:
  `financial-analysis\skills\autoresearch-info-index\scripts\run_article_publish.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Use this when the user wants the publish/readiness layer, not just the draft.

### Feedback workflow reconstruction

- Command doc:
  `financial-analysis/commands/feedback-workflow.md`
- Native skill:
  `financial-analysis/skills/feedback-iteration-workflow/SKILL.md`

Use this when the user wants interviews, podcasts, feedback logs, or social
evidence turned into a workflow, cadence, or priorities loop.

## 5. Guardrails for Claude

- Prefer explicit command docs and their linked helpers over the malformed
  `financial-analysis/commands/autoresearch.md` in the current working copy.
- For X collection on Windows, prefer `remote_debugging` before `cookie_file`,
  matching repo `CLAUDE.md`.
- Do not improvise public scraping first when a native signed-session route
  exists.
- Because local `main` is ahead by 27 commits, do not treat this repo as a
  trivial mirror of `origin/main`.

## 6. Minimum Startup Pack for Claude

Before touching code in this repo, open:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `routing-index.md`
4. this note
5. the latest live-snapshot / setup-launch plans if the task touches topic
   discovery or article quality
