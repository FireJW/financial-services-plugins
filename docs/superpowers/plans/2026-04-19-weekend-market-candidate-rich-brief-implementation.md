# Weekend Market Candidate Rich Brief Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `weekend_market_candidate` so ranked weekend directions carry explicit ranking logic, ranking reason, and key source evidence, and render them as richer Monday-prep cards without changing formal shortlist tiers.

**Architecture:** Extend the existing weekend-candidate helper contract in place with additive fields on `candidate_topics[*]`, then update markdown rendering to consume those richer fields when present and fall back cleanly when absent. Keep all changes inside the weekend-candidate helper and the report-layer renderer in `month_end_shortlist_runtime.py`; do not touch formal shortlist ranking or execution-tier logic.

**Tech Stack:** Python 3.12, existing `month-end-shortlist` runtime, existing weekend candidate helper, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
  - Add richer `candidate_topics[*]` fields:
    - `priority_rank`
    - `ranking_logic`
    - `ranking_reason`
    - `key_sources`
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - Render the richer brief structure when those fields exist
  - Preserve fallback rendering when they do not
- Modify: `tests/test_weekend_market_candidate_runtime.py`
  - Lock richer topic contract fields
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - Lock richer markdown rendering and fallback safety

### Responsibility Boundaries

- `weekend_market_candidate_runtime.py` owns all new ranking semantics and source selection.
- `month_end_shortlist_runtime.py` only renders richer fields; it must not invent ranking logic itself.
- No formal shortlist / `T1` / `T2` / `T3` mutation is allowed in this plan.

---

### Task 1: Extend Weekend Candidate Topic Contract

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
- Modify: `tests/test_weekend_market_candidate_runtime.py`

- [ ] **Step 1: Write the failing richer-contract tests**

```python
def test_build_weekend_market_candidate_adds_priority_rank_ranking_logic_and_key_sources(self) -> None:
    candidate, reference_map = module_under_test.build_weekend_market_candidate(
        {
            "x_seed_inputs": [
                {
                    "handle": "seed_one",
                    "url": "https://x.com/seed_one",
                    "display_name": "seed_one",
                    "tags": ["optical_interconnect"],
                    "candidate_names": ["中际旭创", "新易盛", "太辰光"],
                    "quality_hint": "preferred_seed",
                },
                {
                    "handle": "seed_two",
                    "url": "https://x.com/seed_two",
                    "display_name": "seed_two",
                    "tags": ["optical_interconnect"],
                    "candidate_names": ["中际旭创", "新易盛", "仕佳光子"],
                    "quality_hint": "preferred_seed",
                },
            ],
            "x_expansion_inputs": [
                {
                    "handle": "expansion_one",
                    "url": "https://x.com/expansion_one/status/1",
                    "why_included": "Confirmed the same theme",
                    "theme_overlap": ["optical_interconnect"],
                    "candidate_names": ["太辰光", "仕佳光子"],
                    "quality_hint": "theme_confirmation",
                }
            ],
            "reddit_inputs": [
                {
                    "subreddit": "stocks",
                    "thread_url": "https://reddit.com/example",
                    "thread_summary": "Photonics stayed in focus over the weekend.",
                    "direction_hint": "confirming",
                    "theme_tags": ["optical_interconnect"],
                    "quality_hint": "high_activity",
                }
            ],
        }
    )

    topic = candidate["candidate_topics"][0]
    self.assertEqual(topic["priority_rank"], 1)
    self.assertEqual(topic["ranking_logic"]["seed_alignment"], "high")
    self.assertEqual(topic["ranking_logic"]["expansion_confirmation"], "high")
    self.assertEqual(topic["ranking_logic"]["reddit_confirmation"], "high")
    self.assertEqual(topic["ranking_logic"]["noise_or_disagreement"], "low")
    self.assertIn("ranking_reason", topic)
    self.assertGreaterEqual(len(topic["key_sources"]), 2)
    self.assertIn("source_name", topic["key_sources"][0])
    self.assertIn("source_kind", topic["key_sources"][0])
    self.assertIn("url", topic["key_sources"][0])
    self.assertIn("summary", topic["key_sources"][0])
```

