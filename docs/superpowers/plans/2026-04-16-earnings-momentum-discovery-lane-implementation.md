# Earnings-Momentum Discovery Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a wrapper-level earnings/expectation-change discovery lane that can reverse-inject event-driven names into the trading plan, render `直接可执行 / 重点观察 / 链条跟踪`, and preserve existing shortlist behavior when no discovery inputs are supplied.

**Architecture:** Keep the compiled shortlist core unchanged. Add a new pure-Python discovery helper module under the `month-end-shortlist` wrapper, then integrate it into `month_end_shortlist_runtime.py` and the markdown/reporting layer. Accept normalized event candidates from request payloads rather than trying to fully automate external ingestion in Phase 1.

**Tech Stack:** Python 3.12, wrapper module `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`, new helper module under the same script folder, pytest/unittest.

---

### Task 1: Add Pure Discovery Lane Helper With TDD

**Files:**
- Create: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\financial-analysis\skills\month-end-shortlist\scripts\earnings_momentum_discovery.py`
- Create: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_earnings_momentum_discovery.py`

- [ ] **Step 1: Write the failing tests for normalization, rumor scoring, market validation, and bucket assignment**

Add this test file:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import earnings_momentum_discovery as module_under_test


class EarningsMomentumDiscoveryTests(unittest.TestCase):
    def test_normalize_event_candidate_preserves_upstream_chain_metadata(self) -> None:
        candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "002463.SZ",
                "name": "沪电股份",
                "event_type": "price_hike",
                "event_strength": "strong",
                "chain_name": "pcb",
                "chain_role": "upstream_material",
                "benefit_type": "direct",
                "sources": [
                    {"source_type": "x_summary", "account": "Ariston_Macro", "summary": "PCB 上游材料/电子布涨价弹性更强"}
                ],
            }
        )

        self.assertEqual(candidate["ticker"], "002463.SZ")
        self.assertEqual(candidate["chain_name"], "pcb")
        self.assertEqual(candidate["chain_role"], "upstream_material")
        self.assertEqual(candidate["benefit_type"], "direct")
        self.assertEqual(candidate["source_roles"], ["summary_or_relay"])

    def test_compute_rumor_confidence_range_distinguishes_confirmed_vs_rumor_only(self) -> None:
        rumor_only = module_under_test.normalize_event_candidate(
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "medium",
                "sources": [{"source_type": "market_rumor", "summary": "存在订单/合作传闻"}],
                "market_validation": {"volume_multiple_5d": 2.2, "breakout": True, "relative_strength": "strong"},
            }
        )
        confirmed = module_under_test.normalize_event_candidate(
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "sources": [
                    {"source_type": "official_filing", "summary": "一季报预告大幅增长"},
                    {"source_type": "company_response", "summary": "公司公告确认最新业绩预增"},
                ],
                "market_validation": {"volume_multiple_5d": 1.9, "breakout": True, "relative_strength": "strong"},
            }
        )

        rumor_range = module_under_test.compute_rumor_confidence_range(rumor_only)
        confirmed_range = module_under_test.compute_rumor_confidence_range(confirmed)

        self.assertEqual(rumor_range["label"], "medium")
        self.assertEqual(confirmed_range["label"], "high")

    def test_classify_market_validation_labels_strong_funds_entered_early(self) -> None:
        candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "300857.SZ",
                "name": "协创数据",
                "event_type": "large_order",
                "event_strength": "strong",
                "market_validation": {
                    "volume_multiple_5d": 2.4,
                    "breakout": True,
                    "relative_strength": "strong",
                    "chain_resonance": True,
                },
            }
        )

        validation = module_under_test.classify_market_validation(candidate)

        self.assertEqual(validation["label"], "strong")
        self.assertIn("资金先行", validation["summary"])

    def test_assign_discovery_bucket_keeps_rumor_only_names_out_of_qualified(self) -> None:
        rumor_candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "strong",
                "sources": [{"source_type": "market_rumor", "summary": "传闻发酵"}],
                "market_validation": {"volume_multiple_5d": 2.5, "breakout": True, "relative_strength": "strong"},
            }
        )
        confirmed_candidate = module_under_test.normalize_event_candidate(
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "sources": [{"source_type": "official_filing", "summary": "正式业绩预告"}],
                "market_validation": {"volume_multiple_5d": 2.0, "breakout": True, "relative_strength": "strong"},
            }
        )

        rumor_bucket = module_under_test.assign_discovery_bucket(rumor_candidate)
        confirmed_bucket = module_under_test.assign_discovery_bucket(confirmed_candidate)

        self.assertEqual(rumor_bucket, "watch")
        self.assertEqual(confirmed_bucket, "qualified")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test file and confirm RED**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_earnings_momentum_discovery.py' -q
