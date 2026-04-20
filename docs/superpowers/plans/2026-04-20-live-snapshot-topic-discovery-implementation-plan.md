# Live Snapshot Topic Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `discovery_profile=live_snapshot` path that returns faster, more writeable same-day topic candidates without changing the behavior of `default` or `international_first`.

**Architecture:** Extend request normalization with a live-snapshot-specific default pack and runtime caps, then layer a live-specific fit heuristic and topic filter on top of the existing recency/heat-hardened candidate scoring. Keep the feature opt-in and route all coverage through the existing hot topic runtime plus the shared `test_article_publish.py` suite.

**Tech Stack:** Python 3.12, argparse CLI wrapper, `hot_topic_discovery_runtime.py`, pytest via `test_article_publish.py`

---

### Task 1: Add red tests for the new `live_snapshot` profile contract

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
- Reference: `docs/superpowers/specs/2026-04-20-live-snapshot-topic-discovery-design.md`

- [ ] **Step 1: Add live snapshot fixture candidates**

Add new helper fixtures near the existing hot topic candidate helpers:

```python
    def live_snapshot_candidates(self) -> list[dict]:
        return [
            {
                "title": "Hormuz shipping risk jolts oil and equities again",
                "summary": "A same-day conflict and market read-through topic with clear analysis room.",
                "source_items": [
                    {
                        "source_name": "Reuters",
                        "source_type": "major_news",
                        "url": "https://example.com/reuters-hormuz-live-snapshot",
                        "published_at": "2026-04-20T10:00:00+00:00",
                        "summary": "Oil jumps and equities wobble again as Hormuz disruption risk returns to market pricing.",
                    }
                ],
            },
            {
                "title": "看图学习丨实现中国式现代化 总书记强调这一关必须要过",
                "summary": "A same-day official messaging headline without a clear market or industry read-through.",
                "source_items": [
                    {
                        "source_name": "chinanews.com.cn",
                        "source_type": "major_news",
                        "url": "https://example.com/chinanews-live-snapshot",
                        "published_at": "2026-04-20T10:10:00+00:00",
                        "summary": "A same-day official messaging headline without a clear market or industry read-through.",
                    }
                ],
            },
        ]
```

- [ ] **Step 2: Add a failing test for live snapshot default source pack**

Add a test asserting `normalize_request()` keeps existing profiles unchanged and gives `live_snapshot` its own defaults:

```python
    def test_hot_topic_discovery_live_snapshot_uses_dedicated_default_source_pack(self) -> None:
        request = hot_topic_discovery_runtime.normalize_request({"discovery_profile": "live_snapshot"})
        self.assertEqual(request["sources"], ["google-news-world", "36kr"])
        self.assertEqual(request["limit"], 8)
        self.assertEqual(request["top_n"], 5)
        self.assertEqual(request["max_parallel_sources"], 2)
```

- [ ] **Step 3: Add a failing test for live-specific operator fields**

Add a test asserting `live_snapshot_fit` and `live_snapshot_reason` are present on kept topics:

```python
    def test_hot_topic_discovery_live_snapshot_emits_fit_fields(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_candidates(),
            }
        )
        topic = result["ranked_topics"][0]
        self.assertIn("live_snapshot_fit", topic)
        self.assertIn("live_snapshot_reason", topic)
```

- [ ] **Step 4: Add a failing test for live-specific filtering**

Add a test asserting the official-message headline is filtered while the market read-through topic survives:

```python
    def test_hot_topic_discovery_live_snapshot_filters_same_day_official_messaging(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_candidates(),
            }
        )
        ranked_titles = {item["title"] for item in result["ranked_topics"]}
        self.assertIn("Hormuz shipping risk jolts oil and equities again", ranked_titles)
        self.assertNotIn("看图学习丨实现中国式现代化 总书记强调这一关必须要过", ranked_titles)
```

- [ ] **Step 5: Run the focused tests and confirm RED**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot" -v
```

Expected: newly added tests fail because `live_snapshot` behavior and fields do not exist yet.

- [ ] **Step 6: Commit the red tests**

```bash
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "test(autoresearch): add live snapshot topic discovery coverage"
```

### Task 2: Implement `live_snapshot` request normalization and CLI passthrough

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Add live snapshot default constants**

Near the existing discovery-source constants, define:

```python
LIVE_SNAPSHOT_SOURCES = ["google-news-world", "36kr"]
LIVE_SNAPSHOT_DEFAULT_LIMIT = 8
LIVE_SNAPSHOT_DEFAULT_TOP_N = 5
LIVE_SNAPSHOT_DEFAULT_MAX_PARALLEL_SOURCES = 2
```

- [ ] **Step 2: Extend `normalize_request()` with live snapshot defaults**

Update the request builder so `live_snapshot` gets dedicated defaults only when the caller did not explicitly override them:

```python
    is_live_snapshot = discovery_profile == "live_snapshot"
    sources = explicit_sources or (
        list(INTERNATIONAL_PRIMARY_SOURCES + INTERNATIONAL_FALLBACK_SOURCES)
        if discovery_profile == "international_first"
        else (list(LIVE_SNAPSHOT_SOURCES) if is_live_snapshot else list(DEFAULT_DISCOVERY_SOURCES))
    )
```

Then set:

```python
        "limit": max(1, int(raw_payload.get("limit", LIVE_SNAPSHOT_DEFAULT_LIMIT if is_live_snapshot else 10) or 10)),
        "top_n": max(1, int(raw_payload.get("top_n", LIVE_SNAPSHOT_DEFAULT_TOP_N if is_live_snapshot else 5) or 5)),
        "max_parallel_sources": max(
            1,
            int(
                raw_payload.get(
                    "max_parallel_sources",
                    LIVE_SNAPSHOT_DEFAULT_MAX_PARALLEL_SOURCES if is_live_snapshot else min(4, len(sources)),
                )
                or 1
            ),
        ),
