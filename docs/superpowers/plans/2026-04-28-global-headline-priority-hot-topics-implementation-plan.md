# Global Headline Priority Hot Topics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `hot_topic_discovery` always place a true cross-market global headline at rank 1 when present, while keeping AI and technology topics as the sector follow-up layer behind it.

**Architecture:** Keep the existing live-snapshot candidate clustering and scoring pipeline intact, but add a deterministic `headline_priority_class` pass between scoring and filtering. Global headlines bypass sector-fit suppression, then the final shortlist is composed from a one-item `Top Headline Now` lane plus the remaining `Best Sector Follow-Ups` lane. The existing live-snapshot report stays in the same file, but its rendered sections split into explicit top-headline and sector-follow-up blocks.

**Tech Stack:** Python 3.12, existing `hot_topic_discovery_runtime.py`, existing `test_article_publish.py`, unittest via `python-local.cmd`

---

### Task 1: Add Red Tests For Global-Headline Promotion

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add global-headline manual candidate fixtures**

Add these helper methods near the existing `live_snapshot_candidates`, `live_snapshot_round2_candidates`, and `live_snapshot_round3_candidates` helpers:

```python
    def live_snapshot_global_headline_candidates(self) -> list[dict]:
        return [
            {
                "title": "UAE says it will leave OPEC and OPEC+ next month",
                "summary": "The UAE said it will leave OPEC and OPEC+ from May 1, raising questions about oil supply discipline, inflation, and cross-asset risk pricing.",
                "source_items": [
                    {
                        "source_name": "Reuters",
                        "source_type": "major_news",
                        "url": "https://example.com/reuters-uae-opec-exit",
                        "published_at": "2026-04-28T08:20:00+00:00",
                        "summary": "The UAE said it will leave OPEC and OPEC+ from May 1, sending oil and macro desks scrambling to reassess supply discipline.",
                        "heat_score": 98,
                        "tags": ["macro", "oil", "opec", "geopolitics"],
                    },
                    {
                        "source_name": "AP",
                        "source_type": "major_news",
                        "url": "https://example.com/ap-uae-opec-exit",
                        "published_at": "2026-04-28T08:28:00+00:00",
                        "summary": "AP confirmed the UAE exit decision and highlighted the implications for energy pricing and producer cohesion.",
                        "heat_score": 94,
                        "tags": ["macro", "energy", "opec"],
                    },
                ],
            },
            {
                "title": "Anthropic cloud spending locks in another AI capex cycle",
                "summary": "Google and Amazon are using Anthropic to tie model growth directly to long-duration cloud and compute budgets.",
                "source_items": [
                    {
                        "source_name": "Reuters",
                        "source_type": "major_news",
                        "url": "https://example.com/reuters-anthropic-cloud-cycle",
                        "published_at": "2026-04-28T07:40:00+00:00",
                        "summary": "Anthropic is becoming a focal point for AI cloud spending and long-duration compute commitments.",
                        "heat_score": 93,
                        "tags": ["ai", "cloud", "anthropic", "capex"],
                    },
                    {
                        "source_name": "Investing.com",
                        "source_type": "major_news",
                        "url": "https://example.com/investing-anthropic-cloud-cycle",
                        "published_at": "2026-04-28T07:45:00+00:00",
                        "summary": "Cloud vendors are tying Anthropic growth to infrastructure budgets, not just model hype.",
                        "heat_score": 89,
                        "tags": ["ai", "cloud", "anthropic"],
                    },
                ],
            },
        ]

    def live_snapshot_weak_macro_noise_candidates(self) -> list[dict]:
        return [
            {
                "title": "Commentary wonders if OPEC may discuss future coordination",
                "summary": "A generic commentary thread speculates that energy ministers could revisit coordination at some point.",
                "source_items": [
                    {
                        "source_name": "weibo",
                        "source_type": "social",
                        "url": "https://example.com/weibo-opec-speculation",
                        "published_at": "2026-04-28T08:10:00+00:00",
                        "summary": "A generic speculative post asks whether OPEC might coordinate again in the future.",
                        "heat_score": 42,
                        "tags": ["macro", "oil", "commentary"],
                    }
                ],
            },
            {
                "title": "Intel says AI demand is spreading into CPU and system design",
                "summary": "The AI infrastructure narrative is broadening beyond GPUs into CPUs and system-level architecture.",
                "source_items": [
                    {
                        "source_name": "Reuters",
                        "source_type": "major_news",
                        "url": "https://example.com/reuters-intel-cpu-ai",
                        "published_at": "2026-04-28T07:55:00+00:00",
                        "summary": "Intel rallied as investors priced a wider AI compute stack that now includes CPU demand.",
                        "heat_score": 86,
                        "tags": ["ai", "cpu", "intel"],
                    }
                ],
            },
        ]
```

