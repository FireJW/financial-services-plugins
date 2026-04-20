# Topic Discovery Recency And Heat Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make hot-topic discovery rank fresh high-heat stories more aggressively, demote stale recycled stories, and explain freshness/staleness decisions in operator-facing fields.

**Architecture:** Extend the existing score pipeline in `hot_topic_discovery_runtime.py` with a small set of freshness-specific helpers, then thread those values into `score_breakdown`, `score_reasons`, `why_now`, `selection_reason`, and a new stale-topic filter layer. Keep the current candidate collection and clustering flow intact, and verify the new behavior through targeted `test_article_publish.py` cases before broader regression.

**Tech Stack:** Python, existing `hot_topic_discovery_runtime.py`, existing `test_article_publish.py`, pytest

---

### Task 1: Add failing tests for freshness, stale penalties, and continuing-story exceptions

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py` (later tasks only)

- [ ] **Step 1: Add failing fixture helpers for fresh vs stale topic candidates**

Inside the existing test class that already covers `run_hot_topic_discovery`, add helper methods that return manual candidates with explicit timestamps and source shapes:

```python
    def recency_heat_candidates(self) -> list[dict]:
        return [
            {
                "title": "Hormuz risk returns as oil rebounds and stocks wobble",
                "summary": "Fresh Reuters-backed market move with same-day escalation.",
                "url": "https://example.com/hormuz-fresh",
                "source_name": "Reuters",
                "source_type": "major_news",
                "published_at": "2026-04-20T09:10:00+00:00",
                "heat_score": 8600,
                "tags": ["oil", "shipping", "markets"],
            },
            {
                "title": "DeepSeek breaks with US chip vendors in model testing",
                "summary": "Still discussed, but the last concrete public signal is from February.",
                "url": "https://example.com/deepseek-stale",
                "source_name": "Reuters",
                "source_type": "major_news",
                "published_at": "2026-02-25T10:00:00+00:00",
                "heat_score": 9800,
                "tags": ["ai", "chips", "china"],
            },
        ]

    def continuing_story_candidates(self) -> list[dict]:
        return [
            {
                "title": "Tesla robotaxi story reopens after Dallas and Houston rollout",
                "summary": "An older robotaxi theme gets a fresh operating catalyst.",
                "url": "https://example.com/robotaxi-rollout",
                "source_name": "Reuters",
                "source_type": "major_news",
                "published_at": "2026-04-20T08:30:00+00:00",
                "heat_score": 6200,
                "tags": ["tesla", "robotaxi", "rollout", "dallas", "houston"],
            },
            {
                "title": "Autonomous driving debate continues",
                "summary": "Old broad discussion thread without a new concrete trigger.",
                "url": "https://example.com/robotaxi-stale-chatter",
                "source_name": "Reddit r/stocks",
                "source_type": "social",
                "published_at": "2026-02-20T10:00:00+00:00",
                "heat_score": 7300,
                "tags": ["autonomous", "robotaxi"],
            },
        ]
```

- [ ] **Step 2: Add failing ranking tests for fresh-vs-stale ordering**

Add tests that currently fail because the runtime does not yet expose the new recency-hardening behavior:

```python
    def test_hot_topic_discovery_prefers_fresh_story_over_stale_high_heat_story(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "manual_topic_candidates": self.recency_heat_candidates(),
                "audience_keywords": ["oil", "markets", "shipping", "ai", "chips"],
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        self.assertEqual(
            ranked_titles[0],
            "Hormuz risk returns as oil rebounds and stocks wobble",
        )
```

```python
    def test_hot_topic_discovery_exposes_freshness_and_staleness_fields(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "manual_topic_candidates": self.recency_heat_candidates(),
                "audience_keywords": ["oil", "markets", "shipping", "ai", "chips"],
                "top_n": 5,
            }
        )

        topic = result["ranked_topics"][0]
        for field in (
            "freshness_bucket",
            "freshness_reason",
            "heat_bucket",
            "staleness_flags",
            "is_continuing_story",
            "fresh_catalyst_present",
        ):
            self.assertIn(field, topic)
