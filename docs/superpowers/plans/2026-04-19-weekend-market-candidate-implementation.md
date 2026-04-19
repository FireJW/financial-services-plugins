# Weekend Market Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an advisory weekend market candidate layer that turns weekend X-first social inputs plus Reddit confirmation into Monday watch directions and separate leader/high-beta reference maps without affecting formal shortlist tiers.

**Architecture:** Introduce a focused helper module for weekend candidate normalization and synthesis, then wire its derived outputs into `month_end_shortlist_runtime.py` as report-first advisory blocks. Keep all formal execution paths unchanged: weekend candidate data is rendered ahead of the trade plan and never auto-promotes names into formal `T1/T2/T3`.

**Tech Stack:** Python 3.12, existing `month-end-shortlist` runtime, existing `x_index` / `reddit_bridge` result contracts, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Create: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
  - Normalize `weekend_market_candidate_input`
  - Synthesize topic-level candidate output
  - Build separate `direction_reference_map`
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - Accept request passthrough
  - Attach derived weekend blocks to enriched / merged results
  - Render weekend sections ahead of formal trade-plan content
- Create: `tests/test_weekend_market_candidate_runtime.py`
  - Lock normalization, synthesis, and direction reference mapping
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
  - Lock request normalization and “no auto-overlay” behavior
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - Lock report placement and separation from formal shortlist content

### Responsibility Boundaries

- `weekend_market_candidate_runtime.py` owns all weekend-candidate-specific logic.
- `month_end_shortlist_runtime.py` only wires request/result/report integration.
- Report tests remain in `test_month_end_shortlist_degraded_reporting.py`.
- Weekend-candidate contract tests live in a new dedicated file so they do not bloat unrelated shortlist suites.

---

### Task 1: Build Weekend Candidate Helper Module

**Files:**
- Create: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
- Test: `tests/test_weekend_market_candidate_runtime.py`

- [ ] **Step 1: Write the failing normalization and synthesis tests**

```python
import importlib.util
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "financial-analysis" / "skills" / "month-end-shortlist" / "scripts" / "weekend_market_candidate_runtime.py"
SPEC = importlib.util.spec_from_file_location("weekend_market_candidate_runtime", MODULE_PATH)
module_under_test = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(module_under_test)


class WeekendMarketCandidateRuntimeTests(unittest.TestCase):
    def test_normalize_weekend_market_candidate_input_keeps_seed_expansion_and_reddit_rows(self) -> None:
        normalized = module_under_test.normalize_weekend_market_candidate_input(
            {
                "x_seed_inputs": [
                    {"handle": "tuolaji2024", "tags": ["optical"], "ignored": "drop-me"}
                ],
                "x_expansion_inputs": [
                    {"handle": "aleabitoreddit", "theme_overlap": ["optical_interconnect"]}
                ],
                "reddit_inputs": [
                    {"subreddit": "wallstreetbets", "thread_summary": "Optics supply chain still hot"}
                ],
            }
        )

        self.assertEqual(normalized["x_seed_inputs"][0]["handle"], "tuolaji2024")
        self.assertNotIn("ignored", normalized["x_seed_inputs"][0])
        self.assertEqual(normalized["x_expansion_inputs"][0]["handle"], "aleabitoreddit")
        self.assertEqual(normalized["reddit_inputs"][0]["subreddit"], "wallstreetbets")

    def test_build_weekend_market_candidate_prefers_seed_consensus_and_returns_reference_map(self) -> None:
        candidate, reference_map = module_under_test.build_weekend_market_candidate(
            {
                "x_seed_inputs": [
                    {
                        "handle": "seed_one",
                        "tags": ["optical_interconnect"],
                        "candidate_names": ["中际旭创", "新易盛", "太辰光"],
                    },
                    {
                        "handle": "seed_two",
                        "tags": ["optical_interconnect"],
                        "candidate_names": ["中际旭创", "新易盛", "仕佳光子"],
                    },
                ],
                "x_expansion_inputs": [
                    {
                        "handle": "expansion_one",
                        "theme_overlap": ["optical_interconnect"],
                        "candidate_names": ["太辰光", "仕佳光子"],
                    }
                ],
                "reddit_inputs": [
                    {
                        "subreddit": "stocks",
                        "thread_summary": "AI networking demand still supports optics",
                        "theme_tags": ["optical_interconnect"],
                        "direction_hint": "confirming",
                    }
                ],
            }
        )

        self.assertEqual(candidate["status"], "candidate_only")
        self.assertEqual(candidate["candidate_topics"][0]["topic_name"], "optical_interconnect")
        self.assertEqual(reference_map[0]["direction_key"], "optical_interconnect")
        self.assertEqual(reference_map[0]["leaders"][0]["name"], "中际旭创")
        self.assertEqual(reference_map[0]["high_beta_names"][0]["name"], "太辰光")
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py -v`