```

Expected: FAIL with `ModuleNotFoundError` for `earnings_momentum_discovery` or missing attributes.

- [ ] **Step 3: Create the minimal helper module**

Create this file:

```python
#!/usr/bin/env python3
from __future__ import annotations

from copy import deepcopy
from typing import Any


SOURCE_ROLE_MAP = {
    "official_filing": "official_filing_reference",
    "company_response": "company_response_reference",
    "x_summary": "summary_or_relay",
    "x_thread": "personal_thesis",
    "market_rumor": "market_rumor",
}


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def normalize_source_role(source_type: str) -> str:
    return SOURCE_ROLE_MAP.get(clean_text(source_type), "personal_thesis")


def normalize_event_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    sources = deepcopy(raw.get("sources") or [])
    candidate = {
        "ticker": clean_text(raw.get("ticker")),
        "name": clean_text(raw.get("name")) or clean_text(raw.get("ticker")),
        "event_type": clean_text(raw.get("event_type")),
        "event_strength": clean_text(raw.get("event_strength")) or "medium",
        "chain_name": clean_text(raw.get("chain_name")),
        "chain_role": clean_text(raw.get("chain_role")) or "unknown",
        "benefit_type": clean_text(raw.get("benefit_type")) or "mapping",
        "sources": sources,
        "source_roles": [normalize_source_role(item.get("source_type")) for item in sources if isinstance(item, dict)],
        "market_validation": deepcopy(raw.get("market_validation") or {}),
    }
    return candidate


def compute_rumor_confidence_range(candidate: dict[str, Any]) -> dict[str, Any]:
    roles = set(candidate.get("source_roles") or [])
    if "official_filing_reference" in roles or "company_response_reference" in roles:
        return {"label": "high", "range": [80, 90]}
    if "market_rumor" in roles:
        return {"label": "medium", "range": [40, 65]}
    return {"label": "low", "range": [20, 40]}


def classify_market_validation(candidate: dict[str, Any]) -> dict[str, Any]:
    data = candidate.get("market_validation") if isinstance(candidate.get("market_validation"), dict) else {}
    score = 0
    if float(data.get("volume_multiple_5d") or 0) >= 2.0:
        score += 1
    if bool(data.get("breakout")):
        score += 1
    if clean_text(data.get("relative_strength")).lower() == "strong":
        score += 1
    if bool(data.get("chain_resonance")):
        score += 1
    if score >= 3:
        return {"label": "strong", "summary": "强资金先行，存在提前进场迹象。"}
    if score >= 2:
        return {"label": "medium", "summary": "中等资金先行，已有部分提前验证。"}
    return {"label": "weak", "summary": "弱资金先行，仍需更多量价确认。"}


def assign_discovery_bucket(candidate: dict[str, Any]) -> str:
    confidence = compute_rumor_confidence_range(candidate)
    validation = classify_market_validation(candidate)
    if candidate.get("event_type") == "rumor":
        return "watch"
    if clean_text(candidate.get("event_strength")).lower() == "strong" and validation["label"] == "strong" and confidence["label"] in {"medium", "high"}:
        return "qualified"
    return "watch"