- [ ] **Step 2: Add failing tests for global-headline rank-1 behavior**

Insert these tests after the current live-snapshot fit and filter coverage:

```python
    def test_hot_topic_discovery_live_snapshot_promotes_global_headline_even_when_sector_fit_is_low(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-28T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "preferred_topic_keywords": ["AI", "chip", "data center", "semiconductor"],
                "manual_topic_candidates": self.live_snapshot_global_headline_candidates(),
                "top_n": 5,
            }
        )

        top_topic = result["ranked_topics"][0]
        self.assertEqual(top_topic["title"], "UAE says it will leave OPEC and OPEC+ next month")
        self.assertEqual(top_topic["headline_priority_class"], "global_headline")
        self.assertEqual(top_topic["headline_priority_rank"], 1)

    def test_hot_topic_discovery_live_snapshot_keeps_global_headline_out_of_low_fit_rejection(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-28T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "preferred_topic_keywords": ["AI", "chip", "data center", "semiconductor"],
                "manual_topic_candidates": self.live_snapshot_global_headline_candidates(),
                "top_n": 5,
            }
        )

        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertNotIn("UAE says it will leave OPEC and OPEC+ next month", filtered_titles)

    def test_hot_topic_discovery_live_snapshot_does_not_promote_weak_macro_noise_to_global_headline(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-28T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "preferred_topic_keywords": ["AI", "chip", "data center", "semiconductor"],
                "manual_topic_candidates": self.live_snapshot_weak_macro_noise_candidates(),
                "top_n": 5,
            }
        )

        top_topic = result["ranked_topics"][0]
        self.assertNotEqual(top_topic["title"], "Commentary wonders if OPEC may discuss future coordination")
        weak_macro = next(
            item for item in result["filtered_out_topics"]
            if item["title"] == "Commentary wonders if OPEC may discuss future coordination"
        )
        self.assertIn("low", weak_macro["filter_reason"])

    def test_hot_topic_discovery_report_splits_top_headline_from_sector_followups(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-28T10:30:00+00:00",
                "discovery_profile": "live_snapshot",
                "preferred_topic_keywords": ["AI", "chip", "data center", "semiconductor"],
                "manual_topic_candidates": self.live_snapshot_global_headline_candidates(),
                "top_n": 5,
            }
        )

        self.assertIn("## Top Headline Now", result["report_markdown"])
        self.assertIn("## Best Sector Follow-Ups", result["report_markdown"])
```

- [ ] **Step 3: Run the live-snapshot test file to confirm red**

Run:

```powershell
cmd /c ".\financial-analysis\skills\autoresearch-info-index\scripts\python-local.cmd .\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py"
```

Expected:

- the four new tests fail because `headline_priority_class`, `headline_priority_rank`, and the new report sections do not exist yet
- existing live-snapshot tests continue to run

- [ ] **Step 4: Commit nothing yet**

Do not commit after the red phase. Leave the failing tests in the worktree and move directly into runtime implementation.

### Task 2: Implement Global-Headline Classification And Filter Bypass

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add deterministic global-headline constants**

Add these constants near the existing live-snapshot constants:

```python
GLOBAL_HEADLINE_PRIORITY_KEYWORDS = {
    "opec",
    "opec+",
    "oil",
    "brent",
    "crude",
    "fed",
    "fomc",
    "treasury",
    "tariff",
    "sanction",
    "sanctions",
    "hormuz",
    "strait of hormuz",
    "war",
    "ceasefire",
    "sovereign",
    "central bank",
    "policy shock",
}

GLOBAL_HEADLINE_IMPACT_KEYWORDS = {
    "inflation",
    "equities",
    "stocks",
    "bonds",
    "yield",
    "risk assets",
    "energy prices",
    "global markets",
    "macro desks",
    "supply discipline",
}

GLOBAL_HEADLINE_MIN_TOTAL_SCORE = 72
GLOBAL_HEADLINE_MIN_SOURCE_CONFIRMATION = 65
GLOBAL_HEADLINE_PRIORITY_BONUS = 8
```

- [ ] **Step 2: Add global-headline classifier helpers**

Place these helpers near the live-snapshot fit helpers:

