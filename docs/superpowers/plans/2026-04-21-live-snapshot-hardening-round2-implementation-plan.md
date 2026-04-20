# Live Snapshot Hardening Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten `live_snapshot` so real company/market read-through topics rise to `high_fit`, generic political observation topics fall out of the shortlist, and each source's runtime cost is visible in the result.

**Architecture:** Keep `live_snapshot` opt-in and layer three narrow changes onto the current runtime: strengthen fit classification around real financial and market read-through signals, expand low-yield political/newsy filtering without banning conflict topics that already have market transmission, and add lightweight source timing diagnostics to the result and markdown report.

**Tech Stack:** Python 3.12, `hot_topic_discovery_runtime.py`, pytest via `test_article_publish.py`

---

### Task 1: Add RED tests for round-2 live snapshot hardening

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
- Reference: `docs/superpowers/specs/2026-04-21-live-snapshot-hardening-round2-design.md`

- [ ] **Step 1: Add round-2 live snapshot fixtures**

Add focused helper candidates near the existing `live_snapshot_candidates()` helper:

```python
    def live_snapshot_round2_candidates(self) -> list[dict]:
        return [
            {
                "title": "ByteDance says AI spending drove profit sharply lower",
                "summary": "A same-day company result with clear revenue, profit, and AI capex read-through.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/bytedance-live-round2",
                        "published_at": "2026-04-20T10:05:00+00:00",
                        "summary": "ByteDance says revenue mix improved, but AI investment sharply reduced profit.",
                    }
                ],
            },
            {
                "title": "International observation says US-Iran talks remain uncertain",
                "summary": "A same-day political observation headline without oil, shipping, equities, or other market transmission.",
                "source_items": [
                    {
                        "source_name": "google-news-world",
                        "source_type": "major_news",
                        "url": "https://example.com/us-iran-observation-round2",
                        "published_at": "2026-04-20T10:08:00+00:00",
                        "summary": "A same-day political observation headline without oil, shipping, equities, or other market transmission.",
                    }
                ],
            },
            {
                "title": "Hormuz shipping risk jolts oil and equities again",
                "summary": "A same-day conflict topic already transmitting into market pricing.",
                "source_items": [
                    {
                        "source_name": "Reuters",
                        "source_type": "major_news",
                        "url": "https://example.com/hormuz-round2",
                        "published_at": "2026-04-20T10:00:00+00:00",
                        "summary": "Oil jumps and equities wobble again as Hormuz shipping risk returns to market pricing.",
                    }
                ],
            },
        ]
```

- [ ] **Step 2: Add a failing test that company/financial read-through upgrades to `high_fit`**

```python
    def test_hot_topic_discovery_live_snapshot_promotes_company_financial_readthrough_to_high_fit(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        bytedance = next(item for item in result["ranked_topics"] if item["title"] == "ByteDance says AI spending drove profit sharply lower")
        self.assertEqual(bytedance["live_snapshot_fit"], "high_fit")
```

- [ ] **Step 3: Add a failing test that generic political observation gets filtered or forced low**

```python
    def test_hot_topic_discovery_live_snapshot_filters_generic_political_observation_without_market_readthrough(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        ranked_titles = {item["title"] for item in result["ranked_topics"]}
        self.assertNotIn("International observation says US-Iran talks remain uncertain", ranked_titles)
```

- [ ] **Step 4: Add a failing test that conflict topics with market transmission still survive as `high_fit`**

```python
    def test_hot_topic_discovery_live_snapshot_keeps_conflict_topic_when_market_transmission_is_present(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        topic = next(item for item in result["ranked_topics"] if item["title"] == "Hormuz shipping risk jolts oil and equities again")
        self.assertEqual(topic["live_snapshot_fit"], "high_fit")
```

- [ ] **Step 5: Add a failing test for source timing diagnostics**

```python
    def test_hot_topic_discovery_live_snapshot_emits_source_timings(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        self.assertIn("source_timings", result)
        self.assertGreaterEqual(len(result["source_timings"]), 1)
        self.assertIn("duration_ms", result["source_timings"][0])
        self.assertIn("status", result["source_timings"][0])
```

- [ ] **Step 6: Add a failing test for markdown timing section**

```python
    def test_hot_topic_discovery_report_includes_source_timings_section(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        self.assertIn("## Source Timings", result["report_markdown"])
```