```

- [ ] **Step 4: Run the helper test file and confirm GREEN**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_earnings_momentum_discovery.py' -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit the helper module and tests**

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup' add `
  'financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py' `
  'tests/test_earnings_momentum_discovery.py'
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup' commit -m "feat: add earnings momentum discovery helpers"
```


### Task 2: Merge Discovery Candidates Into Wrapper Results

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_discovery_merge.py`

- [ ] **Step 1: Write failing merge tests**

Create this file:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import month_end_shortlist_runtime as module_under_test


class MonthEndShortlistDiscoveryMergeTests(unittest.TestCase):
    def test_enrich_live_result_reporting_injects_discovery_qualified_and_watch_buckets(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 58.0},
            "top_picks": [],
            "dropped": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
        }
        discovery_candidates = [
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "chain_name": "optical",
                "chain_role": "midstream_manufacturing",
                "benefit_type": "direct",
                "sources": [{"source_type": "official_filing", "summary": "正式业绩预告"}],
                "market_validation": {"volume_multiple_5d": 2.0, "breakout": True, "relative_strength": "strong"},
            },
            {
                "ticker": "688521.SS",
                "name": "芯原股份",
                "event_type": "rumor",
                "event_strength": "strong",
                "chain_name": "chip_design",
                "chain_role": "midstream_manufacturing",
                "benefit_type": "direct",
                "sources": [{"source_type": "market_rumor", "summary": "市场传闻"}],
                "market_validation": {"volume_multiple_5d": 2.4, "breakout": True, "relative_strength": "strong"},
            },
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], [], discovery_candidates)

        self.assertEqual(enriched["discovery_lane_summary"]["qualified_count"], 1)
        self.assertEqual(enriched["discovery_lane_summary"]["watch_count"], 1)
        self.assertEqual(enriched["directly_actionable"][0]["ticker"], "000988.SZ")
        self.assertEqual(enriched["priority_watchlist"][0]["ticker"], "688521.SS")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the merge test file and confirm RED**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_discovery_merge.py' -q
```

Expected: FAIL because `enrich_live_result_reporting` does not yet accept or merge discovery candidates.

- [ ] **Step 3: Add discovery merge helpers to the runtime**

Add these imports and helpers to `month_end_shortlist_runtime.py`:

```python
from earnings_momentum_discovery import (
    assign_discovery_bucket,
    classify_market_validation,
    compute_rumor_confidence_range,
    normalize_event_candidate,
)


def build_discovery_lane_summary(discovery_rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"qualified_count": 0, "watch_count": 0, "track_count": 0}
    for item in discovery_rows:
        bucket = clean_text(item.get("discovery_bucket"))
        if bucket == "qualified":
            summary["qualified_count"] += 1
        elif bucket == "watch":
            summary["watch_count"] += 1
        else:
            summary["track_count"] += 1
    return summary


def build_discovery_candidates(raw_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in raw_candidates:
        if not isinstance(raw, dict):
            continue
        item = normalize_event_candidate(raw)
        item["rumor_confidence_range"] = compute_rumor_confidence_range(item)
        item["market_validation_summary"] = classify_market_validation(item)
        item["discovery_bucket"] = assign_discovery_bucket(item)
        rows.append(item)
    return rows
```

Then extend `enrich_live_result_reporting(...)` signature to accept `discovery_candidates: list[dict[str, Any]] | None = None` and merge them:

```python
discovery_rows = build_discovery_candidates(discovery_candidates or [])
if discovery_rows:
    enriched["discovery_lane_summary"] = build_discovery_lane_summary(discovery_rows)
    enriched["directly_actionable"] = [row for row in discovery_rows if row.get("discovery_bucket") == "qualified"][:MAX_REPORTED_TOP_PICKS]
    enriched["priority_watchlist"] = [row for row in discovery_rows if row.get("discovery_bucket") == "watch"][:MAX_REPORTED_NEAR_MISS]
    enriched["chain_tracking"] = [row for row in discovery_rows if row.get("discovery_bucket") not in {"qualified", "watch"}][:MAX_REPORTED_BLOCKED]
```

