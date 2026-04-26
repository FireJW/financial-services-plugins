# Handoff: article-publish-topic-1-shallow-new-session

## Goal

Help Claude take over the current `financial-analysis` article draft for topic 1
and answer two questions:

1. why a new session generated a much shallower article than the current thread
2. what the best next handling is from here: continue manual polish, regenerate
   from workflow with stronger constraints, or improve the durable handoff path

## Current State

- Status: topic selected, draft manually upgraded, local cover prepared, package
  is structurally ready for WeChat API push
- Scope boundary: focus on the topic-1 article artifacts under
  `financial-analysis\.tmp\article-publish-2026-04-22-topic-1`; do not absorb
  unrelated dirty repo changes into this task
- Local checkpoint note: the readable article source of truth is the standalone
  Markdown draft, not the stale embedded regression metadata in the JSON package

## Managed Snapshot

<!-- codex:handoff-meta:start -->
- Last updated: 2026-04-22 Asia/Shanghai
- Branch: main
- Working directory: D:\Users\rickylu\dev\financial-services-plugins
<!-- codex:handoff-meta:end -->

## Files In Play

- changed:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\final-review-draft.md`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\publish-package.json`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\workflow\final-article-result.json`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1-result.json`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\wechat-draft.html`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\cover-hormuz-consumer-v2.png`
- reviewed:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\hot-topics-2026-04-22-request.json`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\hot-topics-2026-04-22-result.json`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\publish-regression-check.json`
  - `C:\Users\rickylu\.codex\config.toml`
  - `C:\Users\rickylu\.codex\memories\MEMORY.md`
  - `C:\Users\rickylu\.codex\sessions\2026\04\15\rollout-2026-04-15T18-24-42-019d90ab-f6a6-7202-9265-b453c791cb68.jsonl`
- still pending:
  - decide whether the current article is good enough to keep polishing manually
  - decide whether the workflow should be rerun with stronger editorial constraints
  - decide what durable handoff/state file should accompany future article work so
    new sessions do not regress into shallow drafts

## Verification Already Run

- command:
  `python financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery.py financial-analysis\.tmp\hot-topics-2026-04-22-request.json --output financial-analysis\.tmp\hot-topics-2026-04-22-result.json --markdown-output financial-analysis\.tmp\hot-topics-2026-04-22-report.md --quiet`
  result:
  topic 1 selected as `霍尔木兹冲击传导到消费端：油价与通胀压力重新抬头`
- command:
  `python financial-analysis\skills\autoresearch-info-index\scripts\article_publish.py financial-analysis\.tmp\hot-topics-2026-04-22-request.json --selected-topic-index 1 --output-dir financial-analysis\.tmp\article-publish-2026-04-22-topic-1 --output financial-analysis\.tmp\article-publish-2026-04-22-topic-1-result.json --markdown-output financial-analysis\.tmp\article-publish-2026-04-22-topic-1-report.md --quiet`
  result:
  article package created successfully
- command:
  same `article_publish.py` invocation with explicit `--cover-image-path`
  pointing at `cover-hormuz-consumer-v2.png`
  result:
  package remained `ready_for_api_push`
- command:
  `python financial-analysis\skills\autoresearch-info-index\scripts\article_publish_regression_check.py financial-analysis\.tmp\article-publish-2026-04-22-topic-1 --output financial-analysis\.tmp\article-publish-2026-04-22-topic-1\publish-regression-check.json --markdown-output financial-analysis\.tmp\article-publish-2026-04-22-topic-1\publish-regression-check.md --quiet`
  result:
  `changes_recommended`, but this is reading stale embedded `regression_checks`
  from the auto-generated package snapshot, not the current manually polished
  article text

## Decisions

- decision:
  keep WeChat API as the main path and do not use the browser-session helper by
  default
  reason:
  the user explicitly said the real backend route is the API path; browser
  helper work was fallback-only
- decision:
  make `article_publish_runtime.normalize_request()` default to `push_backend =
  "api"` instead of `"auto"`
  reason:
  new article runs should not silently slide into browser-session fallback just
  because browser-session config exists
- decision:
  create a human-readable standalone draft file
  reason:
  PowerShell previews of UTF-8 JSON were rendering Chinese as `?` in some local
  checks; `final-review-draft.md` is the cleanest readable source
- decision:
  user-facing draft focus shifted from abstract market commentary to a sharper
  chain: oil price shock -> gas station sales -> consumer budget squeeze ->
  inflation expectations -> asset pricing
  reason:
  the earlier drafts felt shallow and generic

## Why The New Session Went Shallow

- Codex memory is currently enabled in local config: `memories = true`
- The current article-specific context was not yet represented in
  `C:\Users\rickylu\.codex\memories\MEMORY.md`
- The thread id the user referenced, `019d90ab-f6a6-7202-9265-b453c791cb68`,
  maps to a much older `2026-04-15` recovery session, not this article thread
- So the new session did not actually recover this thread's editorial decisions:
  topic choice, anti-helper instruction, rejected titles, cover iterations, and
  the repeated complaint that generic business-talk phrasing was unacceptable
- Net effect: the new session saw only a file path and sparse global memory, not
  the full thread-local editorial context, so it drifted back to generic output

## Risks / Open Questions

- The article text is materially newer than the embedded `regression_checks`,
  `automatic_acceptance`, and parts of `report_markdown`; there is metadata drift
- `final-review-draft.md` and `publish-package.json` are the most useful current
  sources; some older status/report fields still mention prior titles or older
  regression conclusions
- It is still unresolved whether the best fix is:
  - continue manual polish from current draft
  - rerun the article workflow from an earlier stage with stronger editorial
    constraints
  - add an article-specific durable handoff file or state file so later sessions
    stop losing the thread

## What Claude Should Evaluate

1. Read the current full draft and judge whether the article is now structurally
   strong enough to keep polishing manually, or whether it should be regenerated
   from the workflow with a better brief
2. Explain whether the current title is the right level of directness for a
   Chinese公众号 article, or whether a better final title exists
3. Decide how to eliminate the metadata drift cleanly:
   regenerate package/report artifacts, or formalize the current manual draft as
   the new source of truth
4. Propose the minimum durable handoff mechanism for future article work so a new
   session can recover the article's real editorial context instead of producing
   a shallow draft

## Suggested Working Assumptions For Claude

- Do not spend time re-debugging browser-session push unless the user explicitly
  asks again
- Treat the API push path as the intended destination
- Treat `final-review-draft.md` as the best readable current article
- Treat stale embedded regression metadata as a workflow artifact problem, not as
  definitive evidence that the current article text is still weak

## Next Steps

1. Read `final-review-draft.md`, `publish-package.json`, and
   `publish-regression-check.md`
2. Decide whether to keep polishing the current article or regenerate from the
   workflow with stronger editorial constraints
3. Recommend one durable handoff/state pattern that fixes the shallow-new-session
   problem for future article threads

## Git Snapshot

<!-- codex:handoff-git-status:start -->
```text
## main...origin/main [ahead 1]
 M CLAUDE.md
 M financial-analysis/skills/autoresearch-info-index/scripts/article_publish_runtime.py
 M financial-analysis/skills/autoresearch-info-index/scripts/wechat_browser_session_push.js
 M financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
 M routing-index.md
