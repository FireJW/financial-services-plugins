# Live Snapshot Hardening Round 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten `discovery_profile=live_snapshot` so it promotes real market/company read-through topics, suppresses political/newsy medium-fit leakage, limits medium-fit retention, and emits source timing diagnostics.

**Architecture:** Keep the existing `live_snapshot` profile and extend only its fit heuristic, low-yield filtering, and final retention gate. Add top-level runtime timing fields without changing `default` or `international_first`, and verify all behavior through the shared `test_article_publish.py` suite plus a small CLI smoke.

**Tech Stack:** Python 3.12, argparse CLI wrapper, `hot_topic_discovery_runtime.py`, pytest via `test_article_publish.py`

---

### Task 1: Add red tests for fit promotion, political filtering, medium-fit gating, and timing output

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
- Reference: `docs/superpowers/specs/2026-04-21-live-snapshot-hardening-round2-design.md`

- [ ] **Step 1: Add a second-round live snapshot fixture**

Add a new fixture helper near the existing `live_snapshot_candidates()` fixture:

```python
    def live_snapshot_round2_candidates(self) -> list[dict]:
        return [
            {
                "title": "ByteDance revenue mix shifts while AI spending drives profit down 70%",
                "summary": "A same-day company result with clear revenue, profit, and AI capex read-through.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-bytedance-round2",
                        "published_at": "2026-04-21T08:30:00+00:00",
                        "summary": "Overseas revenue hits a new high while AI investment pulls profit sharply lower.",
                    }
                ],
            },
            {
                "title": "International observation: several paths remain for US-Iran negotiations",
                "summary": "A same-day geopolitical explainer without a direct market, company, or supply-chain read-through.",
                "source_items": [
                    {
                        "source_name": "新华网",
                        "source_type": "major_news",
                        "url": "https://example.com/xinhua-us-iran-round2",
                        "published_at": "2026-04-21T08:35:00+00:00",
                        "summary": "A high-level situation explainer on negotiations and possible diplomatic paths.",
                    }
                ],
            },
            {
                "title": "Token anxiety grows as AI billing spreads through software teams",
                "summary": "Fresh but softer same-day topic that may deserve medium-fit status, not top-slot priority.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-token-anxiety-round2",
                        "published_at": "2026-04-21T08:20:00+00:00",
                        "summary": "Engineering teams are suddenly watching token spending as usage rises.",
                    }
                ],
            },
            {
                "title": "Domestic model vendors quietly reshape go-to-market plans",
                "summary": "Another fresh but weaker same-day topic that should not crowd out stronger read-through stories.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-model-plans-round2",
                        "published_at": "2026-04-21T08:10:00+00:00",
                        "summary": "Vendors are shifting strategy, but the second-order market impact remains fuzzy.",
                    }
                ],
            },
        ]
```

- [ ] **Step 2: Add a failing test that promotes real read-through topics to `high_fit`**

```python
    def test_hot_topic_discovery_live_snapshot_promotes_financial_readthrough_to_high_fit(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-21T09:00:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        topic = next(
            item for item in result["ranked_topics"]
            if item["title"] == "ByteDance revenue mix shifts while AI spending drives profit down 70%"
        )
        self.assertEqual(topic["live_snapshot_fit"], "high_fit")
```

- [ ] **Step 3: Add a failing test that filters the geopolitical explainer**

```python
    def test_hot_topic_discovery_live_snapshot_filters_political_observer_style_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-21T09:00:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        ranked_titles = {item["title"] for item in result["ranked_topics"]}
        self.assertNotIn("International observation: several paths remain for US-Iran negotiations", ranked_titles)
```

- [ ] **Step 4: Add a failing test for medium-fit retention cap**

```python
    def test_hot_topic_discovery_live_snapshot_caps_medium_fit_retention(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-21T09:00:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        medium_titles = [
            item["title"]
            for item in result["ranked_topics"]
            if item["live_snapshot_fit"] == "medium_fit"
        ]
        self.assertLessEqual(len(medium_titles), 2)
```

- [ ] **Step 5: Add a failing test for source timing output**

```python
    def test_hot_topic_discovery_live_snapshot_emits_source_timing_diagnostics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-21T09:00:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round2_candidates(),
            }
        )
        self.assertIn("source_timings", result)
        self.assertIn("total_runtime_ms", result)
```

- [ ] **Step 6: Run focused tests and confirm RED**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot and (promotes_financial_readthrough_to_high_fit or political_observer_style_topics or caps_medium_fit_retention or emits_source_timing_diagnostics)" -v
```

Expected: all new round-2 tests fail because the second-round hardening logic does not exist yet.

- [ ] **Step 7: Commit the red tests**

```bash
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "test(autoresearch): add live snapshot hardening round 2 coverage"
```

### Task 2: Expand `high_fit` detection for financial, market, and conflict read-through topics

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Expand the live snapshot high-signal keyword set**

Replace the current narrow keyword set with a richer read-through-oriented set:

```python
LIVE_SNAPSHOT_ANALYSIS_KEYWORDS = {
    "revenue", "profit", "margin", "loss", "guidance", "earnings", "capex",
    "order", "orders", "oil", "equities", "stocks", "risk assets", "shipping",
    "strait", "inflation", "yield", "ceasefire", "negotiation", "sanction",
    "disruption", "营收", "利润", "净利", "亏损", "指引", "财报",
    "资本开支", "订单", "油价", "航运", "风险资产", "通胀", "谈判", "停火",
}
```

- [ ] **Step 2: Keep the signal text narrow**

Preserve the `live_snapshot_signal_text()` pattern so negative or generic summary prose does not accidentally trip `high_fit`:

```python
def live_snapshot_signal_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        [
            clean_text(candidate.get("title")),
            " ".join(clean_string_list(candidate.get("keywords"))),
        ]
    ).lower()
