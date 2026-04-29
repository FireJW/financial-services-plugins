# Emergent Theme Promotion For Shortlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `emergent_theme_candidates` promotion layer so non-preconfigured themes strengthened by X discussion, earnings/news, and market behavior can participate in formal shortlist ranking instead of being silently missed.

**Architecture:** Keep the current `month_end_shortlist` spine intact and add a narrow promotion layer inside `month_end_shortlist_runtime.py`. Build emergent themes from existing local inputs and runtime outputs, merge promoted themes into the active theme pool, and preserve a degraded `data_blocked_theme_confirmed` visibility state when a theme is strong but bars fail on aligned names.

**Tech Stack:** Python 3.12, `month-end-shortlist` runtime, existing `weekend_market_candidate` output, existing `x_index` request/result surfaces, existing supplement lanes, `unittest`, pytest

---

## File Structure

### New / Modified Files

- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
  - add the `emergent_theme_candidates` contract
  - score and promote non-preconfigured themes
  - merge promoted themes into the active theme pool
  - preserve `data_blocked_theme_confirmed` candidates in enriched output
  - add report rendering for promoted themes and data-blocked aligned names
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
  - add optional helper support for carrying through externally promoted themes when present
  - do not expand `TOPIC_ALIASES` into an unconstrained miner
- Create: `tests/test_emergent_theme_promotion.py`
  - focused unit tests for emergent theme scoring, promotion, active-pool merge, and degraded visibility behavior
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
  - verify request/result passthrough for the new emergent theme surfaces
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
  - verify report sections for promoted themes and `data_blocked_theme_confirmed`

### Responsibility Boundaries

- `x_index_runtime.py` is not rewritten in Phase 1.
- `weekend_market_candidate_runtime.py` remains a predeclared-alias topic detector.
- `month_end_shortlist_runtime.py` becomes the promotion point that turns existing signal families into emergent theme participation.
- Existing `market_strength_candidates` and `setup_launch_candidates` logic remains intact; the new layer only feeds theme promotion and degraded visibility.

---

## Task 1: Add Failing Tests For Emergent Theme Promotion

**Files:**
- Create: `tests/test_emergent_theme_promotion.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Add a failing test for emergent theme scoring**

Create a test that supplies:

- repeated X evidence for a non-preconfigured theme such as `lithium_upstream`
- multiple earnings-aligned tickers
- at least one market-strength-aligned ticker

Expected behavior:

- the emergent theme is scored
- `promotion_score` is populated
- source strengths are classified as `high` / `medium` / `low`

Example assertion target:

```python
themes = module_under_test.build_emergent_theme_candidates(
    x_theme_hits=[{"theme_name": "lithium_upstream", "names": ["002709.SZ", "002466.SZ"]}],
    earnings_theme_hits=[{"theme_name": "lithium_upstream", "names": ["002709.SZ", "002407.SZ"]}],
    market_theme_hits=[{"theme_name": "lithium_upstream", "names": ["002709.SZ"]}],
)

self.assertEqual(themes[0]["theme_name"], "lithium_upstream")
self.assertEqual(themes[0]["source_signals"]["x_discussion_strength"], "high")
self.assertGreater(themes[0]["promotion_score"], 0.0)
```

- [ ] **Step 2: Add a failing test for promotion threshold behavior**

Cover two cases:

- a theme with two meaningful signals should promote
- a theme with only one thin signal should not promote

Expected behavior:

- promoted theme appears in the active theme pool
- weak theme stays out

- [ ] **Step 3: Add a failing test for degraded visibility on bars failure**

Create a candidate row shaped like:

- ticker aligned to a promoted emergent theme
- `bars_fetch_failed`
- valid sector/theme linkage

Expected behavior:

- the candidate is preserved in output as `data_blocked_theme_confirmed`
- it does not become executable

- [ ] **Step 4: Add a passthrough test for new result surfaces**

Verify merged/enriched output can carry:

- `emergent_theme_candidates`
- `promoted_active_themes`
- `data_blocked_theme_confirmed`

- [ ] **Step 5: Run focused tests and confirm failure before implementation**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_emergent_theme_promotion.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v --tb=short
```

Expected:

- failures because the emergent-theme builder, promotion merge, and degraded visibility state do not yet exist

---

## Task 2: Add Emergent Theme Contract And Scoring Helpers

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Create: `tests/test_emergent_theme_promotion.py`

- [ ] **Step 1: Add normalization helpers for emergent theme rows**

Add a helper such as:

```python
def normalize_emergent_theme_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "theme_name": clean_text(row.get("theme_name")),
        "theme_label": clean_text(row.get("theme_label")),
        "source_signals": deepcopy(row.get("source_signals")) if isinstance(row.get("source_signals"), dict) else {},
        "supporting_names": [clean_text(item) for item in row.get("supporting_names", []) if clean_text(item)],
        "promotion_score": float(row.get("promotion_score") or 0.0),
        "promotion_reason": clean_text(row.get("promotion_reason")),
    }
```