- [ ] **Step 4: Run the merge test file and confirm GREEN**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_discovery_merge.py' -q
```

Expected: PASS.

- [ ] **Step 5: Commit merge-layer changes**

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup' add `
  'financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py' `
  'tests/test_month_end_shortlist_discovery_merge.py'
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup' commit -m "feat: merge discovery lane into shortlist results"
```


### Task 3: Render Event Board, Chain Map, and New Decision Buckets

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Add failing report-format tests**

Append tests like this to `test_month_end_shortlist_degraded_reporting.py`:

```python
    def test_enrich_live_result_reporting_renders_event_board_and_chain_map(self) -> None:
        result = {
            "filter_summary": {"kept_count": 0, "keep_threshold": 58.0},
            "dropped": [],
            "top_picks": [],
            "report_markdown": "# Month-End Shortlist Report: 2026-04-17\n",
        }
        discovery_candidates = [
            {
                "ticker": "000988.SZ",
                "name": "华工科技",
                "event_type": "quarterly_preview",
                "event_strength": "strong",
                "chain_name": "optical",
                "chain_role": "midstream_manufacturing",
                "benefit_type": "direct",
                "sources": [{"source_type": "official_filing", "summary": "正式业绩预告"}],
                "market_validation": {"volume_multiple_5d": 2.0, "breakout": True, "relative_strength": "strong"},
            }
        ]

        enriched = module_under_test.enrich_live_result_reporting(result, [], [], discovery_candidates)

        self.assertIn("## 直接可执行", enriched["report_markdown"])
        self.assertIn("## Event Board", enriched["report_markdown"])
        self.assertIn("## Chain Map", enriched["report_markdown"])
        self.assertIn("华工科技", enriched["report_markdown"])
        self.assertIn("optical", enriched["report_markdown"])
```

- [ ] **Step 2: Run the reporting test file and confirm RED**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected: FAIL because the new sections are not rendered yet.

- [ ] **Step 3: Add markdown rendering for the discovery outputs**

Extend the markdown section builder in `enrich_live_result_reporting(...)` with additive sections:

```python
    directly_actionable = enriched.get("directly_actionable", [])
    if isinstance(directly_actionable, list) and directly_actionable and "## 直接可执行" not in "\n".join(lines):
        lines.extend(["", "## 直接可执行", ""])
        for item in directly_actionable:
            lines.append(f"- `{item.get('ticker')}` {item.get('name')}")
            lines.append(f"  - 事件: `{item.get('event_type')}`")
            lines.append(f"  - 链条: `{item.get('chain_name')}` / `{item.get('chain_role')}`")
            lines.append(f"  - 市场验证: {item.get('market_validation_summary', {}).get('summary')}")

    priority_watchlist = enriched.get("priority_watchlist", [])
    if isinstance(priority_watchlist, list) and priority_watchlist and "## 重点观察" not in "\n".join(lines):
        lines.extend(["", "## 重点观察", ""])
        for item in priority_watchlist:
            confidence = item.get("rumor_confidence_range", {})
            lines.append(f"- `{item.get('ticker')}` {item.get('name')}")
            lines.append(f"  - 事件: `{item.get('event_type')}`")
            lines.append(f"  - 可信度区间: `{confidence.get('label')}` `{confidence.get('range')}`")

    chain_tracking = enriched.get("chain_tracking", [])
    if isinstance(chain_tracking, list) and chain_tracking and "## 链条跟踪" not in "\n".join(lines):
        lines.extend(["", "## 链条跟踪", ""])
        for item in chain_tracking:
            lines.append(f"- `{item.get('ticker')}` {item.get('name')}: `{item.get('chain_name')}` / `{item.get('chain_role')}`")

    if enriched.get("discovery_lane_summary") and "## Event Board" not in "\n".join(lines):
        lines.extend(["", "## Event Board", ""])
        for item in enriched.get("directly_actionable", []) + enriched.get("priority_watchlist", []) + enriched.get("chain_tracking", []):
            lines.append(f"- `{item.get('event_type')}` -> `{item.get('ticker')}` {item.get('name')}")

    if enriched.get("discovery_lane_summary") and "## Chain Map" not in "\n".join(lines):
        lines.extend(["", "## Chain Map", ""])
        for item in enriched.get("directly_actionable", []) + enriched.get("priority_watchlist", []) + enriched.get("chain_tracking", []):
            lines.append(f"- `{item.get('chain_name')}` / `{item.get('chain_role')}` -> `{item.get('ticker')}` {item.get('name')}")
```