```python
def global_headline_signal_text(candidate: dict[str, Any]) -> str:
    return " ".join(
        [
            candidate_match_text(candidate),
            clean_text(candidate.get("why_now")),
            clean_text(candidate.get("selection_reason")),
            clean_text(candidate.get("source_mix")),
        ]
    ).lower()


def is_global_headline_candidate(candidate: dict[str, Any]) -> bool:
    text = global_headline_signal_text(candidate)
    source_confirmation = int(safe_dict(candidate.get("score_breakdown")).get("source_confirmation", 0) or 0)
    total = int(safe_dict(candidate.get("score_breakdown")).get("total_score", 0) or 0)
    freshness = clean_text(candidate.get("freshness_bucket"))
    if freshness not in {"0-6h", "6-24h", "24-72h"}:
        return False
    if not contains_any_keyword(text, GLOBAL_HEADLINE_PRIORITY_KEYWORDS):
        return False
    if not contains_any_keyword(text, GLOBAL_HEADLINE_IMPACT_KEYWORDS):
        return False
    if source_confirmation < GLOBAL_HEADLINE_MIN_SOURCE_CONFIRMATION:
        return False
    if total < GLOBAL_HEADLINE_MIN_TOTAL_SCORE:
        return False
    return True


def headline_priority_class(candidate: dict[str, Any]) -> str:
    return "global_headline" if is_global_headline_candidate(candidate) else "sector_follow_up"


def headline_priority_reason(candidate: dict[str, Any]) -> str:
    if headline_priority_class(candidate) == "global_headline":
        return "cross-market macro headline with direct asset-pricing impact"
    return "best sector follow-up after the top cross-market headline slot"
```

- [ ] **Step 3: Attach classification fields inside candidate construction**

Modify the end of `build_clustered_candidate(...)` so the candidate receives:

```python
    if request.get("discovery_profile") == "live_snapshot":
        candidate["live_snapshot_fit"] = live_snapshot_fit(candidate)
        candidate["live_snapshot_reason"] = live_snapshot_reason(candidate)
        candidate["live_snapshot_rank_reason"] = live_snapshot_rank_reason(candidate)
        candidate["headline_priority_class"] = headline_priority_class(candidate)
        candidate["headline_priority_reason"] = headline_priority_reason(candidate)
        if candidate["headline_priority_class"] == "global_headline":
            candidate["score_breakdown"]["global_headline_priority_bonus"] = GLOBAL_HEADLINE_PRIORITY_BONUS
            candidate["score_breakdown"]["total_score"] = clamp(
                int(candidate["score_breakdown"]["total_score"]) + GLOBAL_HEADLINE_PRIORITY_BONUS
            )
        else:
            candidate["score_breakdown"]["global_headline_priority_bonus"] = 0
```

Also append a score reason when the candidate becomes a global headline:

```python
    if candidate.get("headline_priority_class") == "global_headline":
        reasons.append(f"global headline priority (+{GLOBAL_HEADLINE_PRIORITY_BONUS})")
```

- [ ] **Step 4: Bypass sector-fit suppression for global headlines**

Modify `apply_topic_controls(...)`:

```python
    if request.get("discovery_profile") == "live_snapshot":
        fit = clean_text(candidate.get("live_snapshot_fit"))
        total = int(safe_dict(candidate.get("score_breakdown")).get("total_score", 0) or 0)
        is_global_headline = clean_text(candidate.get("headline_priority_class")) == "global_headline"
        if not is_global_headline and fit == "low_fit":
            return False, "filtered low_fit live snapshot topic"
        if not is_global_headline and fit == "medium_fit" and total < LIVE_SNAPSHOT_MEDIUM_FIT_MIN_SCORE:
            return False, "filtered medium_fit live snapshot topic below floor"
        if not is_global_headline and is_live_snapshot_low_yield_candidate(candidate):
            return False, "filtered low-yield live snapshot topic"
```

- [ ] **Step 5: Rebuild the final shortlist as a two-lane output**

Replace the current `enforce_live_snapshot_fit_gate(...)` body with a version that preserves one top headline slot before sector fit gating:

```python
def enforce_live_snapshot_fit_gate(
    kept_topics: list[dict[str, Any]],
    filtered_out_topics: list[dict[str, Any]],
    top_n: int,
) -> list[dict[str, Any]]:
    global_headlines = [
        topic for topic in kept_topics
        if clean_text(topic.get("headline_priority_class")) == "global_headline"
    ]
    sector_topics = [
        topic for topic in kept_topics
        if clean_text(topic.get("headline_priority_class")) != "global_headline"
    ]
    high_fit = [topic for topic in sector_topics if clean_text(topic.get("live_snapshot_fit")) == "high_fit"]
    medium_fit = [topic for topic in sector_topics if clean_text(topic.get("live_snapshot_fit")) == "medium_fit"]
    low_fit = [topic for topic in sector_topics if clean_text(topic.get("live_snapshot_fit")) == "low_fit"]
    for topic in low_fit:
        filtered_out_topics.append(
            {
                "title": clean_text(topic.get("title")),
                "filter_reason": "deprioritized low-fit live snapshot topic",
                "total_score": safe_dict(topic.get("score_breakdown")).get("total_score", 0),
            }
        )
    ordered_global = sorted(
        global_headlines,
        key=lambda topic: int(safe_dict(topic.get("score_breakdown")).get("total_score", 0) or 0),
        reverse=True,
    )
    final_topics = []
    if ordered_global:
        ordered_global[0]["headline_priority_rank"] = 1
        final_topics.append(ordered_global[0])
    final_topics.extend(high_fit)
    final_topics.extend(medium_fit[:LIVE_SNAPSHOT_MEDIUM_FIT_LIMIT])
    return final_topics[:top_n]
```