?? financial-analysis/skills/autoresearch-info-index/tests/test_wechat_browser_session_push.py
?? scripts/codex-native-routing-init.ps1
```
<!-- codex:handoff-git-status:end -->

## Resume Commands

```powershell
Set-Location 'D:\Users\rickylu\dev\financial-services-plugins'
git status --short --branch
Get-Content 'D:\Users\rickylu\dev\financial-services-plugins\.claude\handoff\claude-article-publish-handoff-2026-04-22-topic-1.md'
Get-Content 'D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\final-review-draft.md'
Get-Content 'D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\publish-regression-check.md'
```

## Suggested Prompt To Start Claude

```text
Work in D:\Users\rickylu\dev\financial-services-plugins.

Read these files first:
1. .claude/handoff/claude-article-publish-handoff-2026-04-22-topic-1.md
2. financial-analysis/.tmp/article-publish-2026-04-22-topic-1/final-review-draft.md
3. financial-analysis/.tmp/article-publish-2026-04-22-topic-1/publish-package.json
4. financial-analysis/.tmp/article-publish-2026-04-22-topic-1/publish-regression-check.md

Then answer:
- why did a new Codex session produce a much shallower draft
- is the current article better handled by further manual polish or by rerunning the workflow with a stronger brief
- what is the best durable handoff/state mechanism so later sessions stop losing editorial context

Assume WeChat API push is the preferred path.
Do not default back to browser-session helper work.
Treat stale embedded regression metadata as potentially out of date relative to the current manual draft.
```

## References

- related docs:
  - `D:\Users\rickylu\dev\financial-services-plugins\.claude\handoff\README.md`
  - `D:\Users\rickylu\dev\financial-services-plugins\docs\superpowers\notes\2026-04-21-claude-development-handoff.md`
- article artifacts:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\final-review-draft.md`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\publish-package.json`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\.tmp\article-publish-2026-04-22-topic-1\cover-hormuz-consumer-v2.png`