- [ ] **Step 7: Run the focused live-snapshot round-2 tests and confirm RED**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot and (financial_readthrough or political_observation or market_transmission or source_timings or timings_section)" -v
```

Expected: the new round-2 tests fail because the hardening has not been implemented yet.

- [ ] **Step 8: Commit the RED tests**

```bash
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "test(autoresearch): add live snapshot hardening round 2 coverage"
```

### Task 2: Expand `high_fit` signals and tighten `medium_fit`

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Expand the analysis keyword set for real market/company read-through**

Extend the existing `LIVE_SNAPSHOT_ANALYSIS_KEYWORDS` set with the round-2 financial and market terms from the spec:

```python
LIVE_SNAPSHOT_ANALYSIS_KEYWORDS.update(
    {
        "revenue", "profit", "margin", "loss", "sales",
        "guidance", "earnings", "capex", "order", "orders",
        "bond", "yield", "volatility",
        "ceasefire", "strait", "shipping", "sanction", "tariff", "negotiation",
        "营收", "利润", "净利", "亏损", "指引", "财报", "资本开支",
        "股市", "收益率", "波动率", "停火", "海峡", "航运", "制裁", "关税", "谈判",
    }
)
```

- [ ] **Step 2: Tighten `live_snapshot_fit()` so `medium_fit` is no longer the default bucket for every fresh headline**

Keep the current `high_fit` condition, but make `medium_fit` require some business or policy extension instead of any fresh item:

```python
LIVE_SNAPSHOT_EXTENSION_KEYWORDS = {
    "ai", "model", "chip", "chips", "market", "markets", "company", "policy",
    "robotaxi", "supply chain", "energy", "macro", "earnings", "capex",
    "AI", "芯片", "市场", "公司", "政策", "供应链", "能源", "宏观",
}
```

Then:

```python
def live_snapshot_fit(candidate: dict[str, Any]) -> str:
    signal_text = live_snapshot_signal_text(candidate)
    freshness = clean_text(candidate.get("freshness_bucket"))
    if freshness in {"0-6h", "6-24h"} and contains_any_keyword(signal_text, LIVE_SNAPSHOT_ANALYSIS_KEYWORDS):
        return "high_fit"
    if freshness in {"0-6h", "6-24h"} and contains_any_keyword(signal_text, LIVE_SNAPSHOT_EXTENSION_KEYWORDS):
        return "medium_fit"
    return "low_fit"
```

- [ ] **Step 3: Run the focused fit tests**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot and (financial_readthrough or market_transmission)" -v
```

Expected: `ByteDance...` and `Hormuz...` both become `high_fit`.

- [ ] **Step 4: Commit the fit-hardening change**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): harden live snapshot fit classification"
```

### Task 3: Expand low-yield filtering for political/newsy headlines

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Expand the low-yield keyword set to catch generic political observation**

Extend `LIVE_SNAPSHOT_LOW_YIELD_KEYWORDS` with phrases for generic observation framing:

```python
LIVE_SNAPSHOT_LOW_YIELD_KEYWORDS.update(
    {
        "international observation",
        "global change",
        "talks remain uncertain",
        "observation",
        "analysis says",
        "局势走向有几种可能",
        "观察",
        "背后",
        "变局",
        "密集访华",
        "理性、务实回应",
    }
)
```

- [ ] **Step 2: Keep conflict topics that already have market transmission**

Do not change the helper to blanket-filter conflict or negotiation terms. The existing guard:

```python
if contains_any_keyword(text, LIVE_SNAPSHOT_ANALYSIS_KEYWORDS):
    return False
```

must remain in place so `"Hormuz..."` stays eligible.

- [ ] **Step 3: Run the political-observation filter test**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot_filters_generic_political_observation_without_market_readthrough" -v
```

Expected: PASS

- [ ] **Step 4: Commit the filtering change**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): expand live snapshot low-yield filtering"
```

### Task 4: Add source timing diagnostics to runtime and report

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Import monotonic timing support**

At the top of the file, import:

```python
import time
```

- [ ] **Step 2: Capture per-source timings in `run_hot_topic_discovery()`**

Create a local list:

```python
source_timings: list[dict[str, Any]] = []
```

For each source fetch, wrap with monotonic timing:

```python
started = time.perf_counter()
try:
    items = fetch_source_items(source_name, request)
    raw_items.extend(items)
    source_timings.append(
        {
            "source": source_name,
            "duration_ms": int(round((time.perf_counter() - started) * 1000)),
            "status": "ok",
        }
    )
except Exception as exc:
    source_timings.append(
        {
            "source": source_name,
            "duration_ms": int(round((time.perf_counter() - started) * 1000)),
            "status": "error",
        }
    )
    errors.append({"source": source_name, "message": str(exc)})
```

Then include:

```python
"source_timings": source_timings,
```

in the final result object.

- [ ] **Step 3: Add a markdown timing section**

In `build_markdown_report()`, append:

```python
    if result.get("source_timings"):
        lines.extend(["", "## Source Timings"])
        for item in result["source_timings"]:
            lines.append(
                f"- {item.get('source', '')}: {item.get('status', '')} in {item.get('duration_ms', 0)} ms"
            )
```

- [ ] **Step 4: Run the timing-focused tests**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot and (source_timings or timings_section)" -v
```

Expected: PASS

- [ ] **Step 5: Commit the timing diagnostics**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add live snapshot source timing diagnostics"
```

### Task 5: Full regression and one smoke replay

**Files:**
- Modify: none

- [ ] **Step 1: Run all round-2 live snapshot tests**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot" -v
```

Expected: all live snapshot tests pass.

- [ ] **Step 2: Run the full regression file**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -v
```

Expected: full file passes, including `international_first`.

- [ ] **Step 3: Run one manual smoke replay**

Use a small manual payload similar to the round-2 fixtures and verify:

- company/financial read-through topic reports `high_fit`
- generic political observation topic is filtered
- result includes `source_timings`
- markdown includes `## Source Timings`

- [ ] **Step 4: Commit only if debugging required small code cleanup**

If debugging introduced any small cleanup beyond Tasks 2-4:

```bash
git add <exact files>
git commit -m "fix(autoresearch): tighten live snapshot round 2 runtime"
```

### Task 6: Final branch verification snapshot

**Files:**
- Modify: none

- [ ] **Step 1: Record branch state**

Run:

```bash
git status --short --branch
git log --oneline -8
```

Expected: clean branch with task commits present.

- [ ] **Step 2: Prepare completion summary**

At handoff, report:

- the task commit SHAs
- the live snapshot tests run
- the full regression result
- the smoke replay result including `source_timings`
