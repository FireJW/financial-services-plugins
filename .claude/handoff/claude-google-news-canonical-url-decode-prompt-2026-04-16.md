You are taking over a **single-purpose recovery task** in:

- `D:\Users\rickylu\dev\financial-services-plugins`

Your job is **not** to keep polishing the article pipeline broadly.
Your job is to complete one narrowly scoped task:

`Make the live Google News probe produce source_items[].url values that do not start with news.google.com.`

## Primary Goal

The only success condition that matters is:

- In the live probe output,
  - `source_items[].url`
  - must no longer start with `https://news.google.com`

## Why This Task Exists

The broader article pipeline is already in decent shape:

- manual revised article preservation works
- auto image selection works
- auto cover selection works
- digest / H1 rendering is fixed
- Google News auto-discovery titles / source names / summaries are cleaner than before

However, one hard external-integration problem remains:

- Google News RSS wrapper URLs are still not resolving to real publisher canonical URLs

So the system is usable, but not fully restored at the data-quality level.

## Current Best Status

### Already Working

1. Article pipeline output is usable.
   - current good package:
     - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\article-real-run-2026-04-16-v2-live-sourceopt3-revised-v2\stages\publish-package.json`
   - current readiness audit:
     - `D:\Users\rickylu\dev\financial-services-plugins\.tmp\article-real-run-2026-04-16-v2-live-sourceopt3-revised-v2\wechat-push-readiness-report.md`

2. Auto images still work even with Google wrapper URLs.
   - This must not regress.

3. Google News auto-discovery display quality has improved.
   - titles are cleaner
   - `source_name` can now become a media label such as `C114通信网`
   - summaries are cleaner
   - topic `domains` can now use a publisher-domain hint instead of only `news.google.com`

### Still Broken

The live probe still emits wrapper URLs.

Current evidence:

- `D:\Users\rickylu\dev\financial-services-plugins\.tmp\google-news-resolve-check-2026-04-16-v10\discovery.json`

It already shows:

- clean `title`
- clean `source_name`
- cleaner `summary`
- but `source_items[].url` still equals a `news.google.com/rss/articles/...` wrapper URL

## Critical Constraints

### Do Not Re-expand Scope

Do **not** spend time on:

- article wording
- publish-package formatting
- WeChat credentials
- human review gates
- X / Reddit / OpenCLI improvements
- more generic “pipeline cleanup”

### Do Not Break What Already Works

These must remain true after your changes:

1. Google News auto-discovery still produces clean titles/source names/summaries.
2. Auto image selection still works in the real article flow.
3. Auto cover selection does not regress to `manual_required`.

## Files To Read First

### Plan / Task Definition

1. `D:\Users\rickylu\dev\financial-services-docs\docs\superpowers\plans\2026-04-16-google-news-canonical-url-decode-task.md`

### Current Runtime Code

2. `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`

### Current Regression Coverage

3. `financial-analysis/skills/autoresearch-info-index/tests/test_agent_reach_bridge.py`
4. `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

### Current Probe Artifacts

5. `D:\Users\rickylu\dev\financial-services-plugins\.tmp\google-news-resolve-check-2026-04-16-v10\discovery.json`

### Current Best End-to-End Article Output

6. `D:\Users\rickylu\dev\financial-services-plugins\.tmp\article-real-run-2026-04-16-v2-live-sourceopt3-revised-v2\stages\publish-package.json`

## What Has Already Been Tried

The code already includes multiple attempts:

- legacy token decode
- wrapper-page hint extraction
- extraction of `data-n-a-ts` / `data-n-a-sg`
- signed decode round-trip via `batchexecute`
- simpler `batchexecute?rpcids=Fbv4je` fallback
- wrapper HTML preview-image extraction
- title/source-name cleanup for Google News-discovered topics

Tests for those paths are currently green.

But live probe still does not produce canonical URLs.

That means one of these is true:

1. The live Google path has changed again.
2. The request shape / headers / locale / payload for `batchexecute` are still wrong.
3. A different extraction path is needed.
4. The current environment/network behavior makes this path unreliable.

## Allowed Scope

Prefer to keep changes inside:

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- `financial-analysis/skills/autoresearch-info-index/tests/test_agent_reach_bridge.py`

Only expand beyond that if absolutely necessary for this one task.

## Acceptance Criteria

You are done only when **all** of these are true:

1. Live probe:
   - `source_items[].url`
   - does not start with `news.google.com`

2. Live probe still keeps:
   - clean `title`
   - clean `source_name`
   - clean `summary`

3. Real article flow still works:
   - `image_assets` count > 0
   - `cover_plan.selection_mode != manual_required`

4. Relevant tests still pass:
   - `test_agent_reach_bridge.py`
   - `test_article_publish.py`
   - if you touch reuse flow, also `test_article_publish_reuse.py`

## Recommended Execution Order

1. Reproduce the live failure with the smallest possible Google News probe.
2. Instrument / inspect the decode path until you know exactly which branch is failing in live behavior.
3. Make the smallest code change that fixes live canonical URL resolution.
4. Re-run the same minimal live probe.
5. Only after the live probe is fixed, re-run the real article flow to ensure images still work.

## Useful Commands

### A. Minimal Live Probe

```powershell
& 'D:\Users\rickylu\.codex\vendor\python312\python.exe' `
  'D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery.py' `
  --topic '腾讯 混元 3D 世界模型' `
  --sources google-news-search `
  --limit 1 `
  --top-n 1 `
  --output 'D:\Users\rickylu\dev\financial-services-plugins\.tmp\google-news-canonical-task\discovery.json' `
  --quiet
```

### B. Real Article Flow Regression

```powershell
& 'D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\run_article_publish.cmd' `
  'D:\Users\rickylu\dev\financial-services-plugins\.tmp\article-real-run-2026-04-16-v2\article-publish-request.json' `
  --output 'D:\Users\rickylu\dev\financial-services-plugins\.tmp\google-news-canonical-task\article-publish-result.json' `
  --markdown-output 'D:\Users\rickylu\dev\financial-services-plugins\.tmp\google-news-canonical-task\article-publish-report.md' `
  --output-dir 'D:\Users\rickylu\dev\financial-services-plugins\.tmp\google-news-canonical-task\stages' `
  --quiet
```

## What I Want Back

When you report back, keep it short and concrete:

1. `Status`
   - did the live probe canonical URL requirement pass or fail?

2. `What Changed`
   - exact code path touched

3. `Verification`
   - minimal live probe result
   - article-flow regression result
   - tests run

4. `If Still Not Fixed`
   - the single best technical reason it is still failing
   - the single next thing to try

Do not keep polishing adjacent parts of the system if the live probe criterion still fails.