```

- [ ] **Step 3: Update `live_snapshot_fit()` to use the expanded read-through set**

```python
def live_snapshot_fit(candidate: dict[str, Any]) -> str:
    text = live_snapshot_signal_text(candidate)
    freshness = clean_text(candidate.get("freshness_bucket"))
    if freshness in {"0-6h", "6-24h"} and contains_any_keyword(text, LIVE_SNAPSHOT_ANALYSIS_KEYWORDS):
        return "high_fit"
    if freshness in {"0-6h", "6-24h"}:
        return "medium_fit"
    return "low_fit"
```

- [ ] **Step 4: Run the high-fit promotion test**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "promotes_financial_readthrough_to_high_fit" -v
```

Expected: PASS

- [ ] **Step 5: Commit the fit-expansion change**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): promote live snapshot read-through topics"
```

### Task 3: Filter political/newsy leakage and cap retained medium-fit topics

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Add a stronger low-yield keyword set**

Define a separate set for political/newsy leakage:

```python
LIVE_SNAPSHOT_LOW_YIELD_KEYWORDS = {
    "international observation",
    "several paths remain",
    "diplomatic",
    "visit",
    "visits",
    "modernization",
    "official commentary",
    "观察",
    "访华",
    "政要",
    "外交",
    "口径",
    "国际观察",
}
```

- [ ] **Step 2: Tighten the low-yield helper**

Keep it narrow and still let true market/policy transmission topics through:

```python
def is_live_snapshot_low_yield_candidate(candidate: dict[str, Any]) -> bool:
    text = live_snapshot_signal_text(candidate)
    if not contains_any_keyword(text, LIVE_SNAPSHOT_LOW_YIELD_KEYWORDS):
        return False
    if contains_any_keyword(text, LIVE_SNAPSHOT_ANALYSIS_KEYWORDS):
        return False
    return True
```

- [ ] **Step 3: Add a medium-fit retention gate in `run_hot_topic_discovery()`**

After the normal keep/filter pass but before final truncation, gate `live_snapshot` results:

```python
def enforce_live_snapshot_fit_gate(
    kept_topics: list[dict[str, Any]],
    filtered_out_topics: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    high_fit = [topic for topic in kept_topics if topic.get("live_snapshot_fit") == "high_fit"]
    medium_fit = [topic for topic in kept_topics if topic.get("live_snapshot_fit") == "medium_fit"]
    low_fit = [topic for topic in kept_topics if topic.get("live_snapshot_fit") == "low_fit"]
    for topic in low_fit:
        filtered_out_topics.append(
            {
                "title": clean_text(topic.get("title")),
                "filter_reason": "deprioritized low-fit live snapshot topic",
                "total_score": safe_dict(topic.get("score_breakdown")).get("total_score", 0),
            }
        )
    return (high_fit + medium_fit[:2])[:top_n]
```

Then call it only for `live_snapshot`.

- [ ] **Step 4: Run the filter and medium-cap tests**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "political_observer_style_topics or caps_medium_fit_retention" -v
```

Expected: PASS

- [ ] **Step 5: Commit the filtering/gating change**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): tighten live snapshot ranking gate"
```

### Task 4: Emit source timing diagnostics

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Import a monotonic timer**

Add:

```python
from time import perf_counter
```

- [ ] **Step 2: Track per-source duration and item count**

Inside `run_hot_topic_discovery()`, add:

```python
source_timings: list[dict[str, Any]] = []
run_started = perf_counter()
```

For each source fetch:

```python
started = perf_counter()
items = fetch_source_items(source_name, request)
duration_ms = int(round((perf_counter() - started) * 1000))
source_timings.append(
    {
        "source": source_name,
        "duration_ms": duration_ms,
        "item_count": len(items),
        "status": "ok",
    }
)
```

On exception:

```python
source_timings.append(
    {
        "source": source_name,
        "duration_ms": duration_ms,
        "item_count": 0,
        "status": "error",
    }
)
```

At the end:

```python
total_runtime_ms = int(round((perf_counter() - run_started) * 1000))
```

And add both fields to the final result.

- [ ] **Step 3: Run the timing-output test**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "emits_source_timing_diagnostics" -v
```

Expected: PASS

- [ ] **Step 4: Commit the timing diagnostics**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): emit live snapshot source timings"
```

### Task 5: Full regression and one CLI smoke

**Files:**
- Modify: none
- Verify: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
- Verify manually: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py`

- [ ] **Step 1: Run all live snapshot tests**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "live_snapshot" -v
```

Expected: all `live_snapshot` tests pass.

- [ ] **Step 2: Run the full regression file**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -v
```

Expected: full file passes, including `international_first` coverage.

- [ ] **Step 3: Run a CLI smoke**

Create a smoke request with one clear `high_fit` topic, run:

```bash
py financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py <request.json> --output <result.json> --quiet
```

Verify `result.json` contains:

- `live_snapshot_fit`
- `live_snapshot_reason`
- `source_timings`
- `total_runtime_ms`

- [ ] **Step 4: Record final branch status**

Run:

```bash
git status --short --branch
git log --oneline -6
```

Expected:

- clean branch
- commits in logical order