- [ ] **Step 4: Re-run the reporting test file and confirm GREEN**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_degraded_reporting.py' -q
```

Expected: PASS.

- [ ] **Step 5: Commit the reporting changes**

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup' add `
  'financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py' `
  'tests/test_month_end_shortlist_degraded_reporting.py'
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup' commit -m "feat: render discovery event board and chain map"
```


### Task 4: Add Example Request and End-to-End Wrapper Verification

**Files:**
- Create: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\financial-analysis\skills\month-end-shortlist\examples\month-end-shortlist-earnings-momentum.template.json`
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\docs\superpowers\notes\2026-04-16-next-session-plan-2026-04-17.md`

- [ ] **Step 1: Add a minimal discovery-lane example request**

Create:

```json
{
  "template_name": "month_end_shortlist",
  "target_date": "2026-04-17",
  "filter_profile": "month_end_event_support_transition",
  "event_discovery_candidates": [
    {
      "ticker": "000988.SZ",
      "name": "华工科技",
      "event_type": "quarterly_preview",
      "event_strength": "strong",
      "chain_name": "optical",
      "chain_role": "midstream_manufacturing",
      "benefit_type": "direct",
      "sources": [
        {
          "source_type": "official_filing",
          "summary": "一季报预告显示利润显著增长"
        },
        {
          "source_type": "x_summary",
          "account": "Ariston_Macro",
          "summary": "市场把这次预告理解成板块盈利预期修复信号"
        }
      ],
      "market_validation": {
        "volume_multiple_5d": 2.0,
        "breakout": true,
        "relative_strength": "strong",
        "chain_resonance": true
      }
    }
  ]
}
```

- [ ] **Step 2: Run the full focused regression**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_earnings_momentum_discovery.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_discovery_merge.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_profile_passthrough.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_degraded_reporting.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_candidate_snapshot_enrichment.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_candidate_fetch_fallback.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_benchmark_fallback.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\tests\test_month_end_shortlist_shim.py' -q
```

Expected: all pass.

- [ ] **Step 3: Run an end-to-end example through the CLI**

Run:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py' `
  'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\financial-analysis\skills\month-end-shortlist\examples\month-end-shortlist-earnings-momentum.template.json' `
  --output 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\.tmp\earnings-momentum-example\result.json' `
  --markdown-output 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup\.tmp\earnings-momentum-example\report.md'
```

Expected:

- CLI succeeds
- result contains discovery-lane fields
- markdown contains:
  - `## 直接可执行` or `## 重点观察`
  - `## Event Board`
  - `## Chain Map`

- [ ] **Step 4: Update the next-session note with the new lane**

Append a short section to `2026-04-16-next-session-plan-2026-04-17.md` noting:

- discovery lane now exists
- event-driven reverse injection is supported
- future follow-up should wire live event ingestion into the new normalized field
  instead of hand-writing event candidates

- [ ] **Step 5: Commit the example + verification note**

```powershell
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup' add `
  'financial-analysis/skills/month-end-shortlist/examples/month-end-shortlist-earnings-momentum.template.json' `
  'docs/superpowers/notes/2026-04-16-next-session-plan-2026-04-17.md'
git -C 'D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-codex-plan-followup' commit -m "docs: add earnings momentum discovery example"
```