```

- [ ] **Step 3: Add failing filter tests for stale weak-confirmation topics**

Add tests that describe the desired filter behavior for old single-source weak stories:

```python
    def test_hot_topic_discovery_filters_stale_single_source_topic_without_fresh_catalyst(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "manual_topic_candidates": [
                    {
                        "title": "February AI chip rumor returns to message boards",
                        "summary": "Old single-source platform chatter without a new catalyst.",
                        "url": "https://example.com/ai-rumor-stale",
                        "source_name": "Reddit r/stocks",
                        "source_type": "social",
                        "published_at": "2026-02-18T09:00:00+00:00",
                        "heat_score": 8100,
                        "tags": ["ai", "chips", "rumor"],
                    }
                ],
                "audience_keywords": ["ai", "chips", "markets"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertTrue(
            any("stale" in item["filter_reason"].lower() for item in result["filtered_out_topics"])
        )
```

- [ ] **Step 4: Add failing continuing-story exception tests**

Add tests to prove older themes survive only when a fresh catalyst exists:

```python
    def test_hot_topic_discovery_keeps_continuing_story_when_fresh_catalyst_reopens_it(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "manual_topic_candidates": self.continuing_story_candidates(),
                "audience_keywords": ["tesla", "robotaxi", "mobility", "markets"],
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        self.assertIn(
            "Tesla robotaxi story reopens after Dallas and Houston rollout",
            ranked_titles,
        )
```

- [ ] **Step 5: Run focused topic-discovery tests to verify RED**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "fresh_story or stale_single_source or continuing_story or freshness_and_staleness_fields" -v`

Expected:
- FAIL because the new fields, filters, and ranking behavior do not exist yet

- [ ] **Step 6: Commit the failing tests**

```bash
git -C D:\Users\rickylu\dev\financial-services-plugins add D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py
git -C D:\Users\rickylu\dev\financial-services-plugins commit -m "test(autoresearch): add recency and stale-topic discovery coverage"
```

### Task 2: Implement freshness classification and additive recency-hardening helpers

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add freshness-bucket and continuing-story helper functions**

Near the scoring helpers (`timeliness_score`, `depth_score`, etc.), add focused helpers:

```python
def freshness_bucket(candidate: dict[str, Any], analysis_time: datetime) -> str:
    newest_age = age_minutes(analysis_time, candidate.get("latest_published_at", ""))
    if newest_age <= 360:
        return "0-6h"
    if newest_age <= 1440:
        return "6-24h"
    if newest_age <= 4320:
        return "24-72h"
    return ">72h"


def is_continuing_story_candidate(candidate: dict[str, Any]) -> bool:
    text = candidate_match_text(candidate)
    return contains_any_keyword(
        text,
        [
            "guidance",
            "earnings",
            "rollout",
            "regulation",
            "lawsuit",
            "escalation",
            "停火",
            "关税",
            "扩城",
            "指引",
            "财报",
            "升级",
        ],
    )


def has_fresh_catalyst(candidate: dict[str, Any], analysis_time: datetime) -> bool:
    bucket = freshness_bucket(candidate, analysis_time)
    return bucket in {"0-6h", "6-24h"} and is_continuing_story_candidate(candidate)
```

- [ ] **Step 2: Add recency-hardening score helpers**

Implement the new additive layers:

```python
def freshness_window_bonus(candidate: dict[str, Any], analysis_time: datetime) -> int:
    bucket = freshness_bucket(candidate, analysis_time)
    if bucket == "0-6h":
        return 12
    if bucket == "6-24h":
        return 7
    return 0


def stale_story_penalty(candidate: dict[str, Any], analysis_time: datetime) -> int:
    bucket = freshness_bucket(candidate, analysis_time)
    if bucket != ">72h":
        return 0
    penalty = 10
    if int(candidate.get("source_count", 0) or 0) <= 1:
        penalty += 8
    if primary_platform_signal_count(candidate) > 0 and int(candidate.get("source_count", 0) or 0) <= 1:
        penalty += 6
    if is_rumor_like_candidate(candidate):
        penalty += 6
    return penalty


def fresh_catalyst_bonus(candidate: dict[str, Any], analysis_time: datetime) -> int:
    return 8 if has_fresh_catalyst(candidate, analysis_time) else 0


def near_window_heat_bonus(candidate: dict[str, Any], analysis_time: datetime) -> int:
    bucket = freshness_bucket(candidate, analysis_time)
    if bucket not in {"0-6h", "6-24h"}:
        return 0
    source_count = int(candidate.get("source_count", 0) or 0)
    source_mix = len(candidate.get("source_names") or [])
    if source_count >= 3 and source_mix >= 2:
        return 8
    if source_count >= 2:
        return 4
    return 0
```

- [ ] **Step 3: Run the focused tests again to verify GREEN on helper availability**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "freshness_and_staleness_fields or continuing_story" -v`

Expected:
- still FAIL on ranking/output integration, but no longer fail because helper functions are missing from the code path

- [ ] **Step 4: Commit**

```bash
git -C D:\Users\rickylu\dev\financial-services-plugins add D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py
git -C D:\Users\rickylu\dev\financial-services-plugins commit -m "feat(autoresearch): add recency hardening helper functions"
```

### Task 3: Integrate freshness/staleness layers into candidate scoring and operator output

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Extend `build_clustered_candidate()` scoring path**

In the scoring section around the existing block:

```python
timeliness = timeliness_score(candidate, analysis_time)
debate = discussion_score(candidate["title"], candidate["source_count"])
relevance = relevance_score(candidate, audience_keywords, preferred_topic_keywords)
depth = depth_score(candidate)
seo = seo_score(candidate["title"], candidate["keywords"])
```

Add:

```python
freshness_bonus = freshness_window_bonus(candidate, analysis_time)
stale_penalty = stale_story_penalty(candidate, analysis_time)
catalyst_bonus = fresh_catalyst_bonus(candidate, analysis_time)
near_window_heat = near_window_heat_bonus(candidate, analysis_time)
```

Then compute:

```python
total = clamp(
    timeliness * weights["timeliness"]
    + debate * weights["debate"]
    + relevance * weights["relevance"]
    + depth * weights["depth"]
    + seo * weights["seo"]
    + freshness_bonus
    + catalyst_bonus
    + near_window_heat
    - stale_penalty
)
```

- [ ] **Step 2: Thread new values into `score_breakdown`, `score_reasons`, and candidate fields**

Add the following fields into `candidate["score_breakdown"]`:

```python
candidate["score_breakdown"].update(
    {
        "freshness_window_bonus": freshness_bonus,
        "stale_story_penalty": stale_penalty,
        "fresh_catalyst_bonus": catalyst_bonus,
        "near_window_heat_bonus": near_window_heat,
    }
)
```

Add candidate-level fields:

```python
candidate["freshness_bucket"] = freshness_bucket(candidate, analysis_time)
candidate["freshness_reason"] = freshness_reason_summary(candidate, analysis_time)
candidate["heat_bucket"] = heat_bucket_summary(candidate, analysis_time)
candidate["staleness_flags"] = staleness_flags_for_candidate(candidate, analysis_time)
candidate["is_continuing_story"] = is_continuing_story_candidate(candidate)
candidate["fresh_catalyst_present"] = has_fresh_catalyst(candidate, analysis_time)
```

Add concise reasons like:

```python
if freshness_bonus:
    reasons.append(f"freshness bonus +{freshness_bonus} ({candidate['freshness_bucket']})")
if stale_penalty:
    reasons.append(f"stale penalty -{stale_penalty}")
if catalyst_bonus:
    reasons.append(f"fresh catalyst +{catalyst_bonus}")
if near_window_heat:
    reasons.append(f"near-window heat +{near_window_heat}")
```

- [ ] **Step 3: Update `why_now_summary(...)` and `selection_reason_summary(...)` to explain freshness**

Replace generic explanation paths with bucket-aware language. Example shape:

```python
def why_now_summary(candidate: dict[str, Any]) -> str:
    bucket = clean_text(candidate.get("freshness_bucket"))
    if candidate.get("fresh_catalyst_present"):
        return "This is an older story that became active again because a fresh catalyst just landed."
    if bucket in {"0-6h", "6-24h"}:
        return "This topic is ranking because recent public signals are landing now, not because of residual old discussion."
    return "Discussion exists, but the latest public signals are already aging, so this topic is losing freshness."
```

```python
def selection_reason_summary(candidate: dict[str, Any]) -> str:
    if candidate.get("fresh_catalyst_present"):
        return "The topic stayed in because a new catalyst re-opened a continuing story."
    if clean_text(candidate.get("freshness_bucket")) in {"0-6h", "6-24h"}:
        return "The topic won on fresh signal quality and near-window heat."
    return "The topic is being kept only on residual strength and is vulnerable to stale-story downgrades."
```

- [ ] **Step 4: Run focused scoring/output tests**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "fresh_story or freshness_and_staleness_fields or continuing_story" -v`

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C D:\Users\rickylu\dev\financial-services-plugins add D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py
git -C D:\Users\rickylu\dev\financial-services-plugins commit -m "feat(autoresearch): add freshness and stale-story topic scoring"
```

### Task 4: Add stale-topic filter gates with continuing-story exceptions

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add helper functions for stale-topic filtering**

Add focused gate helpers:

```python
def should_filter_stale_old_story(candidate: dict[str, Any], analysis_time: datetime) -> bool:
    return (
        freshness_bucket(candidate, analysis_time) == ">72h"
        and not has_fresh_catalyst(candidate, analysis_time)
    )


def should_filter_weak_old_story(candidate: dict[str, Any], analysis_time: datetime) -> bool:
    if freshness_bucket(candidate, analysis_time) not in {"24-72h", ">72h"}:
        return False
    source_count = int(candidate.get("source_count", 0) or 0)
    return (
        source_count <= 1
        or "fallback_only" in risk_flags_for_candidate(candidate)
        or (primary_platform_signal_count(candidate) > 0 and source_count <= 1)
    )
```

- [ ] **Step 2: Apply the filter gates in `run_hot_topic_discovery(...)` after candidate build**

In the candidate filtering section before final ranking output, add:

```python
if should_filter_stale_old_story(candidate, request["analysis_time"]):
    filtered_out_topics.append(
        {
            "title": clean_text(candidate.get("title")),
            "filter_reason": "filtered stale topic because the freshest public support is older than 72h and no fresh catalyst was detected",
            "total_score": safe_dict(candidate.get("score_breakdown")).get("total_score", 0),
        }
    )
    continue

if should_filter_weak_old_story(candidate, request["analysis_time"]):
    filtered_out_topics.append(
        {
            "title": clean_text(candidate.get("title")),
            "filter_reason": "filtered weak stale topic because recency and confirmation both fell below the freshness floor",
            "total_score": safe_dict(candidate.get("score_breakdown")).get("total_score", 0),
        }
    )
    continue
```

- [ ] **Step 3: Run stale-filter tests**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "stale_single_source or continuing_story" -v`

Expected:
- PASS

- [ ] **Step 4: Commit**

```bash
git -C D:\Users\rickylu\dev\financial-services-plugins add D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py
git -C D:\Users\rickylu\dev\financial-services-plugins commit -m "feat(autoresearch): filter stale weak-confirmation topics"
```

### Task 5: Run focused and broader regression verification

**Files:**
- Modify: none expected
- Test:
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
  - `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_agent_reach_bridge.py`

- [ ] **Step 1: Run focused hot-topic regression**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "hot_topic_discovery and (fresh or stale or catalyst or why_now or selection_reason)" -v`

Expected:
- PASS

- [ ] **Step 2: Run the full article publish suite**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -v`

Expected:
- PASS

- [ ] **Step 3: Run agent-reach bridge regression**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_agent_reach_bridge.py -v`

Expected:
- PASS

- [ ] **Step 4: Commit final verification state**

```bash
git -C D:\Users\rickylu\dev\financial-services-plugins add D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py
git -C D:\Users\rickylu\dev\financial-services-plugins commit -m "test(autoresearch): verify recency and heat hardened topic discovery"
```

### Task 6: Sanity-check operator output against the user complaint

**Files:**
- Modify: none expected
- Test: reuse `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add an operator-output assertion for stale-vs-fresh explanation**

Add one more test that checks:

```python
    def test_hot_topic_discovery_selection_reason_calls_out_stale_vs_fresh_logic(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-20T10:30:00+00:00",
                "manual_topic_candidates": self.recency_heat_candidates(),
                "audience_keywords": ["oil", "markets", "shipping", "ai", "chips"],
                "top_n": 5,
            }
        )

        fresh_topic = result["ranked_topics"][0]
        self.assertTrue(
            "fresh" in fresh_topic["why_now"].lower()
            or "last 12 hours" in fresh_topic["why_now"].lower()
        )
```

- [ ] **Step 2: Run the single assertion test**

Run:
`pytest D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py -k "selection_reason_calls_out_stale_vs_fresh_logic" -v`

Expected:
- PASS

- [ ] **Step 3: Commit**

```bash
git -C D:\Users\rickylu\dev\financial-services-plugins add D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py
git -C D:\Users\rickylu\dev\financial-services-plugins commit -m "test(autoresearch): assert fresh-vs-stale operator explanations"
```

## Self-Review

Spec coverage check:

- freshness hardening: Task 2 and Task 3
- stale-topic penalties and filters: Task 2 and Task 4
- continuing-story exception: Task 1, Task 2, Task 4
- operator-facing fields and explanations: Task 3 and Task 6
- regression safety: Task 5

Placeholder scan:

- no `TODO`
- no `TBD`
- each task includes exact files, concrete test intentions, concrete commands, and concrete implementation direction

Type consistency check:

- helper names are reused consistently across tasks:
  - `freshness_bucket`
  - `is_continuing_story_candidate`
  - `has_fresh_catalyst`
  - `freshness_window_bonus`
  - `stale_story_penalty`
  - `fresh_catalyst_bonus`
  - `near_window_heat_bonus`
  - `should_filter_stale_old_story`
  - `should_filter_weak_old_story`

