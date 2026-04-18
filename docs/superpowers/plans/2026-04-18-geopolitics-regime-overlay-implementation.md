# Geopolitics Regime Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual `macro_geopolitics_overlay` to the shortlist wrapper so geopolitical regime context can mildly bias observation-layer ranking and execution posture without weakening T1 discipline.

**Architecture:** Keep the compiled shortlist core unchanged and implement the regime logic entirely in wrapper/runtime space. Normalize the overlay request, compute deterministic bias for supported beneficiary/headwind chains, apply that bias to observation-layer ordering and decision/report synthesis, and expose the effect in the final trade-plan cards.

**Tech Stack:** Python, pytest, month-end shortlist runtime wrapper, markdown report synthesis.

---

### Task 1: Normalize and validate the geopolitics overlay request

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Write the failing normalization test**

Add a new test in `tests/test_month_end_shortlist_profile_passthrough.py` that builds a raw request with:

```python
{
    "target_date": "2026-04-21",
    "filter_profile": "month_end_event_support_transition",
    "macro_geopolitics_overlay": {
        "regime_label": "escalation",
        "confidence": "medium",
        "headline_risk": "high",
        "beneficiary_chains": ["oil_shipping", "gold"],
        "headwind_chains": ["airlines", "high_beta_growth"],
        "notes": "Hormuz disruption risk repriced.",
    },
}
```

Assert that `normalize_request(...)` preserves a cleaned `macro_geopolitics_overlay` dict with:
- `regime_label == "escalation"`
- canonical string lists for `beneficiary_chains` / `headwind_chains`
- unknown fields removed or ignored

- [ ] **Step 2: Run the single test to verify it fails**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -q
```

Expected: a failure because the overlay is not yet normalized or asserted shape is missing.

- [ ] **Step 3: Implement overlay normalization**

In `month_end_shortlist_runtime.py`:

- add canonical constants for:
  - supported regime labels: `escalation`, `de_escalation`, `whipsaw`
  - supported beneficiary/headwind chain names from the spec
- add a small helper, for example:

```python
def normalize_macro_geopolitics_overlay(raw: Any) -> dict[str, Any] | None:
    ...
```

Behavior:
- return `None` if not a dict
- return `None` if `regime_label` is invalid or missing
- preserve only:
  - `regime_label`
  - `confidence`
  - `headline_risk`
  - `beneficiary_chains`
  - `headwind_chains`
  - `notes`
- normalize chain lists to canonical strings and drop unknown chain names

Wire this helper into `normalize_request_with_compiled(...)` so normalized requests can carry:

```python
normalized["macro_geopolitics_overlay"] = overlay
```

- [ ] **Step 4: Re-run the normalization test**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py
git commit -m "feat: normalize geopolitics regime overlay"
```

### Task 2: Apply regime bias to observation-layer ranking without changing T1 semantics

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_board_threshold_overrides.py`

- [ ] **Step 1: Write failing ranking-bias tests**

Add focused tests proving:

1. A beneficiary-chain observation candidate is ranked ahead of an otherwise similar neutral candidate during `escalation`.
2. A headwind-chain observation candidate is ranked lower during `escalation`.
3. `T1` membership does not change solely due to the overlay.

Preferred location:
- `tests/test_screening_coverage_optimization.py` for track-level tier/ranking behavior
- `tests/test_board_threshold_overrides.py` only if merged output ordering needs a dedicated assertion

Use simple synthetic candidates with:
- equal or near-equal scores
- different `chain_name`
- one overlay regime

Expected ordering should be explicit, for example:

```python
self.assertEqual([row["ticker"] for row in enriched["tier_output"]["T3"][:2]], ["OIL.SS", "NEUTRAL.SS"])
```

- [ ] **Step 2: Run the new tests to verify failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_board_threshold_overrides.py -q
```

Expected: at least one new failure because no regime-aware ranking bias exists yet.

- [ ] **Step 3: Implement deterministic regime bias helpers**

In `month_end_shortlist_runtime.py`, add small pure helpers such as:

```python
def classify_geopolitics_chain_bias(chain_name: str, overlay: dict[str, Any] | None) -> str:
    ...

def compute_geopolitics_bias(candidate: dict[str, Any], overlay: dict[str, Any] | None) -> float:
    ...
```

Phase 1 rules:
- no overlay or invalid overlay → `0.0`
- `escalation`
  - beneficiary chain → small positive bias
  - headwind chain → small negative bias
- `de_escalation`
  - beneficiary chain → small negative bias
  - headwind chain → small positive bias