Expected: FAIL with missing module or missing functions such as `normalize_weekend_market_candidate_input`

- [ ] **Step 3: Write the minimal helper implementation**

```python
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from typing import Any


def _clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _clean_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [item for item in (_clean_text(value) for value in values) if item]


def normalize_weekend_market_candidate_input(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None

    def normalize_seed(row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        handle = _clean_text(row.get("handle"))
        if not handle:
            return None
        return {
            "handle": handle,
            "url": _clean_text(row.get("url")),
            "display_name": _clean_text(row.get("display_name")),
            "tags": _clean_list(row.get("tags")),
            "theme_aliases": deepcopy(row.get("theme_aliases")) if isinstance(row.get("theme_aliases"), dict) else {},
            "candidate_names": _clean_list(row.get("candidate_names")),
            "x_index_result_path": _clean_text(row.get("x_index_result_path")),
            "quality_hint": _clean_text(row.get("quality_hint")),
        }

    def normalize_expansion(row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        handle = _clean_text(row.get("handle"))
        if not handle:
            return None
        return {
            "handle": handle,
            "url": _clean_text(row.get("url")),
            "why_included": _clean_text(row.get("why_included")),
            "theme_overlap": _clean_list(row.get("theme_overlap")),
            "candidate_names": _clean_list(row.get("candidate_names")),
            "quality_hint": _clean_text(row.get("quality_hint")),
            "x_index_result_path": _clean_text(row.get("x_index_result_path")),
        }

    def normalize_reddit(row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        subreddit = _clean_text(row.get("subreddit"))
        summary = _clean_text(row.get("thread_summary"))
        if not subreddit and not summary:
            return None
        return {
            "subreddit": subreddit,
            "thread_url": _clean_text(row.get("thread_url")),
            "thread_summary": summary,
            "direction_hint": _clean_text(row.get("direction_hint")),
            "theme_tags": _clean_list(row.get("theme_tags")),
            "quality_hint": _clean_text(row.get("quality_hint")),
        }

    normalized = {
        "x_seed_inputs": [item for item in (normalize_seed(row) for row in raw.get("x_seed_inputs", [])) if item],
        "x_expansion_inputs": [item for item in (normalize_expansion(row) for row in raw.get("x_expansion_inputs", [])) if item],
        "reddit_inputs": [item for item in (normalize_reddit(row) for row in raw.get("reddit_inputs", [])) if item],
    }
    return normalized if any(normalized.values()) else None


def build_weekend_market_candidate(candidate_input: dict[str, Any] | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not isinstance(candidate_input, dict):
        return (
            {
                "candidate_topics": [],
                "beneficiary_chains": [],
                "headwind_chains": [],
                "priority_watch_directions": [],
                "signal_strength": "low",
                "evidence_summary": ["No usable weekend market candidate input was provided."],
                "x_seed_alignment": "none",
                "reddit_confirmation": "none",
                "status": "insufficient_signal",
            },
            [],
        )

    topic_counter: Counter[str] = Counter()
    reference_candidates: dict[str, list[str]] = {}
    for row in candidate_input.get("x_seed_inputs", []):
        for topic in row.get("tags", []):
            topic_counter[topic] += 3
            reference_candidates.setdefault(topic, []).extend(row.get("candidate_names", []))
    for row in candidate_input.get("x_expansion_inputs", []):
        for topic in row.get("theme_overlap", []):
            topic_counter[topic] += 1
            reference_candidates.setdefault(topic, []).extend(row.get("candidate_names", []))
    for row in candidate_input.get("reddit_inputs", []):
        for topic in row.get("theme_tags", []):
            topic_counter[topic] += 1

    if not topic_counter:
        return (
            {
                "candidate_topics": [],
                "beneficiary_chains": [],
                "headwind_chains": [],
                "priority_watch_directions": [],
                "signal_strength": "low",
                "evidence_summary": ["Weekend inputs did not converge on a usable A-share topic."],
                "x_seed_alignment": "low",
                "reddit_confirmation": "mixed",
                "status": "insufficient_signal",
            },
            [],
        )

    top_topic, top_score = topic_counter.most_common(1)[0]
    names = [name for name in reference_candidates.get(top_topic, []) if name]
    deduped_names = list(dict.fromkeys(names))
    leaders = deduped_names[:2]
    high_beta_names = deduped_names[2:4]

    candidate = {
        "candidate_topics": [
            {
                "topic_name": top_topic,
                "topic_label": top_topic,
                "signal_strength": "high" if top_score >= 6 else "medium",
                "why_it_matters": "Preferred X seeds converged on the same weekend topic and expansion inputs reinforced it.",
                "monday_watch": f"Watch whether {top_topic} continues to lead on Monday open.",
            }
        ],
        "beneficiary_chains": [top_topic],
        "headwind_chains": [],
        "priority_watch_directions": [top_topic],
        "signal_strength": "high" if top_score >= 6 else "medium",
        "evidence_summary": [
            "Preferred X seeds aligned on the same weekend direction.",
            "Reddit acted as confirmation instead of driving topic selection.",
        ],
        "x_seed_alignment": "high" if top_score >= 6 else "medium",
        "reddit_confirmation": "confirming",
        "status": "candidate_only",
    }
    direction_reference_map = [
        {
            "direction_key": top_topic,
            "direction_label": top_topic,
            "leaders": [{"ticker": "", "name": name} for name in leaders],
            "high_beta_names": [{"ticker": "", "name": name} for name in high_beta_names],
            "mapping_note": "Direction reference only. Not a formal execution layer.",
        }
    ]
    return candidate, direction_reference_map
```

