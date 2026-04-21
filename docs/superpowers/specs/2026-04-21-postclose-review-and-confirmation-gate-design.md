# Postclose Review and Confirmation Gate Design

Date: `2026-04-21`
Repo: `D:\Users\rickylu\dev\financial-services-plugins-clean`
Branch: `feat/cache-first-execution-closure` (or new branch from `main`)
Status: Spec 1 of 2 (Spec 2: direction layer auto-integration, deferred)

## Background

2026-04-20 trading plan review revealed three mechanism-level deficiencies:

1. **No intraday structure verification** — runtime scores candidates on daily bars
   only; a candidate like 华工科技 (score=58, gap=0) passes all filters but fades
   intraday, leading to a losing entry.
2. **No postclose feedback loop** — review is manual; lessons (e.g. 北方稀土
   outperformed but was observation-only) are not fed back into the next run.
3. **No confirmation gate for marginal candidates** — a candidate that barely
   clears the threshold gets the same "qualified" action as a strong pick, with no
   midday re-check prompt.

This spec addresses all three with: an intraday data layer, an automated
postclose review script, and a runtime confirmation gate.

## Scope

- Intraday bars (15min) fetch, cache, and structure classification
- Automated postclose review script producing structured JSON + markdown
- Runtime confirmation gate for marginal candidates
- Review-based priority boost from prior postclose output
- 3 new test files; all 106 existing tests remain green

## Out of Scope (deferred to Spec 2)

- Direction layer (oil/optical/rare-earth) automatic integration into execution
- Cross-day direction momentum tracking
- Multi-day review trend aggregation

---

## Section 1: Intraday Data Layer

### 1.1 Data Source

Extend `tradingagents_eastmoney_market.py` to support 15-minute bars via
Eastmoney `klt=104` parameter. The existing daily bars infrastructure
(`klt=101`) is the template.

### 1.2 New Functions

#### `fetch_intraday_bars(symbol, trade_date, klt=104)`

- Calls Eastmoney kline API with `klt=104` (15min period)
- Returns `list[dict]` with keys: `timestamp`, `open`, `close`, `high`, `low`,
  `volume`, `amount`
- Filters to bars within `trade_date` only (Eastmoney may return adjacent days)
- Raises on HTTP/parse failure; caller handles fallback

#### `eastmoney_cached_intraday_bars_for_candidate(candidate, trade_date)`

- Cache-first wrapper mirroring `eastmoney_cached_bars_for_candidate` pattern
- Cache key: `intraday_{symbol}_{trade_date}_{klt}`
- TTL: same-day = indefinite (intraday data is immutable after close);
  cross-day = 7 days
- Returns cached bars or fetches and caches

#### `classify_intraday_structure(bars_15min) -> str`

Pure function. Input: list of 15min bars for one trading day. Output: one of:

| Classification | Condition |
|---|---|
| `strong_close` | Last 2 bars close > VWAP AND close > open for last bar AND close in top 20% of day range |
| `fade_from_high` | Intraday high in first half, close < VWAP, close in bottom 40% of day range |
| `weak_open_no_recovery` | First bar close < open by > 1%, never recovers above open price |
| `range_bound` | Day range < 3% AND close within 30%-70% of day range |

If none match, default to `range_bound`.

VWAP is calculated as cumulative `amount / volume` across bars.

### 1.3 Integration Point

The postclose review script (Section 2) calls these functions. The runtime
gate (Section 3) reads the classification result from the review output.
The intraday layer does NOT modify the existing daily-bars pipeline.

---

## Section 2: Automated Postclose Review Script

### 2.1 Purpose

Replace the manual postclose review with a script that:

1. Reads the day's `result.json` (shortlist output)
2. Fetches intraday bars for each candidate that received an action
3. Classifies intraday structure
4. Compares plan vs actual outcome
5. Produces upgrade/downgrade adjustments for next-day runtime
6. Renders a markdown report matching the existing manual template

### 2.2 File Location

```
financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py
```

### 2.3 Input

| Input | Source | Required |
|---|---|---|
| `result.json` | Prior shortlist run output | Yes |
| `trade_date` | The date being reviewed | Yes |
| `trading_plan.md` | Optional: the morning plan file | No |

### 2.4 Core Logic: `run_postclose_review(result_json, trade_date, plan_md=None)`

Steps:

1. Parse `result.json` → extract candidates with `midday_action != null`
2. For each candidate:
   - Fetch 15min bars via `eastmoney_cached_intraday_bars_for_candidate`
   - Run `classify_intraday_structure`
   - Compute actual day return: `(close - prev_close) / prev_close`
   - Compare to plan expectation (if plan provided)
3. Classify each candidate's plan outcome:

| Judgment | Condition |
|---|---|
| `plan_correct` | Action was "qualified" + actual return >= -1% |
| `plan_too_aggressive` | Action was "qualified" + actual return < -1% |
| `missed_opportunity` | Action was "观察" or "blocked" + actual return > +2% |
| `plan_correct_negative` | Action was "观察"/"blocked" + actual return <= +2% AND return < 0 |