- `whipsaw`
  - smaller-magnitude bias than escalation/de-escalation

Keep the magnitude intentionally small, e.g. `±1.0` to `±2.0` equivalent ranking points.

- [ ] **Step 4: Apply bias only to observation-layer ordering**

Do **not** rewrite compiled `keep`.

Instead:
- keep `T1` assignment unchanged
- apply regime bias when ordering observation candidates in:
  - `assign_tiers(...)` inputs for `T3/T4`
  - or immediately before `apply_rendered_caps(...)` if that is the smallest reliable hook

Implementation constraint:
- make the bias visible in ordering
- do not let it create or remove `T1`

If needed, annotate candidates with:

```python
candidate["macro_geopolitics_bias"] = ...
candidate["macro_geopolitics_bias_label"] = ...
```

- [ ] **Step 5: Re-run the ranking tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_board_threshold_overrides.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_board_threshold_overrides.py
git commit -m "feat: add geopolitics regime ranking bias"
```

### Task 3: Surface regime, bias, and execution constraints in the final report

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Write failing reporting tests**

Add report-facing assertions that prove Phase 1 user-visible behavior:

1. `decision_flow` / report metadata includes the regime label.
2. An affected observation card includes a short chain-bias explanation.
3. Execution constraint text changes under the overlay, especially for `whipsaw` and `escalation`.

Example assertion style:

```python
self.assertIn("地缘 regime: `escalation`", enriched["report_markdown"])
self.assertIn("链条偏置", enriched["report_markdown"])
self.assertIn("headline reversal risk", enriched["report_markdown"])
```

- [ ] **Step 2: Run degraded-reporting tests to verify failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -q
```

Expected: failures for the new assertions.

- [ ] **Step 3: Add report-layer synthesis**

In `month_end_shortlist_runtime.py`, extend decision/report helpers so overlay context can surface in:

- summary metadata
- decision-flow cards
- observation cards

Recommended additions:
- regime line near report header / summary
- short bias phrase, e.g.:
  - `链条偏置：地缘升级下的受益链条`
  - `链条偏置：地缘缓和下承压`
- execution constraint phrase, e.g.:
  - `执行约束：轻仓，不追高，隔夜谨慎`
  - `执行约束：headline reversal risk 高，优先等确认`

Keep this deterministic and concise. Do not add a long macro essay.

- [ ] **Step 4: Re-run degraded-reporting tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py
git commit -m "feat: surface geopolitics regime in trade plan output"
```

### Task 4: End-to-end verification and smoke examples

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_board_threshold_overrides.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_earnings_momentum_discovery.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_discovery_merge.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_x_style_assisted_shortlist.py`

- [ ] **Step 1: Run the focused shortlist verification suite**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_board_threshold_overrides.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_earnings_momentum_discovery.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_discovery_merge.py D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_x_style_assisted_shortlist.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Create a small manual smoke request**

Use the existing shortlist request fixture and add a `macro_geopolitics_overlay`, for example:

```json
{
  "macro_geopolitics_overlay": {
    "regime_label": "escalation",
    "confidence": "medium",
    "headline_risk": "high",
    "beneficiary_chains": ["oil_shipping", "energy", "gold", "defense"],
    "headwind_chains": ["airlines", "cost_sensitive_chemicals", "export_chain", "high_beta_growth"],
    "notes": "Hormuz disruption risk repriced; market sensitive to headline reversals."
  }
}
```

Write the resolved request to a temporary `.tmp` fixture file before running the shortlist.

- [ ] **Step 3: Run a smoke shortlist generation**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py <overlay-request.json> --output <result.json> --markdown-output <report.md>
```

Expected:
- report renders successfully
- report shows regime text
- at least one observation-layer card includes chain bias or execution constraint wording

- [ ] **Step 4: Commit any request/example fixture if needed**

If you created a durable example fixture that should live in the repo, commit it:

```bash
git add <fixture-path>
git commit -m "test: add geopolitics overlay smoke fixture"
```

If the smoke input is temporary-only, do not commit `.tmp` artifacts.

## Self-Review

- Spec coverage:
  - request contract: Task 1
  - regime bias + ranking: Task 2
  - execution constraints + report visibility: Task 3
  - end-to-end validation: Task 4
- Placeholder scan:
  - no `TODO`/`TBD`
  - explicit file paths and commands included
- Type consistency:
  - `macro_geopolitics_overlay`
  - `regime_label`
  - `beneficiary_chains`
  - `headwind_chains`
  - deterministic helper naming preserved across tasks