- [ ] **Step 4: Run the helper tests to verify they pass**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_weekend_market_candidate_runtime.py financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py
git commit -m "feat: add weekend market candidate synthesis helpers"
```

### Task 2: Wire Request and Result Integration Into Shortlist Runtime

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
- Test: `tests/test_weekend_market_candidate_runtime.py`

- [ ] **Step 1: Write the failing passthrough and result attachment tests**

```python
def test_normalize_request_preserves_weekend_market_candidate_input(self) -> None:
    normalized = module_under_test.normalize_request(
        {
            "analysis_date": "2026-04-21",
            "tickers": ["000988.SZ"],
            "weekend_market_candidate_input": {
                "x_seed_inputs": [{"handle": "tuolaji2024", "tags": ["optical_interconnect"]}],
                "x_expansion_inputs": [{"handle": "aleabitoreddit", "theme_overlap": ["optical_interconnect"]}],
                "reddit_inputs": [{"subreddit": "stocks", "thread_summary": "Optics still strong"}],
            },
        }
    )

    self.assertIn("weekend_market_candidate_input", normalized)
    self.assertEqual(
        normalized["weekend_market_candidate_input"]["x_seed_inputs"][0]["handle"],
        "tuolaji2024",
    )


def test_enrich_live_result_reporting_attaches_weekend_candidate_and_reference_map(self) -> None:
    enriched = module_under_test.enrich_live_result_reporting(
        {
            "top_picks": [],
            "filter_summary": {},
            "assessed_log": [],
            "request": {
                "analysis_date": "2026-04-21",
                "weekend_market_candidate_input": {
                    "x_seed_inputs": [
                        {"handle": "seed_one", "tags": ["optical_interconnect"], "candidate_names": ["中际旭创", "新易盛", "太辰光"]}
                    ]
                },
            },
        },
        failure_candidates=[],
        assessed_candidates=[],
    )

    self.assertIn("weekend_market_candidate", enriched)
    self.assertIn("direction_reference_map", enriched)
    self.assertEqual(
        enriched["direction_reference_map"][0]["mapping_note"],
        "Direction reference only. Not a formal execution layer.",
    )
```

- [ ] **Step 2: Run the targeted integration tests to verify they fail**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v`