- [ ] **Step 2: Run the focused helper tests to verify they fail**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py -v`

Expected: FAIL because the new fields do not exist yet

- [ ] **Step 3: Write the minimal contract extension**

```python
topic = {
    "topic_name": top_topic,
    "topic_label": top_topic,
    "priority_rank": 1,
    "signal_strength": "high" if top_score >= 6 else "medium",
    "why_it_matters": "...",
    "monday_watch": f"Watch whether {top_topic} continues to lead on Monday open.",
    "ranking_logic": {
        "seed_alignment": "high" if seed_count >= 2 else "medium",
        "expansion_confirmation": "high" if expansion_count >= 1 else "low",
        "reddit_confirmation": "high" if reddit_count >= 1 else "low",
        "noise_or_disagreement": "low",
    },
    "ranking_reason": "Preferred X seeds and confirmation layers aligned most clearly on this topic, so it ranks first for Monday watch.",
    "key_sources": selected_sources,
}
```

Use simple deterministic selection:

- `seed_alignment` from preferred seed count
- `expansion_confirmation` from confirming expansion rows
- `reddit_confirmation` from Reddit confirmations
- `noise_or_disagreement` defaults to `low` unless contradictory inputs exist
- `key_sources` prefer:
  - first seed source
  - first expansion source
  - first Reddit confirmation source

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_weekend_market_candidate_runtime.py financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py
git commit -m "feat: add rich brief fields to weekend market candidate"
```

### Task 2: Render Rich Ranking Logic and Key Sources in Markdown

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Write the failing richer-markdown tests**

```python
def test_weekend_candidate_markdown_renders_ranking_logic_and_key_sources(self) -> None:
    lines = module_under_test.build_weekend_market_candidate_markdown(
        {
            "candidate_topics": [
                {
                    "topic_name": "optical_interconnect",
                    "topic_label": "光通信 / 光模块",
                    "priority_rank": 1,
                    "signal_strength": "high",
                    "why_it_matters": "Preferred X seeds aligned.",
                    "monday_watch": "Watch optics first on Monday.",
                    "ranking_logic": {
                        "seed_alignment": "high",
                        "expansion_confirmation": "high",
                        "reddit_confirmation": "high",
                        "noise_or_disagreement": "low",
                    },
                    "ranking_reason": "This direction ranks first because seed and confirmation layers aligned most cleanly.",
                    "key_sources": [
                        {
                            "source_name": "aleabitoreddit",
                            "source_kind": "x_seed",
                            "url": "https://x.com/aleabitoreddit",
                            "summary": "Continued to frame photonics as an AI bottleneck.",
                        }
                    ],
                }
            ],
            "priority_watch_directions": ["光通信 / 光模块"],
            "status": "candidate_only",
        },
        [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [{"ticker": "300308.SZ", "name": "中际旭创"}],
                "high_beta_names": [{"ticker": "300570.SZ", "name": "太辰光"}],
                "mapping_note": "Direction reference only. Not a formal execution layer.",
            }
        ],
    )
    text = "\n".join(lines)
    self.assertIn("### 排序逻辑", text)
    self.assertIn("种子共振：高", text)
    self.assertIn("扩展确认：高", text)
    self.assertIn("Reddit 验证：高", text)
    self.assertIn("分歧 / 噪音：低", text)
    self.assertIn("### 为什么排第一", text)
    self.assertIn("### 最关键 source", text)
    self.assertIn("aleabitoreddit", text)
    self.assertIn("https://x.com/aleabitoreddit", text)
```

- [ ] **Step 2: Run the degraded-reporting tests to verify they fail**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: FAIL because the markdown helper does not yet render richer ranking fields

- [ ] **Step 3: Write the minimal richer markdown rendering**

```python
if ranking_logic:
    lines.append("")
    lines.append("### 排序逻辑")
    lines.append(f"- 种子共振：{logic_label(ranking_logic.get('seed_alignment'))}")
    lines.append(f"- 扩展确认：{logic_label(ranking_logic.get('expansion_confirmation'))}")
    lines.append(f"- Reddit 验证：{logic_label(ranking_logic.get('reddit_confirmation'))}")
    lines.append(f"- 分歧 / 噪音：{logic_label(ranking_logic.get('noise_or_disagreement'))}")

if ranking_reason:
    lines.append("")
    lines.append(f"### 为什么排第{priority_rank}")
    lines.append(ranking_reason)

if key_sources:
    lines.append("")
    lines.append("### 最关键 source")
    for row in key_sources[:3]:
        lines.append(f"- `{row.get('source_name')}`")
        lines.append(f"  - 链接：{row.get('url')}")
        lines.append(f"  - 摘要：{row.get('summary')}")
```