- [ ] **Step 2: Add coarse signal classification helpers**

Add focused helpers:

```python
def classify_emergent_x_discussion_strength(hit_count: int, unique_name_count: int) -> str:
    ...

def classify_emergent_earnings_confirmation_strength(hit_count: int, unique_name_count: int) -> str:
    ...

def classify_emergent_market_confirmation_strength(hit_count: int, unique_name_count: int) -> str:
    ...
```

Phase 1 rules should stay simple and deterministic:

- `high`
- `medium`
- `low`

- [ ] **Step 3: Add promotion-score helper**

Add:

```python
def emergent_theme_promotion_score(
    x_strength: str,
    earnings_strength: str,
    market_strength: str,
    theme_density: str,
) -> float:
    ...
```

Use a bounded score such as:

- `high = 1.0`
- `medium = 0.6`
- `low = 0.0`

Then combine and round.

- [ ] **Step 4: Add promotion-threshold helper**

Add:

```python
def should_promote_emergent_theme(theme: dict[str, Any]) -> bool:
    ...
```

Phase 1 rule:

- at least two major dimensions are `medium` or better
- at least one major dimension is `high`

- [ ] **Step 5: Re-run focused tests and verify partial progress**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_emergent_theme_promotion.py -v --tb=short
```

Expected:

- scoring and threshold tests now pass
- active-pool merge and degraded-output tests still fail

---

## Task 3: Build Emergent Themes From Existing Runtime Inputs

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Create: `tests/test_emergent_theme_promotion.py`

- [ ] **Step 1: Add extraction helpers for X / earnings / market theme hits**

Add helpers such as:

```python
def collect_x_theme_hits(
    request_obj: dict[str, Any],
) -> list[dict[str, Any]]:
    ...

