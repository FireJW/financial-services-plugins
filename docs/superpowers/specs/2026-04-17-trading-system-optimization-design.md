# Trading System Optimization — Design Spec

Date: 2026-04-17

## Scope

Five slices, all at the wrapper/reporting layer. No compiled shortlist core changes.

## B1: Fix Crash Path + Regenerate Artifacts

### Problem

`int(candidate.get("priority_score") or 0)` and similar `float()` calls crash on
truthy non-numeric strings like `"-"` or `"N/A"`. The `or 0` guard only catches
falsy values.

### Change

Add `to_int_safe(value, default=0)` in `earnings_momentum_discovery.py`:

```python
def to_int_safe(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
```

Apply to `classify_trading_profile` line 448 (`priority_score`) and
`compute_event_priority_score` line 216+. Also audit all `float()` calls in both
files — the `to_float()` helper already exists in `month_end_shortlist_runtime.py`
but `earnings_momentum_discovery.py` has raw `float()` calls at lines 82, 298,
666, 739, 740, 742, 808 that need the same guard.

After the fix, rerun the real-X example to regenerate:
- `.tmp/real-x-event-card-example/report.md`
- `.tmp/real-x-event-card-example/result.json`

## B2: Tighten `classify_trading_profile` Fallback Chain

### Problem

>50% of names land in "预期差最大" because:
1. `community_conviction == "low"` catches all auto-discovered names without X commentary
2. `expectation_verdict == "暂无一致预期"` is the default for names without explicit consensus
3. `expectation_verdict == "市场押注超预期"` paradoxically also triggers "预期差最大"

### Changes

#### Fix 1: Remove "市场押注超预期" from the 预期差最大 catch-all

Current (line 536):
```python
if expectation_verdict in {"市场押注超预期", "暂无一致预期"} or community_conviction == "low":
    return {"bucket": "预期差最大", ...}
```

New: names with `expectation_verdict == "市场押注超预期"` should route to 高弹性
or 补涨候选 based on validation strength, not to 预期差最大.

#### Fix 2: Tighten 预期差最大 entry

New condition — all three must hold:
```python
if (
    community_conviction == "low"
    and expectation_verdict == "暂无一致预期"
    and market_validation not in {"strong", "medium"}
):
```

Names that fail this tighter gate but still have no clear profile should fall
through to the final fallback, which routes to 高弹性 (if strong validation) or
补涨候选 (default) instead of 预期差最大.

#### Fix 3: Add `evidence_strength` marker

For names that do land in 预期差最大, add a field:
- `evidence_strength: "genuine_gap"` — when there is actual evidence of
  underpricing (e.g., positive expectation keywords + low conviction)
- `evidence_strength: "weak_evidence"` — when the classification is driven by
  absence of data rather than presence of gap signal

This marker flows into `trading_profile_judgment` and `trading_profile_usage`.

#### Fix 4: Refine 高弹性 vs 补涨候选 boundary

Current: `benefit_type == "mapping"` always → 补涨候选 (Path 6, line 512).

New: insert a check before Path 6:
```python
if (
    benefit_type == "mapping"
    and market_validation in {"strong", "medium"}
    and trading_usability in {"high", "medium"}
    and not is_secondary_name
    and chain_role not in {"logic_support", "quote_only"}
):
    return {"bucket": "高弹性", "subtype": "映射受益但验证充分的弹性表达", ...}
```

Only remaining mapping names (weak validation or secondary or logic_support)
stay as 补涨候选.

#### Fix 5: Change final fallback default

Current (line 543-547): `market_validation == "strong"` → 高弹性, else → 预期差最大.

New: `market_validation == "strong"` → 高弹性, else → **补涨候选** (with subtype
"证据不足的扩散候选"). 预期差最大 should only be reachable through the tightened
explicit gate, never as a default fallback.

## B3: Add Realization Risk Scenario for Expectation Trading Phase

### Problem

Current 兑现风险最高 only triggers in 正式结果/官方预告 phases or on
response_denied. But crowded expectation trades can also have realization risk
before results land.

### Change

Add a new path before the existing 稳健核心 check (after the three existing
兑现风险 paths):

```python
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

Where `source_accounts` is extracted from the candidate's `source_accounts` field
(already present on event cards). For `classify_trading_profile`, we need to pass
this through — either add it to the candidate dict before classification, or
extract it from sources inside the function.

Implementation: extract `source_accounts` count from `candidate.get("source_accounts", [])` inside `classify_trading_profile`.

## B4: Reorganize Event Board Layout

### Problem

Event Board currently renders 10+ lines per name with judgment/usage buried in
the middle. Should read like a trader panel.

### Change

New Event Board layout (in `enrich_live_result_reporting`):

```
- `ticker` name / `chain_name`
  - 判断: ...
  - 用法: ...
  - `阶段` | `预期判断` | 数据: metric1, metric2
  - 社区: account1, account2 | 一致性: level
  - 驱动: basis | 风险: risk_summary
  - 市场验证: signal_summary
```

Key changes:
1. 判断/用法 move to lines 2-3 (from current position after 阶段/预期判断)
2. 阶段 + 预期判断 + 关键数据 merge into one compact line
3. 社区反应 + 一致性 merge into one line
4. 驱动 + 风险 merge into one line
5. Remove 预期驱动/兑现风险 as separate lines — fold into the merged line

Event Cards section keeps full detail (unchanged).

## B5: Improve Chain/Peer Expansion Quality

### Problem

Chain Map profiles are partially populated from discovery_context chain_map, but:
1. Names from chain_map that don't appear in event_cards get static assignment
   (leaders → 稳健核心, tier_1 minus leaders → 高弹性, tier_2 → 补涨候选)
2. No cross-referencing with actual trading profile classification

### Change

In `build_chain_map_entries`:
1. After building initial profiles from discovery_context, iterate event_cards
   and override the bucket assignment for any name that has a computed
   `trading_profile_bucket` (current behavior — already works)
2. For names in chain_map that are NOT in event_cards, use a lightweight
   heuristic instead of the current static mapping:
   - If name is in `leaders` → 稳健核心 (keep current)
   - If name is in `tier_1` but not leaders → check if any event_card in the
     same chain has `market_validation == "strong"` → if yes, 高弹性; if no,
     补涨候选
   - If name is in `tier_2` → 补涨候选 (keep current)
   - Remove the empty `expectation_gap` list generation — names should not be
     assigned to 预期差最大 in chain map without evidence

## Test Plan

### New tests for B2:
- Test that `expectation_verdict == "市场押注超预期"` with weak validation → 高弹性 (not 预期差最大)
- Test that `community_conviction == "low"` alone no longer triggers 预期差最大
- Test that `benefit_type == "mapping"` + strong validation → 高弹性
- Test that final fallback → 补涨候选 (not 预期差最大)
- Test `evidence_strength` marker on genuine 预期差最大 names

### New tests for B3:
- Test 预期交易 phase + high conviction + strong validation + 3+ accounts → 兑现风险最高

### Updated tests for B4:
- Assert Event Board markdown has 判断/用法 on lines 2-3 per entry
- Assert compact merged lines for 阶段/预期/数据

### Updated tests for B5:
- Assert chain map does not produce 预期差最大 entries without evidence
- Assert tier_1 names get 高弹性 when chain has strong validation

### Regression:
- All existing 47 tests must continue to pass (with expected assertion updates for changed classification boundaries)
