# Trading System Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix crash paths, tighten trading-profile classification boundaries, add missing 兑现风险 scenario, reorganize Event Board layout, and improve Chain Map expansion quality — all at the wrapper/reporting layer.

**Architecture:** Five sequential slices (B1→B5) modifying two files: `earnings_momentum_discovery.py` (classification engine) and `month_end_shortlist_runtime.py` (reporting/chain map). Each slice adds tests first, then implementation, then commits. No compiled shortlist core changes.

**Tech Stack:** Python 3, unittest, existing helpers (`clean_text`, `to_float`, `classify_*`)

**Key Paths:**
- Source A: `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py`
- Source B: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Test A: `tests/test_earnings_momentum_discovery.py`
- Test B: `tests/test_month_end_shortlist_degraded_reporting.py`

---

### Task 1: B1 — Fix Crash Path (safe int/float conversions)

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py:0-5,78-82,216,296-298,435-448,665-666,732,738-742,808`
- Test: `tests/test_earnings_momentum_discovery.py`

**Context:** `int(candidate.get("priority_score") or 0)` crashes on truthy non-numeric strings like `"-"` or `"N/A"` because the `or 0` guard only catches falsy values. The file `month_end_shortlist_runtime.py` already has a `to_float()` helper (line 372-376) but `earnings_momentum_discovery.py` uses raw `float()` at 7 locations.

- [ ] **Step 1: Write failing test for `to_int_safe`**

Add at the end of the existing test class in `tests/test_earnings_momentum_discovery.py`:

```python
def test_to_int_safe_handles_non_numeric_strings(self) -> None:
    self.assertEqual(module_under_test.to_int_safe(42), 42)
    self.assertEqual(module_under_test.to_int_safe("85"), 85)
    self.assertEqual(module_under_test.to_int_safe("-"), 0)
    self.assertEqual(module_under_test.to_int_safe("N/A"), 0)
    self.assertEqual(module_under_test.to_int_safe(None), 0)
    self.assertEqual(module_under_test.to_int_safe("", default=5), 5)
    self.assertEqual(module_under_test.to_int_safe(0), 0)