def collect_earnings_theme_hits(
    discovery_candidates: list[dict[str, Any]],
    event_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ...

def collect_market_theme_hits(
    market_strength_candidates: list[dict[str, Any]],
    setup_launch_candidates: list[dict[str, Any]],
    assessed_candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ...
```

Phase 1 extraction rules:

- use existing `theme_guess` where present
- use sector/theme names already attached to candidates
- do not parse arbitrary free text beyond what current structures already provide

- [ ] **Step 2: Add the builder for emergent themes**

Add:

```python
def build_emergent_theme_candidates(
    *,
    x_theme_hits: list[dict[str, Any]],
    earnings_theme_hits: list[dict[str, Any]],
    market_theme_hits: list[dict[str, Any]],
    excluded_theme_names: set[str],
) -> list[dict[str, Any]]:
    ...
```

Behavior:

- aggregate by `theme_name`
- skip already preconfigured active themes if they are already explicitly in the pool
- build `source_signals`
- populate `supporting_names`
- compute `promotion_score`
- populate `promotion_reason`

- [ ] **Step 3: Add a promotion merge helper**

Add:

```python
def merge_active_theme_pool(
    explicit_themes: list[str],
    weekend_themes: list[str],
    strategic_themes: list[str],
    emergent_themes: list[dict[str, Any]],
) -> list[str]:
    ...
```

Merge order:

1. explicit request themes
2. weekend themes
3. strategic themes
4. promoted emergent themes

- [ ] **Step 4: Re-run focused tests and verify emergent promotion behavior**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_emergent_theme_promotion.py -v --tb=short
```

Expected:

- emergent-theme creation and active-pool merge tests pass
- degraded-visibility tests may still fail

---

## Task 4: Let Promoted Themes Participate In Formal Shortlist Flow

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Compute emergent themes during the main runtime path**

In the main orchestration path where:

- `prepared_weekend_market_candidate`
- `market_strength_candidates`
- `setup_launch_candidates`
- `all_assessed`

already exist, add:

```python
emergent_theme_candidates = build_emergent_theme_candidates(
    x_theme_hits=collect_x_theme_hits(prepared_payload),
    earnings_theme_hits=collect_earnings_theme_hits(discovery_candidates, event_cards),
    market_theme_hits=collect_market_theme_hits(
        market_strength_candidates,
        setup_launch_candidates,
        all_assessed,
    ),
    excluded_theme_names=set(active_setup_themes),
)
```

- [ ] **Step 2: Promote emergent themes into the active theme pool**

Replace direct use of only:

- weekend themes
- strategic themes

with:

- merged `promoted_active_themes`

Then feed that merged list into:

- setup-launch theme selection
- other theme-aware supplement surfaces that already consume active themes

- [ ] **Step 3: Preserve the promoted themes in merged/enriched output**

Attach to result:

```python
merged["emergent_theme_candidates"] = [...]
merged["promoted_active_themes"] = promoted_active_themes
```

- [ ] **Step 4: Re-run passthrough tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -v --tb=short
```

Expected:

- result now carries the new surfaces

---

## Task 5: Add Data-Blocked Theme-Confirmed Visibility

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`
- Create: `tests/test_emergent_theme_promotion.py`

- [ ] **Step 1: Add a builder for data-blocked theme-confirmed rows**

Add:

```python
def build_data_blocked_theme_confirmed_candidates(
    dropped: list[dict[str, Any]],
    emergent_themes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ...
```

Behavior:

- match dropped rows with `bars_fetch_failed`
- check whether their ticker belongs to `supporting_names` of a promoted theme
- emit a normalized row with:
  - `ticker`
  - `name`
  - `theme_name`
  - `theme_label`
  - `status = "data_blocked_theme_confirmed"`
  - `drop_reason`
  - `bars_fetch_error`

- [ ] **Step 2: Attach the degraded rows to enriched/merged output**

Attach:

```python
result["data_blocked_theme_confirmed"] = ...
```

This must not alter:

- `top_picks`
- `T1`
- `T2`

- [ ] **Step 3: Add report rendering helper**

Add a markdown block such as:

- `## 新兴共振主题`
- `## 数据受阻但主题已确认`

Each promoted theme should show:

- theme label
- promotion reason
- source signal strengths
- key supporting names

Each data-blocked aligned name should show:

- ticker / name
- aligned theme
- blocking reason

- [ ] **Step 4: Run degraded-reporting tests**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_emergent_theme_promotion.py -v --tb=short
```

Expected:

- promoted-theme and data-blocked sections render
- execution tiers remain unchanged

---

## Task 6: Verify Against The Tiansci Material Failure Mode

**Files:**
- Modify: `tests/test_emergent_theme_promotion.py`

- [ ] **Step 1: Add a focused regression test for the `天赐材料` class of miss**

Model a run where:

- `002709.SZ` is linked to `lithium_upstream`
- X discussion for `lithium_upstream` is present
- earnings confirmation for `lithium_upstream` is present
- market confirmation for at least one related name is present
- `002709.SZ` itself has `bars_fetch_failed`

Expected:

- `lithium_upstream` is promoted
- `002709.SZ` appears under `data_blocked_theme_confirmed`
- the theme enters `promoted_active_themes`

- [ ] **Step 2: Run the focused regression**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_emergent_theme_promotion.py::test_lithium_upstream_theme_promotes_even_when_tiansci_is_data_blocked -v --tb=short
```

Expected:

- PASS

---

## Task 7: Full Focused Verification

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
- Create: `tests/test_emergent_theme_promotion.py`
- Modify: `tests/test_month_end_shortlist_profile_passthrough.py`
- Modify: `tests/test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Run the full focused suite**

Run:

```bash
py -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_emergent_theme_promotion.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -v --tb=short
```

Expected:

- all tests pass

- [ ] **Step 2: Run one realistic local artifact rebuild**

Use the existing `2026-04-27` or a copied `2026-04-29` plan pack and verify:

- a non-preconfigured theme can be promoted
- promoted theme appears in output
- aligned bars-failed names are visible under `data_blocked_theme_confirmed`

Example command shape:

```bash
py D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\plan-2026-04-27\request.month-end-shortlist.json --output D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\plan-2026-04-27\result.month-end-shortlist.emergent-theme.json --markdown-output D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\plan-2026-04-27\report.month-end-shortlist.emergent-theme.md
```

Expected:

- command completes
- output files exist
- new emergent-theme sections are present

- [ ] **Step 3: Commit**

```bash
git add D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\weekend_market_candidate_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_emergent_theme_promotion.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\specs\2026-04-29-emergent-theme-promotion-for-shortlist-design.md D:\Users\rickylu\dev\financial-services-plugins-clean\docs\superpowers\plans\2026-04-29-emergent-theme-promotion-for-shortlist-implementation.md
git commit -m "feat: promote emergent themes into shortlist"
```

---

## Spec Coverage Check

- Root-cause split between `bars_fetch_failed` and missing theme-entry surface is covered by:
  - Task 3
  - Task 5
  - Task 6
- `emergent_theme_candidates` contract is covered by:
  - Task 2
  - Task 3
- promotion into formal shortlist participation is covered by:
  - Task 4
- degraded visibility for data-blocked aligned names is covered by:
  - Task 5
  - Task 6
- no direct automatic `T1` / `T2` promotion is preserved by:
  - Task 5
  - Task 7

## Placeholder Scan

- No `TODO`
- No `TBD`
- No unresolved file placeholders
- All code-touch tasks name explicit files and verification commands