Expected: FAIL because `weekend_market_candidate_input` is dropped and result blocks do not exist yet

- [ ] **Step 3: Write the minimal runtime wiring**

```python
from weekend_market_candidate_runtime import (
    build_weekend_market_candidate,
    normalize_weekend_market_candidate_input,
)


def normalize_request(raw_payload: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        # existing fields...
    }

    weekend_candidate_input = normalize_weekend_market_candidate_input(
        raw_payload.get("weekend_market_candidate_input")
    )
    if weekend_candidate_input:
        normalized["weekend_market_candidate_input"] = weekend_candidate_input
    else:
        normalized.pop("weekend_market_candidate_input", None)
    return normalized


def enrich_live_result_reporting(...):
    enriched = ...
    request_obj = result.get("request", {}) if isinstance(result.get("request"), dict) else {}
    weekend_input = (
        request_obj.get("weekend_market_candidate_input")
        if isinstance(request_obj.get("weekend_market_candidate_input"), dict)
        else None
    )
    weekend_candidate, direction_reference_map = build_weekend_market_candidate(weekend_input)
    enriched["weekend_market_candidate"] = weekend_candidate
    enriched["direction_reference_map"] = direction_reference_map
    return enriched


def merge_track_results(...):
    merged = ...
    request_obj = merged.get("request", {}) if isinstance(merged.get("request"), dict) else {}
    weekend_input = (
        request_obj.get("weekend_market_candidate_input")
        if isinstance(request_obj.get("weekend_market_candidate_input"), dict)
        else None
    )
    weekend_candidate, direction_reference_map = build_weekend_market_candidate(weekend_input)
    merged["weekend_market_candidate"] = weekend_candidate
    merged["direction_reference_map"] = direction_reference_map
    return merged
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_month_end_shortlist_profile_passthrough.py tests/test_weekend_market_candidate_runtime.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: wire weekend market candidate into shortlist results"
```

### Task 3: Render Weekend Candidate Before the Formal Trade Plan

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Write the failing report placement tests**

```python
def test_report_renders_weekend_candidate_before_decision_flow(self) -> None:
    enriched = self._build_enriched_for_decision_flow()
    enriched["weekend_market_candidate"] = {
        "candidate_topics": [
            {
                "topic_name": "optical_interconnect",
                "topic_label": "光通信 / 光模块",
                "signal_strength": "high",
                "why_it_matters": "Preferred X seeds aligned.",
                "monday_watch": "Watch optics first on Monday.",
            }
        ],
        "priority_watch_directions": ["光通信 / 光模块"],
        "evidence_summary": ["Preferred X seeds converged."],
        "status": "candidate_only",
    }
    enriched["direction_reference_map"] = [
        {
            "direction_key": "optical_interconnect",
            "direction_label": "光通信 / 光模块",
            "leaders": [{"ticker": "300308.SZ", "name": "中际旭创"}],
            "high_beta_names": [{"ticker": "300570.SZ", "name": "太辰光"}],
            "mapping_note": "Direction reference only. Not a formal execution layer.",
        }
    ]

    rendered = module_under_test.enrich_live_result_reporting(enriched, failure_candidates=[])
    report = rendered["report_markdown"]

    self.assertIn("## 周末主线候选", report)
    self.assertIn("## 方向参考映射", report)
    self.assertLess(report.index("## 周末主线候选"), report.index("## 决策流"))


def test_direction_reference_map_is_marked_as_reference_only(self) -> None:
    lines = module_under_test.build_weekend_market_candidate_markdown(
        {"candidate_topics": [], "priority_watch_directions": [], "evidence_summary": [], "status": "candidate_only"},
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
    self.assertIn("Direction reference only. Not a formal execution layer.", text)
```

- [ ] **Step 2: Run the report tests to verify they fail**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: FAIL with missing `build_weekend_market_candidate_markdown` or missing report sections

- [ ] **Step 3: Write the minimal report renderer and wire it in**