def test_to_float_safe_handles_non_numeric_strings(self) -> None:
    self.assertAlmostEqual(module_under_test.to_float_safe(1.5), 1.5)
    self.assertAlmostEqual(module_under_test.to_float_safe("2.0"), 2.0)
    self.assertAlmostEqual(module_under_test.to_float_safe("-"), 0.0)
    self.assertAlmostEqual(module_under_test.to_float_safe("N/A"), 0.0)
    self.assertAlmostEqual(module_under_test.to_float_safe(None), 0.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py::TestEarningsMomentumDiscovery::test_to_int_safe_handles_non_numeric_strings -v`
Expected: FAIL — `module_under_test` has no attribute `to_int_safe`

- [ ] **Step 3: Add `to_int_safe` and `to_float_safe` helpers**

In `earnings_momentum_discovery.py`, after the `clean_text` function (after line 37), add:

```python
def to_int_safe(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float_safe(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 4: Replace all raw `float()` calls in `earnings_momentum_discovery.py`**

Replace each raw `float()` with `to_float_safe()`:

Line 81 in `classify_market_validation`:
```python
# OLD:
if float(data.get("volume_multiple_5d") or 0) >= 1.5:
# NEW:
if to_float_safe(data.get("volume_multiple_5d")) >= 1.5:
```

Line 298 in `build_market_signal_summary`:
```python
# OLD:
volume_multiple = float(data.get("volume_multiple_5d") or 0.0)
# NEW:
volume_multiple = to_float_safe(data.get("volume_multiple_5d"))
```

Line 666 in `build_event_cards` (merged_validation):
```python
# OLD:
merged_validation["volume_multiple_5d"] = max(float(merged_validation.get("volume_multiple_5d") or 0), float(validation.get("volume_multiple_5d") or 0))
# NEW:
merged_validation["volume_multiple_5d"] = max(to_float_safe(merged_validation.get("volume_multiple_5d")), to_float_safe(validation.get("volume_multiple_5d")))
```

Lines 739-742 in `build_market_validation_from_shortlist_candidate`:
```python
# OLD:
rs90 = float(price_snapshot.get("rs90") or 0)
distance_to_high = float(price_snapshot.get("distance_to_high52_pct") or 1000)
return {
    "volume_multiple_5d": float(candidate.get("volume_ratio") or 0),
# NEW:
rs90 = to_float_safe(price_snapshot.get("rs90"))
distance_to_high = to_float_safe(price_snapshot.get("distance_to_high52_pct"), default=1000.0)
return {
    "volume_multiple_5d": to_float_safe(candidate.get("volume_ratio")),
```

Line 808 in `build_auto_discovery_candidates`:
```python
# OLD:
"event_strength": "strong" if float((candidate.get("score_components") or {}).get("structured_catalyst_score") or 0) >= 12 else "medium",
# NEW:
"event_strength": "strong" if to_float_safe((candidate.get("score_components") or {}).get("structured_catalyst_score")) >= 12 else "medium",
```

- [ ] **Step 5: Replace `int()` with `to_int_safe` in `classify_trading_profile`**

Line 448:
```python
# OLD:
priority_score = int(candidate.get("priority_score") or 0)
# NEW:
priority_score = to_int_safe(candidate.get("priority_score"))
```

Line 732 in `build_event_cards` sort key:
```python
# OLD:
cards.sort(key=lambda item: (-int(item.get("priority_score") or 0), ...))
# NEW:
cards.sort(key=lambda item: (-to_int_safe(item.get("priority_score")), ...))
```

- [ ] **Step 6: Run all tests**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py tests/test_month_end_shortlist_degraded_reporting.py tests/test_x_style_assisted_shortlist.py tests/test_month_end_shortlist_discovery_merge.py -v`
Expected: All pass (47 existing + 2 new = 49)

- [ ] **Step 7: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py tests/test_earnings_momentum_discovery.py
git commit -m "fix: replace raw int/float with safe helpers in earnings_momentum_discovery"
```

---

### Task 2: B2 — Tighten `classify_trading_profile` Fallback Chain

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py:486-547`
- Test: `tests/test_earnings_momentum_discovery.py`

**Context:** The current 9-path if-elif tree in `classify_trading_profile` (lines 435-547) has a catch-all at lines 536-547 that dumps >50% of names into 预期差最大. Three independent conditions each catch huge swaths: `community_conviction == "low"` (all auto-discovered names without X commentary), `expectation_verdict == "暂无一致预期"` (default for names without consensus), and paradoxically `expectation_verdict == "市场押注超预期"`. This task applies 5 fixes from the spec.

- [ ] **Step 1: Write failing tests for the new classification boundaries**

Add to the test class in `tests/test_earnings_momentum_discovery.py`:

```python
def test_classify_trading_profile_market_bet_outperform_routes_to_elastic_not_gap(self) -> None:
    """Fix 1: 市场押注超预期 with weak validation should go to 高弹性, not 预期差最大."""
    profile = module_under_test.classify_trading_profile(
        {
            "name": "TestName",
            "benefit_type": "direct",
            "chain_role": "unknown",
            "leaders": [],
            "peer_tier_1": [],
            "peer_tier_2": [],
            "event_phase": "预期交易",
            "event_state": {"label": "unconfirmed"},
            "trading_usability": {"label": "low", "summary": "低"},
            "market_validation_summary": {"label": "weak", "summary": "弱"},
            "expectation_verdict": "市场押注超预期",
            "community_conviction": "low",
            "priority_score": 50,
        }
    )
    self.assertNotEqual(profile["bucket"], "预期差最大")

def test_classify_trading_profile_low_conviction_alone_not_gap(self) -> None:
    """Fix 2: community_conviction == low alone should not trigger 预期差最大."""
    profile = module_under_test.classify_trading_profile(
        {
            "name": "TestName2",
            "benefit_type": "direct",
            "chain_role": "unknown",
            "leaders": [],
            "peer_tier_1": [],
            "peer_tier_2": [],
            "event_phase": "预期交易",
            "event_state": {"label": "unconfirmed"},
            "trading_usability": {"label": "low", "summary": "低"},
            "market_validation_summary": {"label": "medium", "summary": "中等"},
            "expectation_verdict": "符合预期",
            "community_conviction": "low",
            "priority_score": 40,
        }
    )
    self.assertNotEqual(profile["bucket"], "预期差最大")

def test_classify_trading_profile_mapping_strong_validation_routes_to_elastic(self) -> None:
    """Fix 4: mapping + strong validation + high usability → 高弹性, not 补涨候选."""
    profile = module_under_test.classify_trading_profile(
        {
            "name": "MappingStrong",
            "benefit_type": "mapping",
            "chain_role": "midstream_manufacturing",
            "leaders": [],
            "peer_tier_1": [],
            "peer_tier_2": [],
            "event_phase": "预期交易",
            "event_state": {"label": "unconfirmed"},
            "trading_usability": {"label": "high", "summary": "高"},
            "market_validation_summary": {"label": "strong", "summary": "强"},
            "expectation_verdict": "市场押注超预期",
            "community_conviction": "medium",
            "priority_score": 70,
        }
    )
    self.assertEqual(profile["bucket"], "高弹性")
    self.assertIn("映射", profile["subtype"])

def test_classify_trading_profile_final_fallback_is_catchup_not_gap(self) -> None:
    """Fix 5: final fallback with weak validation → 补涨候选, not 预期差最大."""
    profile = module_under_test.classify_trading_profile(
        {
            "name": "FallbackName",
            "benefit_type": "direct",
            "chain_role": "unknown",
            "leaders": [],
            "peer_tier_1": [],
            "peer_tier_2": [],
            "event_phase": "预期交易",
            "event_state": {"label": "unconfirmed"},
            "trading_usability": {"label": "low", "summary": "低"},
            "market_validation_summary": {"label": "weak", "summary": "弱"},
            "expectation_verdict": "符合预期",
            "community_conviction": "medium",
            "priority_score": 30,
        }
    )
    self.assertEqual(profile["bucket"], "补涨候选")
    self.assertIn("证据不足", profile["subtype"])

def test_classify_trading_profile_genuine_gap_has_evidence_strength(self) -> None:
    """Fix 3: genuine 预期差最大 entries carry evidence_strength marker."""
    profile = module_under_test.classify_trading_profile(
        {
            "name": "GapName",
            "benefit_type": "direct",
            "chain_role": "unknown",
            "leaders": [],
            "peer_tier_1": [],
            "peer_tier_2": [],
            "event_phase": "预期交易",
            "event_state": {"label": "unconfirmed"},
            "trading_usability": {"label": "low", "summary": "低"},
            "market_validation_summary": {"label": "weak", "summary": "弱"},
            "expectation_verdict": "暂无一致预期",
            "community_conviction": "low",
            "priority_score": 30,
        }
    )
    self.assertEqual(profile["bucket"], "预期差最大")
    self.assertIn("evidence_strength", profile)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py -k "market_bet_outperform or low_conviction_alone or mapping_strong_validation or final_fallback_is_catchup or genuine_gap_has_evidence" -v`
Expected: 5 FAIL

- [ ] **Step 3: Rewrite the classification paths (lines 512-547)**

Replace the entire block from the current Path 6 (line 512) through the final return (line 547) with the new logic. The full replacement in `earnings_momentum_discovery.py`:

```python
    # --- Path 6: mapping with strong validation → 高弹性 (new, before old Path 6) ---
    if (
        benefit_type == "mapping"
        and market_validation in {"strong", "medium"}
        and trading_usability in {"high", "medium"}
        and not is_secondary_name
        and chain_role not in {"logic_support", "quote_only"}
    ):
        return {
            "bucket": "高弹性",
            "subtype": "映射受益但验证充分的弹性表达",
            "reason": "虽然属于映射受益，但量价验证和交易可用性已经足够，更像高弹性表达。",
        }

    # --- Path 7: secondary / weak-mapping / logic_support → 补涨候选 ---
    if is_secondary_name or benefit_type == "mapping" or chain_role in {"logic_support", "quote_only"}:
        subtype = "链条扩散补涨"
        if is_core_name:
            subtype = "核心后的轮动补涨"
        return {
            "bucket": "补涨候选",
            "subtype": subtype,
            "reason": "更偏链条扩散或映射受益，当前更适合作为补涨候选跟踪。",
        }

    # --- Path 8: non-core direct with validation → 高弹性 ---
    if (
        benefit_type == "direct"
        and not is_core_name
        and not is_secondary_name
        and market_validation in {"strong", "medium"}
        and trading_usability in {"high", "medium"}
    ):
        subtype = "事件确认后攻击性弹性" if event_phase in {"正式结果", "官方预告"} else "预期博弈型弹性"
        return {
            "bucket": "高弹性",
            "subtype": subtype,
            "reason": "不是最稳的链条核心，但事件和量价都已具备交易性，更像高弹性表达。",
        }

    # --- Path 9: tightened 预期差最大 (all three conditions must hold) ---
    if (
        community_conviction == "low"
        and expectation_verdict == "暂无一致预期"
        and market_validation not in {"strong", "medium"}
    ):
        has_positive_signal = expectation_verdict != "暂无一致预期" or community_conviction != "low"
        evidence = "genuine_gap" if has_positive_signal else "weak_evidence"
        return {
            "bucket": "预期差最大",
            "subtype": "预期尚未充分定价",
            "reason": "市场一致预期尚未完全收敛，当前更像预期差最大的博弈方向。",
            "evidence_strength": evidence,
        }

    # --- Path 10: final fallback → 高弹性 (strong) or 补涨候选 (default) ---
    if market_validation == "strong":
        return {
            "bucket": "高弹性",
            "subtype": "事件确认后攻击性弹性",
            "reason": "当前更适合按弹性表达理解，而不是按静态行业位次理解。",
        }
    return {
        "bucket": "补涨候选",
        "subtype": "证据不足的扩散候选",
        "reason": "当前证据不足以归入更强的交易属性分类，先按补涨候选跟踪。",
    }
```

**Important:** The old code from line 512 to line 547 is completely replaced. Lines 452-511 (Paths 1-5: response_denied, two 兑现风险 paths, 稳健核心, 高弹性 core aggressive) remain unchanged.

- [ ] **Step 4: Update existing test assertions that depend on old boundaries**

The existing test case for `新易盛` (elastic_leader_profile) currently expects `高弹性` — it has `benefit_type="mapping"` + `chain_role="logic_support"` + `is_core_name=True`. Under the new logic, Path 6 (mapping + strong/medium validation) checks `chain_role not in {"logic_support", "quote_only"}`, so `新易盛` will fall through to Path 7 (补涨候选) with subtype `核心后的轮动补涨`.

However, `新易盛` also matches Path 5 (core + non-direct + 预期交易 + 市场押注超预期 + medium usability) at line 499-510, which returns `高弹性` with subtype `核心链条攻击性弹性`. Path 5 is before Path 6, so **no change needed** — the existing assertion still passes.

The `沪电股份` case (elastic_profile) has `benefit_type="direct"`, `is_core_name=False`, `is_secondary_name=False`, `market_validation="medium"`, `trading_usability="medium"`, `community_conviction="low"`. Under old code it hit Path 8 (direct + non-core + medium validation + medium usability → 高弹性). Under new code, same Path 8 still applies. **No change needed.**

The `兆易创新` case has `benefit_type="direct"`, `is_core_name=True`, `event_phase="正式结果"`, `event_state="official_confirmed"`, `priority_score=80`, `expectation_verdict="符合预期"`. It hits Path 3 (正式结果 + official_confirmed + direct + core + priority>=80 + verdict!="暂无一致预期") → 兑现风险最高. **No change needed.**

Verify: no existing assertions need updating.

- [ ] **Step 5: Run all tests**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py tests/test_month_end_shortlist_degraded_reporting.py tests/test_x_style_assisted_shortlist.py tests/test_month_end_shortlist_discovery_merge.py -v`
Expected: All pass (49 from Task 1 + 5 new = 54)

- [ ] **Step 6: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py tests/test_earnings_momentum_discovery.py
git commit -m "feat: tighten classify_trading_profile fallback chain — reduce 预期差最大 over-classification"
```

---

### Task 3: B3 — Add Realization Risk Scenario for Expectation Trading Phase

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py:484-486`
- Test: `tests/test_earnings_momentum_discovery.py`

**Context:** Current 兑现风险最高 only triggers in 正式结果/官方预告 phases or on response_denied. But crowded expectation trades (预期交易 phase with high conviction + strong validation + 3+ source accounts + high priority) can also have realization risk before results land. The `source_accounts` field already exists on event cards.

- [ ] **Step 1: Write failing test**

Add to the test class in `tests/test_earnings_momentum_discovery.py`:

```python
def test_classify_trading_profile_expectation_phase_crowded_trade_triggers_realization_risk(self) -> None:
    """B3: 预期交易 + high conviction + strong validation + 3+ accounts + priority>=85 → 兑现风险最高."""
    profile = module_under_test.classify_trading_profile(
        {
            "name": "CrowdedTrade",
            "benefit_type": "direct",
            "chain_role": "midstream_manufacturing",
            "leaders": ["CrowdedTrade"],
            "peer_tier_1": ["CrowdedTrade"],
            "peer_tier_2": [],
            "event_phase": "预期交易",
            "event_state": {"label": "unconfirmed"},
            "trading_usability": {"label": "high", "summary": "高"},
            "market_validation_summary": {"label": "strong", "summary": "强"},
            "expectation_verdict": "市场押注超预期",
            "community_conviction": "high",
            "priority_score": 90,
            "source_accounts": ["account1", "account2", "account3"],
        }
    )
    self.assertEqual(profile["bucket"], "兑现风险最高")
    self.assertIn("预期交易", profile["subtype"])

def test_classify_trading_profile_expectation_phase_not_crowded_stays_core(self) -> None:
    """B3 negative: same setup but only 2 accounts → should NOT trigger 兑现风险."""
    profile = module_under_test.classify_trading_profile(
        {
            "name": "NotCrowded",
            "benefit_type": "direct",
            "chain_role": "midstream_manufacturing",
            "leaders": ["NotCrowded"],
            "peer_tier_1": ["NotCrowded"],
            "peer_tier_2": [],
            "event_phase": "预期交易",
            "event_state": {"label": "unconfirmed"},
            "trading_usability": {"label": "high", "summary": "高"},
            "market_validation_summary": {"label": "strong", "summary": "强"},
            "expectation_verdict": "市场押注超预期",
            "community_conviction": "high",
            "priority_score": 90,
            "source_accounts": ["account1", "account2"],
        }
    )
    self.assertNotEqual(profile["bucket"], "兑现风险最高")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py -k "expectation_phase_crowded or expectation_phase_not_crowded" -v`
Expected: first test FAIL (currently routes to 稳健核心 via Path 4), second test PASS

- [ ] **Step 3: Add new path in `classify_trading_profile`**

In `earnings_momentum_discovery.py`, insert a new path **after** the existing Path 3 (sell-the-fact, ending around line 484) and **before** Path 4 (稳健核心, starting at line 486). The insertion point is between the `}` closing Path 3's return and the `if is_core_name and benefit_type == "direct":` line.

Insert:

```python
    # --- Path 3b: 预期交易阶段的过度定价风险 ---
    source_accounts = candidate.get("source_accounts") or []
    if not isinstance(source_accounts, list):
        source_accounts = []
    if (
        event_phase == "预期交易"
        and community_conviction == "high"
        and market_validation == "strong"
        and expectation_verdict == "市场押注超预期"
        and len(source_accounts) >= 3
        and priority_score >= 85
    ):
        return {
            "bucket": "兑现风险最高",
            "subtype": "预期交易阶段的过度定价风险",
            "reason": "虽然还没到正式结果，但多个社区声音已经高度一致且量价强势验证，当前更像预期过度定价的兑现窗口。",
        }
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py tests/test_month_end_shortlist_degraded_reporting.py tests/test_x_style_assisted_shortlist.py tests/test_month_end_shortlist_discovery_merge.py -v`
Expected: All pass (54 from Task 2 + 2 new = 56)

**Important check:** The existing `中际旭创` test case has `priority_score=100`, `community_conviction="high"`, `market_validation_summary.label="strong"`, `expectation_verdict="市场押注超预期"`, `event_phase="预期交易"`, but does NOT have `source_accounts` in its test dict. So `source_accounts` defaults to `[]`, `len([]) >= 3` is False, and it will NOT trigger the new path. It continues to hit Path 4 (稳健核心) as before. **No existing test update needed.**

- [ ] **Step 5: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/earnings_momentum_discovery.py tests/test_earnings_momentum_discovery.py
git commit -m "feat: add realization risk scenario for crowded expectation-phase trades"
```

---

### Task 4: B4 — Reorganize Event Board Layout

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py:1048-1063`
- Test: `tests/test_month_end_shortlist_degraded_reporting.py`

**Context:** Event Board currently renders 10+ lines per name with 判断/用法 buried in the middle. The spec requires a trader-panel layout: 判断/用法 on lines 2-3, then compact merged lines for 阶段+预期+数据, 社区+一致性, 驱动+风险, 市场验证. Event Cards section keeps full detail (unchanged).

Current Event Board rendering (lines 1048-1063 in `month_end_shortlist_runtime.py`):
```
- `ticker` name / `chain_name`
  - 阶段: `phase`
  - 预期判断: `verdict`
  - judgment
  - usage
  - 关键数据: `metrics`
  - 社区反应: reaction
  - 社区一致性: `conviction`
  - 预期驱动: basis
  - 兑现风险: risk
  - 市场验证: signal
```

Target layout:
```
- `ticker` name / `chain_name`
  - judgment
  - usage
  - `phase` | `verdict` | 数据: metric1, metric2
  - 社区: account1, account2 | 一致性: level
  - 驱动: basis | 风险: risk
  - 市场验证: signal
```

- [ ] **Step 1: Write failing test for new Event Board layout**

Add to the test class in `tests/test_month_end_shortlist_degraded_reporting.py`:

```python
def test_event_board_layout_judgment_usage_on_lines_2_3(self) -> None:
    """B4: Event Board should have 判断 on line 2 and 用法 on line 3 per entry."""
    enriched = self._build_enriched_with_event_cards()
    report = enriched.get("report_markdown", "")
    board_section = report.split("## Event Board")[1].split("## ")[0] if "## Event Board" in report else ""
    entries = [line for line in board_section.strip().split("\n") if line.strip()]
    # Find first entry (starts with "- `")
    entry_lines = []
    collecting = False
    for line in entries:
        if line.startswith("- `"):
            if collecting:
                break
            collecting = True
            entry_lines = [line]
        elif collecting and line.startswith("  - "):
            entry_lines.append(line)
    self.assertTrue(len(entry_lines) >= 3, f"Expected at least 3 lines per entry, got {len(entry_lines)}")
    self.assertIn("判断:", entry_lines[1])
    self.assertIn("用法:", entry_lines[2])
    # Lines 4+ should NOT start with "阶段:" or "预期判断:" as separate lines
    for line in entry_lines[3:]:
        self.assertNotIn("  - 阶段:", line)
        self.assertNotIn("  - 预期判断:", line)
```

Note: `_build_enriched_with_event_cards` is a helper you need to add (or use the existing test infrastructure). If the test file already has a test that calls `enrich_live_result_reporting` with event cards, reuse that setup. Otherwise, create a minimal helper:

```python
def _build_enriched_with_event_cards(self):
    """Helper to build enriched result with at least one event card for layout testing."""
    from financial_analysis_skills.month_end_shortlist.scripts import month_end_shortlist_runtime as runtime
    enriched = {
        "discovery_lane_summary": "test",
        "event_cards": [
            {
                "ticker": "000001.SZ",
                "name": "TestStock",
                "chain_name": "TestChain",
                "event_phase": "预期交易",
                "expectation_verdict": "市场押注超预期",
                "trading_profile_judgment": "判断: 预期交易阶段先按高弹性处理",
                "trading_profile_usage": "用法: 适合快进快出",
                "headline_metrics": ["800G", "Q1"],
                "community_reaction_summary": "多数看多",
                "community_conviction": "high",
                "expectation_basis_summary": "Q1放量",
                "expectation_risk_summary": "兑现窗口临近",
                "market_signal_summary": "volume_5d=2.1x; breakout=yes",
                "source_accounts": ["account1", "account2"],
                "trading_profile_bucket": "高弹性",
                "trading_profile_subtype": "预期博弈型弹性",
                "trading_profile_reason": "test",
                "trading_profile_playbook": "打法: test",
                "primary_event_type": "earnings",
                "priority_score": 80,
                "why_now": "test",
                "chain_path_summary": "TestChain / midstream / direct",
                "source_count": 2,
                "source_urls": [],
                "evidence_mix": {},
                "event_state": {"label": "unconfirmed"},
                "trading_usability": {"label": "high", "summary": "高"},
                "key_evidence": [],
            }
        ],
        "chain_map_entries": [],
    }
    runtime.enrich_live_result_reporting(enriched)
    return enriched
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_month_end_shortlist_degraded_reporting.py::TestDegradedReporting::test_event_board_layout_judgment_usage_on_lines_2_3 -v`
Expected: FAIL — current layout has 阶段 on line 2, not 判断

- [ ] **Step 3: Rewrite Event Board rendering block**

In `month_end_shortlist_runtime.py`, replace lines 1048-1063 (the Event Board rendering loop) with:

```python
    event_cards = enriched.get("event_cards", [])
    if enriched.get("discovery_lane_summary") and "## Event Board" not in "\n".join(lines):
        lines.extend(["", "## Event Board", ""])
        for item in (event_cards if isinstance(enriched.get("event_cards"), list) else []):
            lines.append(f"- `{item.get('ticker')}` {item.get('name')} / `{item.get('chain_name')}`")
            lines.append(f"  - {item.get('trading_profile_judgment')}")
            lines.append(f"  - {item.get('trading_profile_usage')}")
            metrics = item.get("headline_metrics") if isinstance(item.get("headline_metrics"), list) else []
            metrics_text = f" | 数据: {', '.join(metrics[:4])}" if metrics else ""
            lines.append(f"  - `{item.get('event_phase')}` | `{item.get('expectation_verdict')}`{metrics_text}")
            accounts = item.get("source_accounts") if isinstance(item.get("source_accounts"), list) else []
            accounts_text = ", ".join(accounts[:3]) if accounts else "none"
            lines.append(f"  - 社区: {accounts_text} | 一致性: `{item.get('community_conviction')}`")
            lines.append(f"  - 驱动: {item.get('expectation_basis_summary')} | 风险: {item.get('expectation_risk_summary')}")
            lines.append(f"  - 市场验证: {item.get('market_signal_summary')}")
```

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py tests/test_month_end_shortlist_degraded_reporting.py tests/test_x_style_assisted_shortlist.py tests/test_month_end_shortlist_discovery_merge.py -v`
Expected: All pass (56 from Task 3 + 1 new = 57). Some existing tests that assert on Event Board content may need assertion updates if they check for specific line patterns — update those assertions to match the new layout.

- [ ] **Step 5: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_month_end_shortlist_degraded_reporting.py
git commit -m "feat: reorganize Event Board layout — judgment/usage first, compact merged lines"
```

---

### Task 5: B5 — Improve Chain/Peer Expansion Quality

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py:800-850`
- Test: `tests/test_month_end_shortlist_degraded_reporting.py`

**Context:** `build_chain_map_entries` (lines 800-850 in `month_end_shortlist_runtime.py`) builds chain profiles from `discovery_context.chain_map`. Currently, names NOT in event_cards get static assignment: leaders → 稳健核心, tier_1 minus leaders → 高弹性, tier_2 → 补涨候选, and leftover names → 预期差最大 (line 815). The spec requires: (1) remove the empty `expectation_gap` list generation that assigns names to 预期差最大 without evidence, (2) for tier_1 names not in event_cards, check if any event_card in the same chain has `market_validation == "strong"` → 高弹性, else → 补涨候选.

Current problematic code (lines 812-822):
```python
all_candidates = unique_strings(item.get("all_candidates") or (leaders + tier_1 + tier_2))
high_beta = [name for name in tier_1 if name not in leaders]
assigned = set(leaders + high_beta + tier_2)
expectation_gap = [name for name in all_candidates if name and name not in assigned]
profiles = {
    "稳健核心": leaders,
    "高弹性": high_beta,
    "补涨候选": tier_2,
    "预期差最大": expectation_gap,
    "兑现风险最高": [],
}
```

- [ ] **Step 1: Write failing tests**

Add to the test class in `tests/test_month_end_shortlist_degraded_reporting.py`:

```python
def test_chain_map_does_not_produce_expectation_gap_without_evidence(self) -> None:
    """B5: chain map should not assign names to 预期差最大 without evidence."""
    from financial_analysis_skills.month_end_shortlist.scripts import month_end_shortlist_runtime as runtime
    entries = runtime.build_chain_map_entries(
        event_cards=[],
        discovery_context={
            "chain_map": [
                {
                    "chain_name": "光模块",
                    "leaders": ["中际旭创"],
                    "tier_1": ["中际旭创", "新易盛"],
                    "tier_2": ["天孚通信"],
                    "all_candidates": ["中际旭创", "新易盛", "天孚通信", "ExtraName"],
                }
            ]
        },
    )
    self.assertEqual(len(entries), 1)
    profiles = entries[0]["profiles"]
    self.assertEqual(profiles["预期差最大"], [])

def test_chain_map_tier1_gets_elastic_when_chain_has_strong_validation(self) -> None:
    """B5: tier_1 names should get 高弹性 when an event_card in the same chain has strong validation."""
    from financial_analysis_skills.month_end_shortlist.scripts import month_end_shortlist_runtime as runtime
    event_cards = [
        {
            "ticker": "000001.SZ",
            "name": "中际旭创",
            "chain_name": "光模块",
            "trading_profile_bucket": "稳健核心",
            "market_validation_summary": {"label": "strong", "summary": "强"},
        }
    ]
    entries = runtime.build_chain_map_entries(
        event_cards=event_cards,
        discovery_context={
            "chain_map": [
                {
                    "chain_name": "光模块",
                    "leaders": ["中际旭创"],
                    "tier_1": ["中际旭创", "新易盛"],
                    "tier_2": ["天孚通信"],
                }
            ]
        },
    )
    self.assertEqual(len(entries), 1)
    profiles = entries[0]["profiles"]
    # 新易盛 is tier_1 (not leader), chain has strong validation → 高弹性
    self.assertIn("新易盛", profiles["高弹性"])
    # 天孚通信 is tier_2 → 补涨候选
    self.assertIn("天孚通信", profiles["补涨候选"])

def test_chain_map_tier1_gets_catchup_when_chain_has_weak_validation(self) -> None:
    """B5: tier_1 names should get 补涨候选 when no event_card in chain has strong validation."""
    from financial_analysis_skills.month_end_shortlist.scripts import month_end_shortlist_runtime as runtime
    event_cards = [
        {
            "ticker": "000001.SZ",
            "name": "中际旭创",
            "chain_name": "光模块",
            "trading_profile_bucket": "稳健核心",
            "market_validation_summary": {"label": "weak", "summary": "弱"},
        }
    ]
    entries = runtime.build_chain_map_entries(
        event_cards=event_cards,
        discovery_context={
            "chain_map": [
                {
                    "chain_name": "光模块",
                    "leaders": ["中际旭创"],
                    "tier_1": ["中际旭创", "新易盛"],
                    "tier_2": ["天孚通信"],
                }
            ]
        },
    )
    profiles = entries[0]["profiles"]
    self.assertIn("新易盛", profiles["补涨候选"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_month_end_shortlist_degraded_reporting.py -k "expectation_gap_without_evidence or tier1_gets_elastic or tier1_gets_catchup" -v`
Expected: All 3 FAIL

- [ ] **Step 3: Rewrite the initial profile assignment in `build_chain_map_entries`**

In `month_end_shortlist_runtime.py`, replace lines 800-828 (from `def build_chain_map_entries` through the initial `grouped` building loop, before the `for card in event_cards:` loop) with:

```python
def build_chain_map_entries(event_cards: list[dict[str, Any]], discovery_context: dict[str, Any] | None) -> list[dict[str, Any]]:
    rows = discovery_context.get("chain_map") if isinstance(discovery_context, dict) and isinstance(discovery_context.get("chain_map"), list) else []

    # Pre-compute which chains have strong validation from event_cards
    chain_has_strong_validation: dict[str, bool] = {}
    for card in (event_cards if isinstance(event_cards, list) else []):
        if not isinstance(card, dict):
            continue
        chain_name = clean_text(card.get("chain_name"))
        if not chain_name:
            continue
        validation_label = clean_text((card.get("market_validation_summary") or {}).get("label"))
        if validation_label == "strong":
            chain_has_strong_validation[chain_name] = True

    grouped: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        chain_name = clean_text(item.get("chain_name"))
        if not chain_name:
            continue
        leaders = unique_strings(item.get("leaders") or [])
        tier_1 = unique_strings(item.get("tier_1") or [])
        tier_2 = unique_strings(item.get("tier_2") or [])
        has_strong = chain_has_strong_validation.get(chain_name, False)
        high_beta_candidates = [name for name in tier_1 if name not in leaders]
        if has_strong:
            high_beta = high_beta_candidates
            catchup = tier_2
        else:
            high_beta = []
            catchup = unique_strings(high_beta_candidates + tier_2)
        profiles = {
            "稳健核心": leaders,
            "高弹性": high_beta,
            "补涨候选": catchup,
            "预期差最大": [],
            "兑现风险最高": [],
        }
        grouped[chain_name] = {
            "chain_name": chain_name,
            "profiles": profiles,
            "chain_playbook": build_chain_map_playbook(profiles),
            "anchors": [],
        }
```

The rest of the function (the `for card in event_cards:` loop starting at the old line 829) remains unchanged.

- [ ] **Step 4: Run all tests**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py tests/test_month_end_shortlist_degraded_reporting.py tests/test_x_style_assisted_shortlist.py tests/test_month_end_shortlist_discovery_merge.py -v`
Expected: All pass (57 from Task 4 + 3 new = 60)

- [ ] **Step 5: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_month_end_shortlist_degraded_reporting.py
git commit -m "feat: improve chain map expansion — remove evidence-free 预期差最大, use validation-aware tier_1 routing"
```

---

### Task 6: Final Regression Verification

**Files:**
- All test files

- [ ] **Step 1: Run full regression**

Run: `python -m pytest tests/test_earnings_momentum_discovery.py tests/test_month_end_shortlist_degraded_reporting.py tests/test_x_style_assisted_shortlist.py tests/test_month_end_shortlist_discovery_merge.py -v`
Expected: 60 passed, 0 failed

- [ ] **Step 2: Verify no import errors or missing references**

Run: `python -c "from financial_analysis_skills.month_end_shortlist.scripts import earnings_momentum_discovery; print('OK')"`
Run: `python -c "from financial_analysis_skills.month_end_shortlist.scripts import month_end_shortlist_runtime; print('OK')"`
Expected: Both print `OK`
