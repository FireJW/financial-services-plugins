# Live Snapshot Hardening Round 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden `discovery_profile=live_snapshot` so low-fit topics stop occupying the shortlist, medium-fit topics are capped more aggressively, and slow sources stop dragging the entire run.

**Architecture:** Keep the scope inside `hot_topic_discovery_runtime.py` by layering a live-snapshot-specific shortlist gate on top of the existing fit classification, then add a lightweight source budget/timeout guard that records source timing even when a source times out. Preserve the behavior of `default` and `international_first`, and verify everything through `test_article_publish.py`.

**Tech Stack:** Python 3.12, `hot_topic_discovery_runtime.py`, pytest via `test_article_publish.py`

---

### Task 1: Add red tests for round 3 shortlist and source-budget behavior

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`
- Reference: `docs/superpowers/specs/2026-04-21-live-snapshot-hardening-round3-design.md`

- [ ] **Step 1: Add round 3 fixture candidates**

Extend the test fixture section with one helper that contains:

- one `high_fit` company financial read-through topic
- one `high_fit` conflict-to-market-transmission topic
- three `medium_fit` same-day but weaker topics
- one `low_fit` same-day narrow news flash

Use concrete titles so the tests can assert exact shortlist ordering:

```python
    def live_snapshot_round3_candidates(self) -> list[dict]:
        return [
            {
                "title": "ByteDance says AI spending drove profit sharply lower",
                "summary": "A same-day company financial read-through topic with profit and AI capex implications.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/bytedance-profit-round3",
                        "published_at": "2026-04-21T09:40:00+00:00",
                        "summary": "ByteDance says heavier AI investment pushed profit sharply lower while overseas revenue kept rising.",
                    }
                ],
            },
            {
                "title": "Hormuz shipping risk jolts oil and equities again",
                "summary": "A same-day market-transmission topic tying shipping disruption to oil and equity repricing.",
                "source_items": [
                    {
                        "source_name": "Reuters",
                        "source_type": "major_news",
                        "url": "https://example.com/hormuz-round3",
                        "published_at": "2026-04-21T09:50:00+00:00",
                        "summary": "Shipping risk in Hormuz pushes oil higher and drags risk assets lower.",
                    }
                ],
            },
            {
                "title": "Anthropic cuts off a large Claude customer overnight",
                "summary": "A fresh AI platform headline with some analysis room but weaker direct market transmission.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/anthropic-round3",
                        "published_at": "2026-04-21T09:55:00+00:00",
                        "summary": "A large Claude customer loses service suddenly, raising questions about platform concentration.",
                    }
                ],
            },
            {
                "title": "Meta token spending anxiety keeps spreading across AI teams",
                "summary": "A fresh AI cost headline with extension room but no hard market transmission.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/meta-token-round3",
                        "published_at": "2026-04-21T09:56:00+00:00",
                        "summary": "Developers complain that token costs are forcing new budgeting conversations across AI teams.",
                    }
                ],
            },
            {
                "title": "Domestic model makers are all changing direction again",
                "summary": "A fresh but weaker synthesis headline without a hard company or market read-through.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/domestic-model-round3",
                        "published_at": "2026-04-21T09:57:00+00:00",
                        "summary": "Several domestic model makers appear to be shifting priorities again.",
                    }
                ],
            },
            {
                "title": "Ceremony honors a historical ancestor",
                "summary": "A same-day narrow news flash with no company, market, or policy read-through.",
                "source_items": [
                    {
                        "source_name": "google-news-world",
                        "source_type": "major_news",
                        "url": "https://example.com/ceremony-round3",
                        "published_at": "2026-04-21T09:58:00+00:00",
                        "summary": "A same-day ceremony headline without analysis value for the live snapshot shortlist.",
                    }
                ],
            },
        ]
```

- [ ] **Step 2: Add a failing test that `low_fit` does not enter the shortlist**

```python
    def test_hot_topic_discovery_live_snapshot_excludes_low_fit_topics_from_shortlist(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-21T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round3_candidates(),
                "top_n": 6,
            }
        )
        ranked_titles = {item["title"] for item in result["ranked_topics"]}
        self.assertNotIn("Ceremony honors a historical ancestor", ranked_titles)
