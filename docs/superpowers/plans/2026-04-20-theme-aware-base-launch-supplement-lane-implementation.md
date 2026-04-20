# Theme-Aware Base Launch Supplement Lane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a theme-aware `setup_launch_candidates` supplement lane so the shortlist can surface bottom-completion / early-launch names inside live priority themes and strategic base-watch themes without loosening `T1/T2` execution gates.

**Architecture:** Keep the existing event-driven shortlist and `market_strength_candidates` lane unchanged, add a new theme-scoped setup detector that scans for structure repair + early volume return + RS improvement, and late-merge those names as a separately labeled `筑底启动补充` layer. The new lane should consume the union of current weekend priority themes and a new durable `strategic_base_watch_themes` pool, but only promote names into `T3`, `T4`, and watchlist/report surfaces.

**Tech Stack:** Python 3.12, `month-end-shortlist` runtime, existing weekend candidate output, Eastmoney-derived candidate snapshots already present in the runtime, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - add the durable `strategic_base_watch_themes` configuration surface
  - normalize optional `setup_launch_candidates` request rows
  - add setup-stage scoring / filtering helpers
  - generate `setup_launch_candidates` from a theme-scoped universe
  - late-merge the new lane into enriched output and markdown reporting
- Create: `tests/test_setup_launch_supplement_lane.py`
  - focused unit tests for theme-pool union logic, setup scoring, exclusion, and candidate generation
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
  - lock request/result passthrough for `setup_launch_candidates` and `strategic_base_watch_themes`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - verify the report renders a dedicated `筑底启动补充` section without polluting `T1/T2`

### Responsibility Boundaries

- The existing event-driven shortlist spine remains unchanged.
- The existing `market_strength_candidates` lane remains same-day strong-close oriented.
- `setup_launch_candidates` is a distinct supplement lane with distinct report semantics.
- No change is allowed to:
  - `keep_threshold`
  - `strict_top_pick_threshold`
  - direct `T1/T2` promotion rules

---

## Task 1: Add Failing Tests for the New Setup Lane Contract

**Files:**
- Create: `tests/test_setup_launch_supplement_lane.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Add a normalization test for explicit setup-lane inputs**

Verify `normalize_request(...)` accepts and cleans:

- `setup_launch_candidates`
- `strategic_base_watch_themes`

Example target assertions:

```python
normalized = module_under_test.normalize_request(
    {
        "template_name": "month_end_shortlist",
        "target_date": "2026-04-21",
        "strategic_base_watch_themes": [
            "commercial_space",
            "controlled_fusion",
            "humanoid_robotics",
            "semiconductor_equipment",
        ],
        "setup_launch_candidates": [
            {
                "ticker": "603698.SS",
                "name": "航天工程",
                "theme_guess": ["commercial_space"],
                "setup_reasons": ["reclaimed_ma20_ma50"],
                "ignored": "drop-me",
            }
        ],
    }
)

self.assertEqual(normalized["strategic_base_watch_themes"][0], "commercial_space")
self.assertEqual(normalized["setup_launch_candidates"][0]["ticker"], "603698.SS")
self.assertNotIn("ignored", normalized["setup_launch_candidates"][0])
```

- [ ] **Step 2: Add a failing test for theme-pool union behavior**

Lock the expected union of:

- top `2-3` `weekend_market_candidate` topic names
- configured `strategic_base_watch_themes`

Expected behavior:

- duplicates deduped
- strategic themes remain even if absent from current weekend top topics

- [ ] **Step 3: Add a failing test for setup-stage candidate generation**

Create a small theme-scoped universe where:

- `603698.SS` looks like structure repair + volume return + RS improvement
- another row looks like pure bottom drift
- another row looks like already overextended strong-close momentum

Expected:

- only the true early-launch row is generated as `setup_launch_scan`

- [ ] **Step 4: Run the focused tests and confirm failure before implementation**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v --tb=short
```

Expected:

- failures because the new normalization surface and setup-lane helpers do not yet exist

---

## Task 2: Add Durable Theme-Pool Configuration and Setup-Lane Normalization

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

- [ ] **Step 1: Add the strategic theme configuration surface**

Add a durable default constant such as:

```python
DEFAULT_STRATEGIC_BASE_WATCH_THEMES = (
    "commercial_space",
    "controlled_fusion",
    "humanoid_robotics",
    "semiconductor_equipment",
)
```

- [ ] **Step 2: Normalize request overrides safely**

Extend request normalization to accept:

- `strategic_base_watch_themes`
- `setup_launch_candidates`

Normalization rules:

- keep only non-empty strings for themes
- dedupe themes while preserving order
- clean `setup_launch_candidates` similarly to other supplement rows

- [ ] **Step 3: Add a helper that resolves the active theme pool**

Recommended shape:

```python
def resolve_setup_launch_theme_pool(
    request_obj: dict[str, Any],
    weekend_market_candidate: dict[str, Any] | None,
) -> list[str]:
    ...
```

Behavior:

- start with weekend top-topic names
- extend with request override or defaults from `DEFAULT_STRATEGIC_BASE_WATCH_THEMES`
- dedupe while preserving order

- [ ] **Step 4: Re-run focused tests and verify partial progress**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v --tb=short
```

Expected:

- normalization / theme-pool tests now pass
- setup-generation tests still fail

---

## Task 3: Implement Setup-Stage Scoring and Candidate Generation

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Create: `tests/test_setup_launch_supplement_lane.py`

- [ ] **Step 1: Add explainable setup-stage helper functions**

Add focused helpers instead of burying logic inline. Recommended shapes:

```python
def classify_structure_repair(row: dict[str, Any]) -> str:
    ...