```python
def build_weekend_market_candidate_markdown(
    weekend_candidate: dict[str, Any] | None,
    direction_reference_map: list[dict[str, Any]] | None,
) -> list[str]:
    if not isinstance(weekend_candidate, dict) or weekend_candidate.get("status") == "insufficient_signal":
        return []

    lines = ["", "## 周末主线候选", ""]
    for item in weekend_candidate.get("candidate_topics", []):
        lines.append(f"- `{item.get('topic_label')}` / `{item.get('signal_strength')}`")
        lines.append(f"  - 为什么重要: {item.get('why_it_matters')}")
        lines.append(f"  - 周一先看: {item.get('monday_watch')}")

    directions = weekend_candidate.get("priority_watch_directions") if isinstance(weekend_candidate.get("priority_watch_directions"), list) else []
    if directions:
        lines.extend(["", "## 周一优先盯的方向", ""])
        for direction in directions:
            lines.append(f"- {direction}")

    if isinstance(direction_reference_map, list) and direction_reference_map:
        lines.extend(["", "## 方向参考映射", ""])
        for item in direction_reference_map:
            lines.append(f"- `{item.get('direction_label')}`")
            lines.append(f"  - 龙头股: {', '.join(f\"{row.get('name')} {row.get('ticker')}\".strip() for row in item.get('leaders', [])) or 'none'}")
            lines.append(f"  - 弹性股: {', '.join(f\"{row.get('name')} {row.get('ticker')}\".strip() for row in item.get('high_beta_names', [])) or 'none'}")
            lines.append(f"  - 说明: {item.get('mapping_note')}")
    return lines


def enrich_live_result_reporting(...):
    enriched = ...
    weekend_candidate = enriched.get("weekend_market_candidate") if isinstance(enriched.get("weekend_market_candidate"), dict) else None
    direction_reference_map = enriched.get("direction_reference_map") if isinstance(enriched.get("direction_reference_map"), list) else None
    weekend_lines = build_weekend_market_candidate_markdown(weekend_candidate, direction_reference_map)
    if weekend_lines and "## 周末主线候选" not in "\n".join(lines):
        lines.extend(weekend_lines)
    if decision_flow and "## 决策流" not in "\n".join(lines):
        lines.extend(build_decision_flow_markdown(decision_flow, geopolitics_overlay, geopolitics_candidate))
```

- [ ] **Step 4: Run the report tests to verify they pass**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: render weekend market candidate ahead of trade plan"
```

### Task 4: Lock “Reference Only, No Execution Pollution” Behavior

**Files:**
- Modify: `tests/test_weekend_market_candidate_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Write the failing no-pollution tests**

```python
def test_weekend_reference_map_does_not_create_formal_tiers(self) -> None:
    result = {
        "top_picks": [],
        "filter_summary": {},
        "near_miss_candidates": [],
        "request": {
            "analysis_date": "2026-04-21",
            "weekend_market_candidate_input": {
                "x_seed_inputs": [
                    {"handle": "seed_one", "tags": ["optical_interconnect"], "candidate_names": ["中际旭创", "新易盛", "太辰光"]}
                ]
            },
        },
    }

    enriched = module_under_test.enrich_live_result_reporting(result, failure_candidates=[], assessed_candidates=[])

    self.assertEqual(enriched.get("top_picks", []), [])
    self.assertNotIn("T1", "".join(enriched.get("report_markdown", "")))
    self.assertIn("## 方向参考映射", enriched["report_markdown"])


def test_direction_reference_map_stays_separate_from_decision_flow_cards(self) -> None:
    enriched = self._build_enriched_for_decision_flow()
    enriched["direction_reference_map"] = [
        {
            "direction_key": "optical_interconnect",
            "direction_label": "光通信 / 光模块",
            "leaders": [{"ticker": "300308.SZ", "name": "中际旭创"}],
            "high_beta_names": [{"ticker": "300570.SZ", "name": "太辰光"}],
            "mapping_note": "Direction reference only. Not a formal execution layer.",
        }
    ]

    report = module_under_test.enrich_live_result_reporting(enriched, failure_candidates=[])["report_markdown"]
    self.assertIn("## 方向参考映射", report)
    self.assertIn("## 决策流", report)
    self.assertLess(report.index("## 方向参考映射"), report.index("## 决策流"))
```

- [ ] **Step 2: Run the narrow no-pollution tests to verify they fail**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: FAIL until the report ordering and non-pollution safeguards are explicit

- [ ] **Step 3: Add explicit safeguard comments / guards only if tests require them**