Keep fallback behavior:

- if richer fields are missing, continue rendering the old lighter brief
- do not break existing tests that depend on the old section titles

- [ ] **Step 4: Run the degraded-reporting tests to verify they pass**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: render weekend market candidate as rich brief"
```

### Task 3: Preserve Backward Compatibility for Older Weekend Candidate Payloads

**Files:**
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Write the failing fallback-render test**

```python
def test_weekend_candidate_markdown_falls_back_when_rich_fields_are_missing(self) -> None:
    text = "\n".join(
        module_under_test.build_weekend_market_candidate_markdown(
            {
                "candidate_topics": [
                    {
                        "topic_name": "oil_shipping",
                        "topic_label": "油运",
                        "signal_strength": "high",
                        "why_it_matters": "Shipping risk remains elevated.",
                        "monday_watch": "Watch oil shipping first on Monday.",
                    }
                ],
                "priority_watch_directions": ["油运"],
                "status": "candidate_only",
            },
            [],
        )
    )
    self.assertIn("为什么重要: Shipping risk remains elevated.", text)
    self.assertNotIn("### 排序逻辑", text)
```

- [ ] **Step 2: Run the specific test to verify it fails**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py::MonthEndShortlistDegradedReportingTests::test_weekend_candidate_markdown_falls_back_when_rich_fields_are_missing -v`

Expected: FAIL if the richer renderer assumes new fields always exist

- [ ] **Step 3: Add explicit fallback guards**

```python
ranking_logic = item.get("ranking_logic") if isinstance(item.get("ranking_logic"), dict) else {}
ranking_reason = clean_text(item.get("ranking_reason"))
key_sources = item.get("key_sources") if isinstance(item.get("key_sources"), list) else []

if not ranking_logic and not ranking_reason and not key_sources:
    # existing brief behavior remains
```

- [ ] **Step 4: Run the focused compatibility tests**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "test: preserve weekend market candidate brief compatibility"
```

### Task 4: Final Focused Verification and Real Brief Refresh

**Files:**
- Modify: none required
- Test: `tests/test_weekend_market_candidate_runtime.py`
- Test: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Run the full focused verification**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v
```

Expected: all PASS

- [ ] **Step 2: Refresh the real weekend candidate briefs**

Run the same local helper flow that previously produced:

- `D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\weekend-market-candidate-actual\result.weekend-market-candidate.actual.json`
- `D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\weekend-market-candidate-actual\result.weekend-market-candidate.actual.round2.json`

Expected:

- each topic now carries:
  - `priority_rank`
  - `ranking_logic`
  - `ranking_reason`
  - `key_sources`
- regenerated markdown shows:
  - `### 排序逻辑`
  - `### 为什么排第一` / `### 为什么排第二`
  - `### 最关键 source`

- [ ] **Step 3: Inspect the refreshed brief contract**

Checklist:

- ranking logic matches the intended first-vs-second-priority explanation
- key sources include name, URL, and one-line summary
- direction reference map is still marked as reference-only
- no formal shortlist tiers changed

- [ ] **Step 4: Commit any final brief-alignment fixes**

```bash
git add tests/test_weekend_market_candidate_runtime.py tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: complete weekend market candidate rich brief upgrade"
```

---

## Self-Review

### Spec coverage

- additive contract upgrade: covered by Task 1
- `priority_rank`: covered by Task 1
- `ranking_logic`: covered by Task 1 and Task 2
- `ranking_reason`: covered by Task 1 and Task 2
- `key_sources`: covered by Task 1 and Task 2
- markdown rendering of richer brief: covered by Task 2
- backward compatibility fallback: covered by Task 3
- no execution-layer pollution: preserved by scope and verified in Task 4 inspection

### Placeholder scan

- no `TODO` / `TBD`
- all code-changing steps include concrete snippets
- commands are explicit

### Type consistency

- `priority_rank`
- `ranking_logic`
- `ranking_reason`
- `key_sources`
- `seed_alignment`
- `expansion_confirmation`
- `reddit_confirmation`
- `noise_or_disagreement`

These names are used consistently across all tasks.