- [ ] **Step 6: Run the red file again and verify green for the new tests**

Run:

```powershell
cmd /c ".\financial-analysis\skills\autoresearch-info-index\scripts\python-local.cmd .\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py"
```

Expected:

- the new global-headline tests now pass
- previously existing live-snapshot tests still pass

- [ ] **Step 7: Commit the runtime and test changes**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins-clean/financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py D:/Users/rickylu/dev/financial-services-plugins-clean/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "fix(autoresearch): prioritize global headlines in live snapshots"
```

### Task 3: Update Report Output To Separate The Top Headline From Sector Follow-Ups

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
- Doc: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\commands\hot-topics.md`

- [ ] **Step 1: Split report rendering into top-headline and sector-follow-up sections**

Inside the report-rendering logic, format the ranked topics as:

```python
top_headline = next(
    (topic for topic in result["ranked_topics"] if clean_text(topic.get("headline_priority_class")) == "global_headline"),
    None,
)
sector_follow_ups = [
    topic for topic in result["ranked_topics"]
    if topic is not top_headline
]
```

Render:

```python
if top_headline:
    lines.extend(
        [
            "## Top Headline Now",
            f"- Title: {clean_text(top_headline.get('title'))}",
            f"- Why rank 1: {clean_text(top_headline.get('headline_priority_reason'))}",
            f"- Market read-through: {clean_text(top_headline.get('why_now'))}",
            "",
        ]
    )

lines.append("## Best Sector Follow-Ups")
```

Then keep the existing per-topic details for `sector_follow_ups`.

- [ ] **Step 2: Document the new rule in the command doc**

Update `financial-analysis\commands\hot-topics.md` so the default selection rule reads like this:

```markdown
- when a true cross-market global headline is present, it occupies rank 1
- AI and technology relevance decide the sector follow-up layer behind the top headline
- explicit operator exclusions, such as entertainment or gossip keywords, remain hard filters
```

- [ ] **Step 3: Run the same test file to verify report formatting stays green**

Run:

```powershell
cmd /c ".\financial-analysis\skills\autoresearch-info-index\scripts\python-local.cmd .\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py"
```

Expected:

- all report-formatting assertions pass
- no existing live-snapshot test regresses

- [ ] **Step 4: Commit the report/doc refinement**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins-clean/financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py D:/Users/rickylu/dev/financial-services-plugins-clean/financial-analysis/commands/hot-topics.md D:/Users/rickylu/dev/financial-services-plugins-clean/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "docs: split hot-topics output into headline and sector layers"
```

### Task 4: Final Verification

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\autoresearch-info-index\scripts\hot_topic_discovery_runtime.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\commands\hot-topics.md`

- [ ] **Step 1: Run the live-snapshot regression file one final time**

Run:

```powershell
cmd /c ".\financial-analysis\skills\autoresearch-info-index\scripts\python-local.cmd .\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py"
```

Expected:

- PASS
- the new global-headline tests pass
- the old live-snapshot low-fit and medium-fit tests still pass

- [ ] **Step 2: Spot-check the repo command surface**

Run:

```powershell
cmd /c ".\financial-analysis\skills\autoresearch-info-index\scripts\run_hot_topic_discovery.cmd --help"
```

Expected:

- usage text prints successfully
- no wrapper regression

- [ ] **Step 3: Review git diff before merge or push**

Run:

```bash
git status --short
git diff --stat
```

Expected:

- only the runtime, tests, and command doc changed
- no `.tmp` or publish artifacts are mixed into the worktree
```

## Self-Review

- Spec coverage:
  - global headline rank-1 guarantee: covered in Task 1 tests and Task 2 ranking logic
  - live snapshot bypass rules: covered in Task 2 filter changes
  - report split into top headline and sector follow-ups: covered in Task 3
  - deterministic keyword-and-threshold design: covered in Task 2 constants and classifier helpers
- Placeholder scan:
  - no `TBD`, `TODO`, or “implement later” markers remain
  - each code-changing step includes concrete code or exact command text
- Type consistency:
  - `headline_priority_class`, `headline_priority_reason`, and `headline_priority_rank` are used consistently across tests, runtime, and report output