```

- [ ] **Step 3: Verify the focused normalization test turns green**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot_uses_dedicated_default_source_pack" -v
```

Expected: PASS

- [ ] **Step 4: Commit the normalization change**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add live snapshot request defaults"
```

### Task 3: Add live snapshot fit heuristics and operator output

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Add live fit helper functions**

Create compact helpers near the recency/heat helpers:

```python
def live_snapshot_fit(candidate: dict[str, Any]) -> str:
    text = candidate_match_text(candidate)
    freshness = clean_text(candidate.get("freshness_bucket"))
    if freshness in {"0-6h", "6-24h"} and contains_any_keyword(
        text,
        {
            "market", "markets", "oil", "equities", "stocks", "guidance", "earnings",
            "capex", "rollout", "policy", "conflict", "supply chain", "订单", "油价", "风险资产",
        },
    ):
        return "high_fit"
    if freshness in {"0-6h", "6-24h"}:
        return "medium_fit"
    return "low_fit"
```

And:

```python
def live_snapshot_reason(candidate: dict[str, Any]) -> str:
    fit = live_snapshot_fit(candidate)
    freshness = clean_text(candidate.get("freshness_bucket"))
    if fit == "high_fit":
        return "This is still a real-time writeable topic because the new signal already changes market or policy expectations."
    if fit == "medium_fit":
        return f"Fresh headline in the {freshness} window, but it still needs a clearer second-order read-through."
    return "Freshness alone is not enough here because the story still reads more like a narrow news flash than an analysis topic."
```

- [ ] **Step 2: Attach the new fields only under `live_snapshot`**

Inside `build_clustered_candidate()` after the existing operator fields:

```python
    if request.get("discovery_profile") == "live_snapshot":
        candidate["live_snapshot_fit"] = live_snapshot_fit(candidate)
        candidate["live_snapshot_reason"] = live_snapshot_reason(candidate)
```

- [ ] **Step 3: Run the fit-field test**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot_emits_fit_fields" -v
```

Expected: PASS

- [ ] **Step 4: Commit the operator-field change**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): emit live snapshot fit metadata"
```

### Task 4: Add live-specific topic filtering

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Add a helper that rejects same-day official messaging**

Create a helper that is intentionally narrow and only applies to `live_snapshot`:

```python
def is_live_snapshot_low_yield_candidate(candidate: dict[str, Any]) -> bool:
    text = candidate_match_text(candidate)
    if contains_any_keyword(
        text,
        {
            "看图学习", "现代化", "总书记", "强调", "会议精神", "宣传", "口径",
            "official commentary", "protocol", "modernization",
        },
    ):
        if not contains_any_keyword(
            text,
            {
                "market", "markets", "oil", "equities", "stocks", "guidance", "earnings",
                "capex", "rollout", "policy", "conflict", "supply chain", "油价", "风险资产",
            },
        ):
            return True
    return False
```

- [ ] **Step 2: Apply it in `apply_topic_controls()`**

Inside the existing control chain, add:

```python
    if request.get("discovery_profile") == "live_snapshot":
        if is_live_snapshot_low_yield_candidate(candidate):
            return False, "filtered low-yield live snapshot topic"
```

- [ ] **Step 3: Run the focused filter test**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot_filters_same_day_official_messaging" -v
```

Expected: PASS

- [ ] **Step 4: Commit the live filter**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): filter low-yield live snapshot topics"
```

### Task 5: Run broader regression and one manual snapshot smoke

**Files:**
- Modify: none
- Verify: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
- Verify manually: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py`

- [ ] **Step 1: Run all live snapshot tests together**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot" -v
```

Expected: all new `live_snapshot` tests pass.

- [ ] **Step 2: Run the full regression file**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -v
```

Expected: full file passes with no regressions to `international_first`.

- [ ] **Step 3: Run one manual smoke on the CLI**

Create a small payload or reuse an inline JSON request that exercises:

```json
{
  "discovery_profile": "live_snapshot",
  "manual_topic_candidates": [
    {
      "title": "Hormuz shipping risk jolts oil and equities again",
      "summary": "A same-day conflict and market read-through topic with clear analysis room.",
      "source_items": [
        {
          "source_name": "Reuters",
          "source_type": "major_news",
          "url": "https://example.com/reuters-hormuz-live-snapshot",
          "published_at": "2026-04-20T10:00:00+00:00",
          "summary": "Oil jumps and equities wobble again as Hormuz disruption risk returns to market pricing."
        }
      ]
    }
  ]
}
```

Run:

```bash
py financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py <request.json> --quiet --output <result.json>
```

Verify the result includes:

- `live_snapshot_fit`
- `live_snapshot_reason`

- [ ] **Step 4: Commit the verification-only state if code changed during debugging**

If no code changed, skip commit. If any small fix was needed during verification:

```bash
git add <exact files>
git commit -m "fix(autoresearch): tighten live snapshot topic discovery"
```

### Task 6: Final branch verification snapshot

**Files:**
- Modify: none

- [ ] **Step 1: Record the final branch status**

Run:

```bash
git status --short --branch
git log --oneline -5
```

Expected:

- clean branch
- task commits present in order

- [ ] **Step 2: Prepare for review**

At completion, summarize:

- which commits belong to the feature
- exact pytest commands run
- whether the CLI smoke emitted `live_snapshot_fit` and `live_snapshot_reason`