```python
# Weekend market candidate is advisory only. Never convert reference-map names
# into formal shortlist tiers from this path.
if weekend_candidate:
    enriched["weekend_market_candidate"] = weekend_candidate
if direction_reference_map:
    enriched["direction_reference_map"] = direction_reference_map
# No tier mutation here.
```

- [ ] **Step 4: Run the focused suite to verify the full slice passes**

Run: `py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_weekend_market_candidate_runtime.py tests/test_month_end_shortlist_degraded_reporting.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "test: lock weekend market candidate as reference-only"
```

### Task 5: Final Verification and Monday-Prep Smoke

**Files:**
- Modify: none
- Test: `tests/test_weekend_market_candidate_runtime.py`
- Test: `tests/test_month_end_shortlist_profile_passthrough.py`
- Test: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Run the full focused verification suite**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v
```

Expected: all PASS

- [ ] **Step 2: Run one smoke invocation with weekend candidate input**

Create a temporary request file by copying the existing request shape and adding a
minimal `weekend_market_candidate_input` block:

```json
{
  "analysis_date": "2026-04-21",
  "tickers": ["000988.SZ", "002384.SZ", "300476.SZ"],
  "weekend_market_candidate_input": {
    "x_seed_inputs": [
      {
        "handle": "tuolaji2024",
        "tags": ["optical_interconnect"],
        "candidate_names": ["中际旭创", "新易盛", "太辰光"]
      },
      {
        "handle": "aleabitoreddit",
        "tags": ["ai_infra"],
        "candidate_names": ["沪电股份", "胜宏科技", "深南电路"]
      }
    ],
    "x_expansion_inputs": [
      {
        "handle": "expansion_optics",
        "theme_overlap": ["optical_interconnect"],
        "candidate_names": ["仕佳光子", "太辰光"]
      }
    ],
    "reddit_inputs": [
      {
        "subreddit": "stocks",
        "thread_summary": "AI networking and optical supply chain remain in focus.",
        "theme_tags": ["optical_interconnect", "ai_infra"],
        "direction_hint": "confirming"
      }
    ]
  }
}
```

Save it to:

`D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\request.weekend-market-candidate.json`

Then run:

```bash
py D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\request.weekend-market-candidate.json --output D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\result.weekend-market-candidate.json --markdown-output D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\report.weekend-market-candidate.md
```

Expected:

- result includes `weekend_market_candidate`
- result includes `direction_reference_map`
- report renders:
  - `## 周末主线候选`
  - `## 周一优先盯的方向`
  - `## 方向参考映射`
- formal decision flow still appears after those sections

- [ ] **Step 3: Inspect the smoke report for contract compliance**

Checklist:

- `方向参考映射` contains both `龙头股` and `弹性股`
- mapping note explicitly says it is not a formal execution layer
- no reference names appear as formal `T1/T2/T3` solely because of weekend candidate data

- [ ] **Step 4: If the smoke exposes a contract mismatch, add a narrow regression before any follow-up fix**

Example:

```python
def test_smoke_contract_renders_weekend_market_candidate_sections(self) -> None:
    report = pathlib.Path("D:/Users/rickylu/dev/financial-services-plugins-clean/.tmp/next-session-2026-04-21/report.weekend-market-candidate.md").read_text(encoding="utf-8")
    self.assertIn("## 周末主线候选", report)
    self.assertIn("## 周一优先盯的方向", report)
    self.assertIn("## 方向参考映射", report)
```

If the smoke already matches the contract, skip this step.

---

## Self-Review

### Spec coverage

- input contract: covered by Task 1 and Task 2
- X seed priority and one-layer expansion: covered by Task 1 synthesis tests and implementation
- Reddit as supplement only: covered by Task 1 and Task 4 no-pollution tests
- `weekend_market_candidate` + `direction_reference_map` contracts: covered by Task 1 and Task 2
- report placement before formal trade plan: covered by Task 3
- no automatic execution-tier mutation: covered by Task 4

### Placeholder scan

- no `TODO` / `TBD`
- each code-changing step includes concrete test or implementation snippets
- commands are explicit

### Type consistency

- `weekend_market_candidate_input`
- `weekend_market_candidate`
- `direction_reference_map`
- `build_weekend_market_candidate`
- `build_weekend_market_candidate_markdown`

These names are used consistently across the plan.