```

- [ ] **Step 3: Add a failing test that only two `medium_fit` topics survive**

```python
    def test_hot_topic_discovery_live_snapshot_caps_medium_fit_backups(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-21T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "manual_topic_candidates": self.live_snapshot_round3_candidates(),
                "top_n": 6,
            }
        )
        medium_titles = [item["title"] for item in result["ranked_topics"] if item["live_snapshot_fit"] == "medium_fit"]
        self.assertLessEqual(len(medium_titles), 2)
```

- [ ] **Step 4: Add a failing test that source timing survives source timeout**

Use a patch on `fetch_source_items` so one source raises after being invoked:

```python
    def test_hot_topic_discovery_live_snapshot_records_source_timing_even_when_source_errors(self) -> None:
        def fake_fetch(source_name: str, request: dict) -> list[dict]:
            if source_name == "google-news-world":
                raise RuntimeError("timed out")
            return []

        with patch("hot_topic_discovery_runtime.fetch_source_items", side_effect=fake_fetch):
            result = run_hot_topic_discovery(
                {
                    "analysis_time": "2026-04-21T10:30:00+00:00",
                    "discovery_profile": "live_snapshot",
                    "sources": ["36kr", "google-news-world"],
                }
            )

        timing_by_source = {item["source"]: item for item in result["source_timings"]}
        self.assertIn("google-news-world", timing_by_source)
        self.assertEqual(timing_by_source["google-news-world"]["status"], "error")
        self.assertIn("duration_ms", timing_by_source["google-news-world"])
```

- [ ] **Step 5: Run focused pytest to confirm RED**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "round3 or low_fit_topics_from_shortlist or caps_medium_fit_backups or records_source_timing_even_when_source_errors" -v
```

Expected: the newly added tests fail because the shortlist cap and source budget behavior do not exist yet.

- [ ] **Step 6: Commit the red tests**

```bash
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "test(autoresearch): add live snapshot round 3 coverage"
```

### Task 2: Add fit-based shortlist gates for `live_snapshot`

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Add live snapshot shortlist constants**

Near the existing `LIVE_SNAPSHOT_*` constants, add:

```python
LIVE_SNAPSHOT_MEDIUM_FIT_LIMIT = 2
LIVE_SNAPSHOT_MEDIUM_FIT_MIN_SCORE = 70
```

- [ ] **Step 2: Add a helper for live snapshot rank reason**

Add a helper that explains shortlist retention:

```python
def live_snapshot_rank_reason(candidate: dict[str, Any]) -> str:
    fit = clean_text(candidate.get("live_snapshot_fit"))
    total = int(safe_dict(candidate.get("score_breakdown")).get("total_score", 0) or 0)
    if fit == "high_fit":
        return "kept as high_fit"
    if fit == "medium_fit" and total >= LIVE_SNAPSHOT_MEDIUM_FIT_MIN_SCORE:
        return "eligible medium_fit backup"
    if fit == "medium_fit":
        return "filtered because medium_fit score below floor"
    return "filtered because low_fit"
```

- [ ] **Step 3: Attach `live_snapshot_rank_reason` inside `build_clustered_candidate()`**

After the existing live snapshot fields:

```python
    if request.get("discovery_profile") == "live_snapshot":
        candidate["live_snapshot_rank_reason"] = live_snapshot_rank_reason(candidate)
```

- [ ] **Step 4: Enforce `low_fit` filtering and `medium_fit` floor in `apply_topic_controls()`**

Add a live-specific gate:

```python
    if request.get("discovery_profile") == "live_snapshot":
        fit = clean_text(candidate.get("live_snapshot_fit"))
        total = int(safe_dict(candidate.get("score_breakdown")).get("total_score", 0) or 0)
        if fit == "low_fit":
            return False, "filtered low_fit live snapshot topic"
        if fit == "medium_fit" and total < LIVE_SNAPSHOT_MEDIUM_FIT_MIN_SCORE:
            return False, "filtered medium_fit live snapshot topic below floor"
```

