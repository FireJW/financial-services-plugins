# Direction Layer Automatic Integration into Execution Layer

Date: `2026-04-21`
Repo: `D:\Users\rickylu\dev\financial-services-plugins-clean`
Branch: `main`
Status: Spec 2 of 2 (Spec 1: postclose review + confirmation gate, completed)

## Background

The direction layer (`weekend_market_candidate_runtime.py`) produces sector-level
signals (optical interconnect, oil/shipping, rare-earth, etc.) with
`signal_strength` and a `direction_reference_map` listing leader/high-beta names.
Currently this data feeds only into:

1. **Theme-pool gating** — direction topics are prepended to the strategic theme
   pool in `resolve_setup_launch_theme_pool()`, determining which stocks enter
   the setup-launch scan.
2. **Report rendering** — direction data appears in the markdown output but is
   explicitly marked "Direction reference only. Not a formal execution layer."

The gap: direction signals do not influence candidate scoring, tier assignment,
or confirmation gate behavior. A candidate that is a named direction leader in
a high-signal sector gets the same treatment as any theme-matched stock.

## Scope

- Ticker resolution for `direction_reference_map` (build-time + execution-time)
- Two-tier direction alignment scoring (theme match + reference map match)
- Direction-based tier promotion (T2→T1, T3→T2)
- Confirmation gate bypass for direction-aligned candidates
- Postclose review momentum proxy (no new persistence layer)
- Decision flow card and report labels
- 18 new tests; all 346 existing tests remain green

## Out of Scope

- Dedicated cross-day persistence file for direction momentum (reuses postclose
  review output instead)
- Multi-day review trend aggregation beyond single prior-day lookback
- New direction topics or sector definitions
- Changes to the direction layer's own scoring/ranking logic

---

## Section 1: Ticker Resolution in Direction Layer

### 1.1 Problem

`direction_reference_map` entries have `leaders` and `high_beta_names` with
`ticker: ""`. The names come from seed/expansion inputs which contain only
Chinese company names, never ticker codes. Without tickers, the execution layer
cannot match direction names to scored candidates.

### 1.2 Build-Time Resolution

#### `resolve_direction_tickers(direction_reference_map, *, resolver=None)`

Location: `weekend_market_candidate_runtime.py`

- Iterates each entry's `leaders` and `high_beta_names`
- For each name with `ticker == ""`, calls the resolver (default: Eastmoney
  search API name→ticker lookup)
- If resolution succeeds: fills `ticker` field
- If resolution fails: keeps `ticker: ""`
- Updates `mapping_note` from `"Direction reference only..."` to
  `"Tickers resolved at build time."`
- Called inside `build_weekend_market_candidate()` before returning the tuple

#### Resolver Interface

```python
def default_ticker_resolver(name: str) -> str | None:
    """Return ticker string like '300308' or None if not found."""
```

Uses the same Eastmoney search endpoint already available in the codebase.
Accepts a `resolver` parameter for test injection.

### 1.3 Execution-Time Cross-Check

#### `cross_check_direction_tickers(direction_reference_map, universe)`

Location: `month_end_shortlist_runtime.py`

- For entries where `ticker == ""`: attempt match by name against the
  already-fetched stock universe (name field comparison)
- For entries with a ticker: verify ticker exists in universe
- Adds `in_universe: bool` to each leader/high_beta entry
- Returns enriched `direction_reference_map`
- Called inside `run_month_end_shortlist()` after universe fetch

### 1.4 Error Handling

- If the Eastmoney search API is unavailable at build time, all tickers stay
  `""` — execution-time cross-check is the fallback
- If a name matches multiple tickers, use the first result (highest relevance)
- Universe cross-check is name-based fuzzy: strip whitespace, compare
  normalized Chinese characters

---

## Section 2: Two-Tier Direction Alignment Scoring

### 2.1 Function

#### `direction_alignment_boost(candidates, direction_reference_map, weekend_market_candidate)`

Location: `month_end_shortlist_runtime.py`

Applied after `review_based_priority_boost`, before `assign_tiers`.

### 2.2 Tier 1: Theme Intersection Boost

If a candidate's `matched_themes` (from setup-launch scan) intersects with any
active direction topic:

| Direction signal_strength | Score boost |
|---|---|
| `"high"` | +3 |
| `"medium"` | +1 |
| `"low"` or absent | +0 |

Adds tier tag `"direction_theme_aligned"`.

### 2.3 Tier 2: Reference Map Match Boost

Stacks with Tier 1. Matched by ticker (after resolution).

| Match type | Score boost | Tier tag |
|---|---|---|
| `leaders` match | +6 | `"direction_leader"` |
| `high_beta_names` match | +4 | `"direction_high_beta"` |

Leader and high-beta are mutually exclusive — leader takes precedence if a
ticker appears in both lists.

### 2.4 Combined Effect

Maximum possible boost: theme(+3) + leader(+6) = **+9** for a high-signal
direction leader.

Applied to `adjusted_total_score`. A new field `direction_boost` is recorded
in the candidate dict:

```json
{
  "direction_boost": {
    "theme_delta": 3,
    "reference_delta": 6,
    "total_delta": 9,
    "direction_key": "optical_interconnect",
    "direction_role": "leader",
    "signal_strength": "high"
  }
}
```

### 2.5 Momentum Modulation

If `direction_momentum` is present in `prior_review_adjustments` (from
previous day's postclose review), boost values are modulated:

| momentum_signal | Effect |
|---|---|
| `"confirmed"` | Full boost (no change) |
| `"strengthening"` | Full boost (no change) |
| `"caution"` | Boost halved: theme +1, leader +3, high-beta +2 |
| `"fading"` | Boost zeroed for that direction |

### 2.6 No-Direction Fallback

If `weekend_market_candidate` is `None` or has `status: "insufficient_signal"`,
the function returns candidates unchanged (no-op).

---

## Section 3: Direction-Based Tier Promotion

### 3.1 Function

#### `direction_tier_promotion(tiered_candidates, direction_reference_map, weekend_market_candidate)`

Location: `month_end_shortlist_runtime.py`

Applied after `assign_tiers`.

### 3.2 Promotion Rules

Only when direction `signal_strength == "high"`:

| Current Tier | Condition | Promotion | Cap Check |
|---|---|---|---|
| T2 | `direction_leader` or `direction_high_beta` | → T1 | Only if T1 count < 10 |
| T3 | `direction_leader` | → T2 | Only if T2 count < 5 |
| T3 | `direction_high_beta` | No promotion | — |
| T4 | Any | No promotion | — |

### 3.3 Constraints

- **Max 2 promotions per run** — prevents direction from dominating tiers
- Promoted candidates get tier tag `"direction_promoted"`
- Stacks with `review_upgraded` from Spec 1 — but still counts against the
  2-promotion cap
- `signal_strength == "medium"` gets score boost only, no tier movement

### 3.4 Promotion with Momentum Caution

If the direction's `momentum_signal == "caution"`, tier promotion is disabled
for that direction regardless of signal_strength.

---

## Section 4: Confirmation Gate Bypass

### 4.1 Modification Target

Modify existing `intraday_confirmation_gate()` in
`month_end_shortlist_runtime.py`.

### 4.2 Bypass Condition

Before checking the existing gate trigger conditions, check if the candidate
has **both**:

1. Tier tag `"direction_leader"` or `"direction_high_beta"`
2. The associated direction has `signal_strength == "high"`

If both are true → skip the gate, candidate stays `"可执行"`.

### 4.3 Priority Order

1. `review_force_gate == True` → gate **always triggers** (review override
   from Spec 1, cannot be bypassed by direction)
2. Direction leader/high-beta + high signal → gate **bypassed**
3. Normal gate logic (gap ≤ 2, weak catalyst, stale cache)

The review's "you were too aggressive yesterday" judgment takes precedence
over direction conviction. This prevents the system from repeating the same
mistake with direction as justification.

### 4.4 Decision Flow Card Note

When bypass is applied:

```
方向层免确认：光通信 / 光模块 信号强度=high
```

When bypass is blocked by review_force_gate:

```
方向层免确认：不适用（复盘强制门控优先）
```

---

## Section 5: Postclose Review as Momentum Proxy

### 5.1 Purpose

Extend `postclose_review_runtime.py` to capture direction alignment data and
produce a momentum signal that feeds back into the next day's direction boost.
No new persistence layer — reuses the existing review→next-day feedback loop.

### 5.2 New Fields in `candidates_reviewed` Entries

| Field | Type | Description |
|---|---|---|
| `direction_aligned` | `bool` | Was this candidate direction-aligned at execution time? |
| `direction_key` | `str \| null` | Which direction topic (e.g. `"optical_interconnect"`) |
| `direction_role` | `str \| null` | `"leader"`, `"high_beta"`, `"theme_only"`, or `null` |

### 5.3 New Output Section: `direction_momentum`

```json
{
  "direction_momentum": [
    {
      "direction_key": "optical_interconnect",
      "direction_label": "光通信 / 光模块",
      "aligned_candidates_count": 3,
      "aligned_correct": 2,
      "aligned_too_aggressive": 1,
      "aligned_missed": 0,
      "momentum_signal": "caution"
    }
  ]
}
```

### 5.4 Momentum Signal Logic

| Condition | momentum_signal |
|---|---|
| `aligned_correct / aligned_candidates_count >= 0.5` AND zero `too_aggressive` | `"confirmed"` |
| Any `too_aggressive` among aligned candidates | `"caution"` |
| `aligned_missed > 0` AND zero `too_aggressive` | `"strengthening"` |
| All aligned candidates are `correct_negative` | `"fading"` |

Evaluation order: `caution` first (any too_aggressive), then `strengthening`
(any missed), then `confirmed` (≥50% correct), then `fading` (fallback).

If `aligned_candidates_count == 0` for a direction, omit that direction from
`direction_momentum` entirely (no signal to produce).

### 5.5 Feedback Path

The `direction_momentum` array is included alongside `prior_review_adjustments`
in the review output. At next-day runtime, `direction_alignment_boost()` reads
it to modulate boost values (see Section 2.5).

---

## Section 6: Decision Flow Card and Report Rendering

### 6.1 Decision Flow Card Labels

Added to `build_decision_flow_card()`.

**Direction-boosted candidate:**

```
方向层加分：+6（光通信 / 光模块 龙头）
方向信号强度：high
原始得分：52.0 → 方向调整后：58.0
```

**Direction-promoted candidate:**

```
方向层晋级：T2 → T1（光通信 / 光模块 龙头，信号=high）
```

**Direction gate bypass:**

```
方向层免确认：光通信 / 光模块 信号强度=high
```

**Momentum-modulated candidate:**

```
方向动量：confirmed（前日复盘确认）
```

or

```
方向动量：caution（前日方向过激，加分减半）
```

### 6.2 Markdown Report

Extend `build_weekend_market_candidate_markdown()` with a new subsection
"方向层执行整合" showing:

- Which candidates received direction boost and how much
- Tier promotions applied
- Gate bypasses granted
- Momentum signal from prior review

---

## Section 7: Testing Strategy

### 7.1 New Test File

`tests/test_direction_layer_integration.py`

### 7.2 Test Cases

#### Ticker Resolution (2 tests)

1. `test_resolve_direction_tickers_fills_known_names` — mock resolver returns
   tickers for known names, verify tickers are filled
2. `test_cross_check_direction_tickers_against_universe` — names matched
   against universe by name, `in_universe` flag set correctly

#### Two-Tier Scoring (5 tests)

3. `test_theme_alignment_boost_high_signal` — theme match + high signal → +3
4. `test_theme_alignment_boost_medium_signal` — theme match + medium → +1
5. `test_reference_map_leader_boost` — leader ticker match → +6
6. `test_reference_map_high_beta_boost` — high-beta ticker match → +4
7. `test_leader_and_theme_boost_stack` — both match → +3 + +6 = +9

#### No-Op and Edge Cases (2 tests)

8. `test_no_boost_when_insufficient_signal` — direction status insufficient →
   candidates unchanged
9. `test_no_boost_when_no_direction` — `weekend_market_candidate` is None →
   no-op

#### Tier Promotion (3 tests)

10. `test_tier_promotion_t2_to_t1_leader` — leader promoted when T1 < 10
11. `test_tier_promotion_respects_cap` — no promotion when T1 is full (10)
12. `test_tier_promotion_max_2_per_run` — third promotion blocked

#### Confirmation Gate Bypass (2 tests)

13. `test_gate_bypass_for_direction_leader_high_signal` — stays `"可执行"`
14. `test_gate_bypass_blocked_by_review_force_gate` — review override wins,
    gate still triggers

#### Momentum Proxy (3 tests)

15. `test_momentum_confirmed_full_boost` — no modulation applied
16. `test_momentum_caution_halves_boost` — theme +3→+1, leader +6→+3
17. `test_momentum_fading_zeros_boost` — all boosts zeroed for that direction

#### Decision Flow Card (1 test)

18. `test_decision_flow_card_direction_labels` — card contains `"方向层加分"`,
    `"方向信号强度"`, `"方向层晋级"`, `"方向层免确认"` as appropriate

### 7.3 Regression Constraint

All 346 existing tests remain green. Direction integration is additive — only
activates when `direction_reference_map` has resolved tickers and
`signal_strength` is present. No existing test assertions are modified.

### 7.4 Test Data

Tests use synthetic data constructed in `setUp` methods. No network calls.
Direction reference maps are hand-crafted with pre-filled tickers. Resolver
is injected as a mock.

---

## Appendix: File Change Summary

| File | Change Type |
|---|---|
| `weekend_market_candidate_runtime.py` | Add `resolve_direction_tickers`, `default_ticker_resolver`; call resolver in `build_weekend_market_candidate` |
| `month_end_shortlist_runtime.py` | Add `cross_check_direction_tickers`, `direction_alignment_boost`, `direction_tier_promotion`; modify `intraday_confirmation_gate` for bypass; extend `build_decision_flow_card` with direction labels; update `__all__` |
| `postclose_review_runtime.py` | Add `direction_aligned`, `direction_key`, `direction_role` to candidate entries; add `direction_momentum` section to output; extend `build_review_markdown` |
| `tests/test_direction_layer_integration.py` | New file: 18 tests |

## Appendix: Pipeline Insertion Order

```
1. build_weekend_market_candidate()        ← resolve_direction_tickers added here
2. resolve_setup_launch_theme_pool()       ← unchanged
3. fetch universe
4. cross_check_direction_tickers()         ← NEW: after universe fetch
5. build_setup_launch_candidates()         ← unchanged
6. assess candidates (compiled core)       ← unchanged
7. review_based_priority_boost()           ← unchanged (Spec 1)
8. direction_alignment_boost()             ← NEW: after review boost
9. assign_tiers()                          ← unchanged
10. direction_tier_promotion()             ← NEW: after tier assignment
11. intraday_confirmation_gate()           ← MODIFIED: bypass check added
12. build_decision_flow_card()             ← MODIFIED: direction labels added
13. enrich_live_result_reporting()         ← MODIFIED: direction section in report
```