Note: "qualified" with return between -1% and 0% counts as `plan_correct`
(minor drawdown within normal range). "观察"/"blocked" with return between
0% and +2% falls through to `plan_correct_negative` — a small positive move
on a skipped candidate is not a missed opportunity.

4. Generate adjustments:

| Judgment | Adjustment |
|---|---|
| `plan_too_aggressive` | `downgrade`: reduce priority by 5, add confirmation gate |
| `missed_opportunity` | `upgrade`: boost priority by 5 for next run |
| `plan_correct` | `hold`: no change |
| `plan_correct_negative` | `hold`: no change |

### 2.5 Output

#### Structured JSON: `review_output.json`

```json
{
  "trade_date": "2026-04-20",
  "candidates_reviewed": [
    {
      "ticker": "000988",
      "name": "华工科技",
      "plan_action": "qualified",
      "actual_return_pct": -1.46,
      "intraday_structure": "fade_from_high",
      "judgment": "plan_too_aggressive",
      "adjustment": "downgrade",
      "priority_delta": -5,
      "gate_next_run": true
    },
    {
      "ticker": "002185",
      "name": "华天科技",
      "plan_action": "观察",
      "actual_return_pct": 3.39,
      "intraday_structure": "strong_close",
      "judgment": "missed_opportunity",
      "adjustment": "upgrade",
      "priority_delta": 5,
      "gate_next_run": false
    }
  ],
  "summary": {
    "total_reviewed": 4,
    "correct": 1,
    "too_aggressive": 1,
    "missed": 1,
    "correct_negative": 1
  },
  "prior_review_adjustments": [
    {
      "ticker": "002185",
      "adjustment": "upgrade",
      "priority_delta": 5,
      "gate_next_run": false
    }
  ]
}
```

#### Markdown Report: `postclose-review-{date}.md`

Follows the structure of `post-close-review-template.md`:
- Action summary table (plan vs actual)
- Intraday structure classification per candidate
- Judgment and adjustment per candidate
- Next-day watch points derived from adjustments

### 2.6 CLI Interface

```
python postclose_review_runtime.py --result <result.json> --date 2026-04-20 \
  [--plan <trading_plan.md>] \
  [--output <review_output.json>] \
  [--markdown-output <report.md>]
```

### 2.7 Error Handling

- If intraday bars fetch fails for a candidate: skip intraday classification,
  mark `intraday_structure: "unavailable"`, still produce judgment from daily
  return alone
- If `result.json` has no actionable candidates: produce empty review with
  `total_reviewed: 0`

---

## Section 3: Runtime Confirmation Gate and Priority Boost

### 3.1 Confirmation Gate: `intraday_confirmation_gate`

Added to `month_end_shortlist_runtime.py`.

#### Trigger Condition

A candidate triggers the confirmation gate when ALL of:

1. `midday_action` would be `"qualified"` under current logic
2. AND at least one of:
   - `gap_to_next_tier <= 2` (marginal score)
   - `catalyst_strength` is `"weak"` or absent
   - `execution_state` is `"fresh_cache"` or `"stale_cache"`

#### Gate Effect

When triggered:

- `midday_action` changes from `"qualified"` to `"待确认"`
- `midday_status` set to new value `"pending_confirmation"`
- Decision flow card adds line: `"盘中确认：需等待 11:00 后分时确认"`
- Operation reminder adds: `"午盘前确认分时结构再决定是否执行"`

#### Non-Trigger

Candidates that clear the gate (strong score, strong catalyst, live data)
keep `midday_action = "qualified"` unchanged.

### 3.2 Priority Boost: `review_based_priority_boost`

Added to `month_end_shortlist_runtime.py`.

#### Input

The shortlist request JSON gains an optional field:

```json
{
  "prior_review_adjustments": [
    {
      "ticker": "002185",
      "adjustment": "upgrade",
      "priority_delta": 5,
      "gate_next_run": false
    },
    {
      "ticker": "000988",
      "adjustment": "downgrade",
      "priority_delta": -5,
      "gate_next_run": true
    }
  ]
}
```

This is the `prior_review_adjustments` array from the previous day's
`review_output.json`.

#### Logic

Applied after scoring, before tier assignment:

1. For each adjustment in `prior_review_adjustments`:
   - Find matching candidate by ticker
   - Apply `priority_delta` to candidate's score
   - If `gate_next_run == true`: force candidate through confirmation gate
     regardless of score margin
   - If `adjustment == "upgrade"`: add tier tag `"review_upgraded"`
   - If `adjustment == "downgrade"`: add tier tag `"review_downgraded"`

2. Decision flow card reflects the boost:
   - Upgraded: `"复盘加分：+5（前日错过机会）"`
   - Downgraded: `"复盘减分：-5（前日过于激进）"` + `"强制确认门控"`

### 3.3 New `midday_status` Value

Add `"pending_confirmation"` to the existing set:

| Status | Meaning |
|---|---|
| `qualified` | Passes all checks, executable |
| `near_miss` | Close but below threshold |
| `blocked` | Hard filter failure |
| `watch` | Observation only |
| `pending_confirmation` | **New**: marginally qualified, needs intraday confirmation |

### 3.4 Decision Flow Card Updates

For `pending_confirmation` candidates, the card renders:

```
操作建议：待确认
盘中确认：需等待 11:00 后分时确认
确认条件：分时不出现 fade_from_high 或 weak_open_no_recovery
确认后操作：按原计划执行
未确认操作：降级为观察
```

For review-boosted candidates:

```
复盘加分：+5（前日错过机会）
原始得分：53.0 → 调整后：58.0
```

For review-downgraded candidates:

```
复盘减分：-5（前日过于激进）
强制确认门控：是
原始得分：58.0 → 调整后：53.0
```

---

## Section 4: Testing Strategy

### 4.1 New Test Files

#### `tests/test_intraday_structure_classification.py`

- `test_strong_close_classification`: bars with rising last 2 bars above VWAP,
  close in top 20% → `"strong_close"`
- `test_fade_from_high_classification`: high in first half, close below VWAP in
  bottom 40% → `"fade_from_high"`
- `test_weak_open_no_recovery`: first bar drops > 1%, never recovers →
  `"weak_open_no_recovery"`
- `test_range_bound_default`: narrow range, mid-close → `"range_bound"`
- `test_empty_bars_returns_range_bound`: edge case
- `test_vwap_calculation_correctness`: verify cumulative amount/volume

#### `tests/test_postclose_review_runtime.py`

- `test_plan_too_aggressive_generates_downgrade`: 华工科技 scenario — qualified
  action, -1.46% return, fade_from_high → judgment `plan_too_aggressive`,
  adjustment `downgrade`, `priority_delta: -5`, `gate_next_run: true`
- `test_missed_opportunity_generates_upgrade`: 北方稀土 scenario — observation
  action, +3.39% return, strong_close → judgment `missed_opportunity`,
  adjustment `upgrade`, `priority_delta: +5`
- `test_plan_correct_no_adjustment`: positive return on qualified action →
  `plan_correct`, no delta
- `test_plan_correct_negative_no_adjustment`: negative return on blocked action →
  `plan_correct_negative`, no delta
- `test_intraday_fetch_failure_still_produces_judgment`: bars unavailable →
  `intraday_structure: "unavailable"`, judgment still computed from daily return
- `test_empty_result_produces_empty_review`: no actionable candidates →
  `total_reviewed: 0`
- `test_markdown_report_matches_template_structure`: output has required sections

#### `tests/test_confirmation_gate_and_priority_boost.py`

- `test_marginal_candidate_triggers_confirmation_gate`: score gap ≤ 2 →
  `midday_action: "待确认"`, `midday_status: "pending_confirmation"`
- `test_strong_candidate_bypasses_gate`: high score, strong catalyst →
  `midday_action: "qualified"` unchanged
- `test_weak_catalyst_triggers_gate`: absent catalyst on qualified candidate →
  gate triggered
- `test_stale_cache_execution_state_triggers_gate`: `execution_state:
  "stale_cache"` on qualified candidate → gate triggered
- `test_review_upgrade_boosts_priority`: `prior_review_adjustments` with
  `upgrade` → score +5, tier tag `"review_upgraded"`
- `test_review_downgrade_reduces_priority_and_forces_gate`: `downgrade` →
  score -5, tier tag `"review_downgraded"`, forced through confirmation gate
- `test_decision_flow_card_shows_pending_confirmation_labels`: card contains
  `"待确认"`, `"盘中确认"`, `"确认条件"`
- `test_decision_flow_card_shows_review_boost_labels`: card contains
  `"复盘加分"` or `"复盘减分"` as appropriate

### 4.2 Regression Constraint

All 106 existing tests must remain green. No existing test assertions are
modified by this spec. The confirmation gate and priority boost are additive
paths that only activate when new input fields are present.

### 4.3 Test Data

Tests use synthetic data constructed in `setUp` methods. No network calls.
Intraday bars are hand-crafted lists of dicts matching the
`fetch_intraday_bars` return schema. Review inputs are hand-crafted
`result.json` fragments.

---

## Appendix: File Change Summary

| File | Change Type |
|---|---|
| `tradingagents_eastmoney_market.py` | Add `fetch_intraday_bars`, `eastmoney_cached_intraday_bars_for_candidate`, `classify_intraday_structure` |
| `postclose_review_runtime.py` | New file: `run_postclose_review`, CLI entry point |
| `month_end_shortlist_runtime.py` | Add `intraday_confirmation_gate`, `review_based_priority_boost`; extend `build_decision_flow_card`; add `pending_confirmation` status |
| `tests/test_intraday_structure_classification.py` | New file |
| `tests/test_postclose_review_runtime.py` | New file |
| `tests/test_confirmation_gate_and_priority_boost.py` | New file |