- [ ] **Step 5: Cap `medium_fit` results after filtering**

In the final ranking path, after `kept_topics` is assembled and before `top_n` slicing, add:

```python
    if request.get("discovery_profile") == "live_snapshot":
        high_fit = [topic for topic in kept_topics if clean_text(topic.get("live_snapshot_fit")) == "high_fit"]
        medium_fit = [topic for topic in kept_topics if clean_text(topic.get("live_snapshot_fit")) == "medium_fit"]
        kept_topics = high_fit + medium_fit[:LIVE_SNAPSHOT_MEDIUM_FIT_LIMIT]
```

- [ ] **Step 6: Run focused shortlist tests**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "low_fit_topics_from_shortlist or caps_medium_fit_backups" -v
```

Expected: PASS

- [ ] **Step 7: Commit the shortlist gate**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): tighten live snapshot shortlist gates"
```

### Task 3: Add lightweight source budget behavior for slow live snapshot sources

**Files:**
- Modify: `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- Test: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Add live snapshot source budget constants**

Define:

```python
LIVE_SNAPSHOT_SOURCE_ORDER = ["36kr", "google-news-world"]
LIVE_SNAPSHOT_GOOGLE_WORLD_TIMEOUT_SECONDS = 15
```

- [ ] **Step 2: Add source ordering helper**

```python
def ordered_sources_for_request(request: dict[str, Any]) -> list[str]:
    sources = list(request["sources"])
    if request.get("discovery_profile") != "live_snapshot":
        return sources
    ordered: list[str] = []
    for preferred in LIVE_SNAPSHOT_SOURCE_ORDER:
        if preferred in sources:
            ordered.append(preferred)
    for source in sources:
        if source not in ordered:
            ordered.append(source)
    return ordered
```

- [ ] **Step 3: Add a budget-aware source fetch wrapper**

Add a small wrapper that only special-cases `google-news-world` under `live_snapshot`:

```python
def fetch_source_items_with_live_snapshot_budget(source_name: str, request: dict[str, Any]) -> list[dict[str, Any]]:
    if request.get("discovery_profile") != "live_snapshot" or source_name != "google-news-world":
        return fetch_source_items(source_name, request)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fetch_source_items, source_name, request)
        try:
            return future.result(timeout=LIVE_SNAPSHOT_GOOGLE_WORLD_TIMEOUT_SECONDS)
        except Exception as exc:  # includes timeout
            future.cancel()
            raise RuntimeError(f"live snapshot source budget exceeded for {source_name}: {exc}") from exc
```

- [ ] **Step 4: Switch `run_hot_topic_discovery()` to ordered sources and wrapper**

Replace direct iteration over `request["sources"]` with:

```python
        sources = ordered_sources_for_request(request)
```

And replace direct `fetch_source_items(...)` calls with:

```python
fetch_source_items_with_live_snapshot_budget(source_name, request)
```

- [ ] **Step 5: Run the focused source timing test**

Run:

```bash
py -m pytest financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "records_source_timing_even_when_source_errors" -v
```

Expected: PASS

- [ ] **Step 6: Commit the source budget change**

```bash
git add financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py
git add financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add live snapshot source budget guard"
```

### Task 4: Run full regression and one live smoke

**Files:**
- Modify: none
- Verify: `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

- [ ] **Step 1: Run the focused live snapshot suite**

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

Expected: full file passes.

- [ ] **Step 3: Run one live smoke**

Use the existing live snapshot request shape and verify:

- low-fit topics are absent from the shortlist
- no more than two `medium_fit` topics remain
- `source_timings` exists

Run:

```bash
py financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py <request.json> --output <result.json> --markdown-output <report.md> --quiet
```

Inspect:

```python
result["ranked_topics"]
result["source_timings"]
result["report_markdown"]
```

- [ ] **Step 4: Record final branch state**

Run:

```bash
git status --short --branch
git log --oneline -6
```

Expected:

- clean branch
- red tests, shortlist gate, and source budget commits present