def classify_volume_return(row: dict[str, Any]) -> str:
    ...

def classify_rs_improvement(row: dict[str, Any]) -> str:
    ...

def classify_distance_from_bottom_state(row: dict[str, Any]) -> str:
    ...
```

- [ ] **Step 2: Add a setup-lane exclusion helper**

Recommended shape:

```python
def is_setup_launch_excluded(row: dict[str, Any], existing_tickers: set[str]) -> bool:
    ...
```

Phase 1 should exclude:

- blank ticker
- duplicates already present in formal candidates
- `ST` / risk-warning names
- clearly illiquid rows
- names still acting like pure bottom drift with no repair signal

- [ ] **Step 3: Add the setup score helper**

Recommended shape:

```python
def setup_launch_score(row: dict[str, Any]) -> float:
    ...
```

Phase 1 should reward:

- structure repair
- visible volume return
- RS improvement
- `off_bottom_not_extended` behavior

It should not require:

- extreme day gain
- near-limit close
- `distance_to_high52_pct <= 25`
- `rs90 >= 500`

- [ ] **Step 4: Add the generator**

Recommended shape:

```python
def build_setup_launch_candidates_from_universe(
    universe_rows: list[dict[str, Any]],
    *,
    active_themes: list[str],
    existing_tickers: set[str],
    max_names: int = 10,
) -> list[dict[str, Any]]:
    ...
```

Generated row contract should include:

- `ticker`
- `name`
- `theme_guess`
- `setup_reasons`
- `structure_repair`
- `volume_return`
- `rs_improvement`
- `distance_from_bottom_state`
- `source = "setup_launch_scan"`

- [ ] **Step 5: Keep the generator theme-aware**

Phase 1 should only consider rows whose theme mapping intersects the active theme pool.

If no theme mapping is available for a row, do not silently include it in Phase 1.

- [ ] **Step 6: Re-run the focused setup-lane tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py -v --tb=short
```

Expected:

- PASS for helper and generator coverage

---

## Task 4: Wire the Setup Lane into the Existing Runtime and Report

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Extend `run_month_end_shortlist(...)` to build the new lane**

Recommended structure:

```python
weekend_market_candidate, direction_reference_map = build_weekend_market_candidate(...)
active_setup_themes = resolve_setup_launch_theme_pool(prepared_payload, weekend_market_candidate)
generated_setup_launch = build_setup_launch_candidates_from_universe(
    full_universe_or_theme_scoped_rows,
    active_themes=active_setup_themes,
    existing_tickers=existing_tickers,
    max_names=10,
)
```

- [ ] **Step 2: Late-merge setup candidates without altering formal keep logic**

Follow the same product discipline used for supplement lanes:

- generated setup rows become report/watchlist candidates
- they do not alter the formal `keep` decision path
- they do not create direct `T1/T2` promotions

- [ ] **Step 3: Add a dedicated enriched output surface**

Add a clear enriched key such as:

```python
enriched["setup_launch_candidates"] = generated_setup_launch
```

This keeps the lane inspectable and reusable.

- [ ] **Step 4: Render a separate report section**

Add a dedicated markdown section:

- `## 筑底启动补充`

Each card should show:

- ticker / name
- theme guess
- setup reasons
- source `setup_launch_scan`

Do not merge this section into:

- `直接可执行`
- `市场强势补充`

- [ ] **Step 5: Add report regressions**

Lock that:

- setup-lane names appear under `筑底启动补充`
- market-strength names remain under `市场强势补充`
- no setup-lane name reaches `T1/T2` purely because of this lane

- [ ] **Step 6: Run focused integration tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- PASS

---

## Task 5: Verify Behavior Against the Original Product Goal

**Files:**
- No new files required beyond the runtime and tests above

- [ ] **Step 1: Add one end-to-end test for strategic themes that are not currently hot**

Example:

- weekend candidate top topics do not include `controlled_fusion`
- `strategic_base_watch_themes` still includes `controlled_fusion`
- a fusion-themed setup row still reaches `筑底启动补充`

- [ ] **Step 2: Add one end-to-end test for a live-hot theme**

Example:

- weekend top topic includes `commercial_space`
- a `commercial_space` setup row such as `603698.SS` is surfaced as `setup_launch_scan`

- [ ] **Step 3: Run the full focused ladder**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_setup_launch_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_market_strength_supplement_lane.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- PASS
- no regression in weekend candidate ranking
- no regression in market-strength supplement semantics

---

## Spec Coverage Self-Review

- Spec requirement: theme-aware lane instead of naked full-market setup scanning
  - Covered by Task 2 theme-pool resolver and Task 3 theme-aware generator.
- Spec requirement: strategic base-watch themes include commercial space, controlled fusion, humanoid robotics, semiconductor equipment
  - Covered by Task 2 default configuration surface.
- Spec requirement: lane is distinct from `market_strength_candidates`
  - Covered by Task 4 dedicated enriched output and separate markdown section.
- Spec requirement: no direct `T1/T2` promotion
  - Covered by Task 4 late-merge boundaries and Task 5 regressions.
- Spec requirement: explainable setup signals
  - Covered by Task 3 structure / volume / RS / distance helpers.

Placeholder scan result:

- No `TODO`, `TBD`, or unresolved references remain.

Type / naming consistency:

- `strategic_base_watch_themes`
- `setup_launch_candidates`
- `setup_launch_scan`

These names are used consistently across tasks.
