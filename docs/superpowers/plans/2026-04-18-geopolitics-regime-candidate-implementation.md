# Geopolitics Regime Candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Phase 2 geopolitics regime candidate layer that turns mixed news, X, and market inputs into a deterministic advisory candidate without directly mutating the formal geopolitics overlay.

**Architecture:** Keep the existing Phase 1 `macro_geopolitics_overlay` path unchanged and add a separate `macro_geopolitics_candidate_input -> macro_geopolitics_candidate` pipeline in wrapper/runtime space. Normalize mixed inputs, synthesize a unified evidence block, score `escalation / de_escalation / whipsaw`, emit `insufficient_signal` conservatively, and surface the candidate lightly in the report without letting it auto-become the formal overlay.

**Tech Stack:** Python, pytest, `month_end_shortlist_runtime.py`, markdown report synthesis.

---

### Task 1: Create an isolated worktree for the Phase 2 candidate branch

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean`

- [ ] **Step 1: Create a fresh feature worktree**

Run:

```bash
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" -c safe.directory="D:/Users/rickylu/dev/financial-services-plugins-clean" worktree add "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" -b feat/geopolitics-regime-candidate main
```

Expected:
- a new worktree exists at `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate`
- branch `feat/geopolitics-regime-candidate` points at current `main`

- [ ] **Step 2: Verify the worktree is on the expected branch**

Run:

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" -c safe.directory="D:/Users/rickylu/dev/.worktrees/financial-services-plugins-clean/feat-geopolitics-regime-candidate" status --short --branch
```

Expected:

```text
## feat/geopolitics-regime-candidate
```

- [ ] **Step 3: Commit only if the worktree bootstrap needs tracked fixes**

Most runs should not need a commit here. If the worktree needs tracked repo-local bootstrap changes, commit them separately; otherwise skip commit in this task.

### Task 2: Normalize `macro_geopolitics_candidate_input` without touching the formal overlay

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_profile_passthrough.py`

- [ ] **Step 1: Write failing normalization tests for candidate input**

Add tests in `tests/test_month_end_shortlist_profile_passthrough.py` covering:

```python
def test_normalize_request_preserves_cleaned_geopolitics_candidate_input(self) -> None:
    payload = {
        "target_date": "2026-04-21",
        "filter_profile": "month_end_event_support_transition",
        "macro_geopolitics_candidate_input": {
            "news_signals": [
                {
                    "source": "ap",
                    "headline": "Shipping disruption fears rise",
                    "summary": "Hormuz disruption risk repriced.",
                    "direction_hint": "escalation",
                    "timestamp": "2026-04-18T09:30:00+08:00",
                }
            ],
            "x_signals": [
                {
                    "account": "MacroDesk",
                    "url": "https://x.com/example/status/1",
                    "summary": "Energy traders lean toward renewed supply fear.",
                    "direction_hint": "escalation",
                    "timestamp": "2026-04-18T09:40:00+08:00",
                }
            ],
            "market_signals": {
                "oil": "up",
                "gold": "up",
                "shipping": "up",
                "risk_style": "risk_off",
                "usd_rates": "tightening",
                "airlines": "down",
                "industrials": "down",
            },
            "ignored_field": "drop-me",
        },
    }
    normalized = module_under_test.normalize_request(payload)
    self.assertIn("macro_geopolitics_candidate_input", normalized)
    candidate_input = normalized["macro_geopolitics_candidate_input"]
    self.assertEqual(candidate_input["news_signals"][0]["direction_hint"], "escalation")
    self.assertEqual(candidate_input["x_signals"][0]["account"], "MacroDesk")
    self.assertEqual(candidate_input["market_signals"]["oil"], "up")
    self.assertNotIn("ignored_field", candidate_input)


def test_candidate_input_does_not_auto_create_formal_overlay(self) -> None:
    payload = {
        "target_date": "2026-04-21",
        "filter_profile": "month_end_event_support_transition",
        "macro_geopolitics_candidate_input": {
            "news_signals": [{"headline": "Talks resume", "direction_hint": "de_escalation"}],
            "market_signals": {"oil": "down", "gold": "down"},
        },
    }
    normalized = module_under_test.normalize_request(payload)
    self.assertIn("macro_geopolitics_candidate_input", normalized)
    self.assertNotIn("macro_geopolitics_overlay", normalized)
```

- [ ] **Step 2: Run the normalization test file and confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_profile_passthrough.py -q
```

Expected:
- at least one new failure because `macro_geopolitics_candidate_input` is not yet normalized/preserved

- [ ] **Step 3: Add candidate-input normalization helpers**

In `month_end_shortlist_runtime.py`, add canonical constants and helpers such as:

```python
GEOPOLITICS_CANDIDATE_DIRECTIONS = {"escalation", "de_escalation", "whipsaw"}
GEOPOLITICS_MARKET_SIGNAL_VALUES = {
    "oil": {"up", "down", "flat"},
    "gold": {"up", "down", "flat"},
    "shipping": {"up", "down", "flat"},
    "risk_style": {"risk_on", "risk_off", "mixed"},
    "usd_rates": {"tightening", "loosening", "mixed"},
    "airlines": {"up", "down", "flat"},
    "industrials": {"up", "down", "flat"},
}


def normalize_candidate_signal_row(raw: Any, source_type: str) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    row: dict[str, Any] = {}
    if source_type == "news":
        row["source"] = clean_text(raw.get("source"))
        row["headline"] = clean_text(raw.get("headline"))
    elif source_type == "x":
        row["account"] = clean_text(raw.get("account"))
        row["url"] = clean_text(raw.get("url"))
    summary = clean_text(raw.get("summary"))
    direction_hint = clean_text(raw.get("direction_hint"))
    timestamp = clean_text(raw.get("timestamp"))
    if summary:
        row["summary"] = summary
    if direction_hint in GEOPOLITICS_CANDIDATE_DIRECTIONS:
        row["direction_hint"] = direction_hint
    if timestamp:
        row["timestamp"] = timestamp
    return row or None


def normalize_macro_geopolitics_candidate_input(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    news = [item for item in (normalize_candidate_signal_row(x, "news") for x in raw.get("news_signals", [])) if item]
    x_rows = [item for item in (normalize_candidate_signal_row(x, "x") for x in raw.get("x_signals", [])) if item]
    market_raw = raw.get("market_signals")
    market: dict[str, str] = {}
    if isinstance(market_raw, dict):
        for key, allowed in GEOPOLITICS_MARKET_SIGNAL_VALUES.items():
            value = clean_text(market_raw.get(key))
            if value in allowed:
                market[key] = value
    normalized: dict[str, Any] = {}
    if news:
        normalized["news_signals"] = news
    if x_rows:
        normalized["x_signals"] = x_rows
    if market:
        normalized["market_signals"] = market
    return normalized or None
```

Then wire it into `normalize_request_with_compiled(...)`:

```python
candidate_input = normalize_macro_geopolitics_candidate_input(
    raw_payload.get("macro_geopolitics_candidate_input")
)
if candidate_input:
    normalized["macro_geopolitics_candidate_input"] = candidate_input
else:
    normalized.pop("macro_geopolitics_candidate_input", None)
```

- [ ] **Step 4: Re-run the normalization tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_profile_passthrough.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" add "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py" "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_profile_passthrough.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" commit -m "feat: normalize geopolitics candidate input"
```

### Task 3: Build the evidence block and deterministic regime candidate

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_screening_coverage_optimization.py`

- [ ] **Step 1: Write failing tests for evidence synthesis and conservative candidate output**

Add tests in `tests/test_screening_coverage_optimization.py` such as:

```python
def test_builds_escalation_candidate_from_news_x_market_alignment(self):
    candidate_input = {
        "news_signals": [{"headline": "Shipping risk rises", "summary": "Disruption fears climb", "direction_hint": "escalation"}],
        "x_signals": [{"account": "MacroDesk", "summary": "Supply risk repricing resumes", "direction_hint": "escalation"}],
        "market_signals": {"oil": "up", "gold": "up", "shipping": "up", "risk_style": "risk_off", "airlines": "down"},
    }
    candidate = module_under_test.build_macro_geopolitics_candidate(candidate_input)
    self.assertEqual(candidate["candidate_regime"], "escalation")
    self.assertEqual(candidate["signal_alignment"], "news+x+market")
    self.assertEqual(candidate["status"], "candidate_only")


def test_returns_insufficient_signal_when_only_one_signal_class_supports_direction(self):
    candidate_input = {
        "news_signals": [{"headline": "Shipping risk rises", "summary": "Disruption fears climb", "direction_hint": "escalation"}],
    }
    candidate = module_under_test.build_macro_geopolitics_candidate(candidate_input)
    self.assertEqual(candidate["candidate_regime"], "insufficient_signal")


def test_whipsaw_requires_cross_source_conflict(self):
    candidate_input = {
        "news_signals": [{"headline": "Talks resume", "summary": "Transit may normalize", "direction_hint": "de_escalation"}],
        "x_signals": [{"account": "MacroDesk", "summary": "Headline reversal risk is rising", "direction_hint": "whipsaw"}],
        "market_signals": {"oil": "up", "gold": "up", "risk_style": "mixed"},
    }
    candidate = module_under_test.build_macro_geopolitics_candidate(candidate_input)
    self.assertIn(candidate["candidate_regime"], {"whipsaw", "insufficient_signal"})
    self.assertTrue(candidate["evidence_summary"])
```

- [ ] **Step 2: Run the screening test file and confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_screening_coverage_optimization.py -q
```

Expected:
- failures because the evidence-block and candidate helpers do not exist yet

- [ ] **Step 3: Implement evidence-block synthesis and scoring helpers**

In `month_end_shortlist_runtime.py`, add small pure helpers like:

```python
def synthesize_geopolitics_evidence_block(candidate_input: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(candidate_input, dict):
        return {"news_evidence": [], "x_evidence": [], "market_evidence": []}

    def make_row(source_type: str, signal_family: str, direction: str, strength: str, summary: str) -> dict[str, Any]:
        return {
            "source_type": source_type,
            "signal_family": signal_family,
            "direction": direction,
            "strength": strength,
            "summary": summary,
        }

    news_rows: list[dict[str, Any]] = []
    for row in candidate_input.get("news_signals", []):
        direction = row.get("direction_hint")
        if direction in GEOPOLITICS_CANDIDATE_DIRECTIONS:
            news_rows.append(
                make_row("news", "headline_flow", direction, "medium", row.get("summary") or row.get("headline") or "news signal")
            )

    x_rows: list[dict[str, Any]] = []
    for row in candidate_input.get("x_signals", []):
        direction = row.get("direction_hint")
        if direction in GEOPOLITICS_CANDIDATE_DIRECTIONS:
            x_rows.append(
                make_row("x", "x_discussion", direction, "medium", row.get("summary") or "x signal")
            )

    market_rows: list[dict[str, Any]] = []
    market = candidate_input.get("market_signals", {})
    if isinstance(market, dict):
        if market.get("oil") == "up":
            market_rows.append(make_row("market", "oil", "escalation", "medium", "Oil is confirming upside risk."))
        if market.get("oil") == "down":
            market_rows.append(make_row("market", "oil", "de_escalation", "medium", "Oil is unwinding risk premium."))
        if market.get("gold") == "up":
            market_rows.append(make_row("market", "gold", "escalation", "medium", "Gold is confirming safety demand."))
        if market.get("shipping") == "up":
            market_rows.append(make_row("market", "shipping", "escalation", "medium", "Shipping tape is repricing disruption risk."))
        if market.get("risk_style") == "risk_off":
            market_rows.append(make_row("market", "risk_style", "escalation", "medium", "Risk style is defensive."))
        if market.get("risk_style") == "risk_on":
            market_rows.append(make_row("market", "risk_style", "de_escalation", "medium", "Risk style is improving."))
        if market.get("risk_style") == "mixed":
            market_rows.append(make_row("market", "risk_style", "whipsaw", "low", "Risk style is mixed."))
        if market.get("airlines") == "down":
            market_rows.append(make_row("market", "airlines", "escalation", "medium", "Airlines are lagging."))
        if market.get("industrials") == "down":
            market_rows.append(make_row("market", "industrials", "escalation", "low", "Industrials are under pressure."))

    return {
        "news_evidence": news_rows,
        "x_evidence": x_rows,
        "market_evidence": market_rows,
    }


def build_macro_geopolitics_candidate(candidate_input: dict[str, Any] | None) -> dict[str, Any]:
    evidence = synthesize_geopolitics_evidence_block(candidate_input)
    all_rows = evidence["news_evidence"] + evidence["x_evidence"] + evidence["market_evidence"]
    if not all_rows:
        return {
            "candidate_regime": "insufficient_signal",
            "confidence": "low",
            "signal_alignment": "none",
            "status": "insufficient_signal",
            "evidence_summary": ["No usable geopolitical candidate signals were provided."],
        }

    source_alignment = {
        row["source_type"]: row["direction"]
        for row in all_rows
        if row["direction"] in GEOPOLITICS_CANDIDATE_DIRECTIONS
    }
    score = {"escalation": 0, "de_escalation": 0, "whipsaw": 0}
    weight = {"low": 1, "medium": 2, "high": 3}
    for row in all_rows:
        score[row["direction"]] += weight.get(row["strength"], 1)

    supporting_pairs = [
        "news+x",
        "news+market",
        "x+market",
    ]
    aligned_pair = next(
        (
            pair
            for pair in supporting_pairs
            if all(
                source_alignment.get(source) == max(score, key=score.get)
                for source in pair.split("+")
                if source in source_alignment
            )
            and all(source in source_alignment for source in pair.split("+"))
        ),
        None,
    )
    ordered = sorted(score.items(), key=lambda kv: kv[1], reverse=True)
    top_regime, top_score = ordered[0]
    second_score = ordered[1][1]
    if not aligned_pair or top_score - second_score < 2:
        return {
            "candidate_regime": "insufficient_signal",
            "confidence": "low",
            "signal_alignment": aligned_pair or "mixed",
            "status": "insufficient_signal",
            "evidence_summary": [row["summary"] for row in all_rows[:3]],
        }

    return {
        "candidate_regime": top_regime,
        "confidence": "high" if top_score >= 6 else "medium",
        "signal_alignment": "news+x+market" if {"news", "x", "market"}.issubset(source_alignment) else aligned_pair,
        "status": "candidate_only",
        "evidence_summary": [row["summary"] for row in all_rows[:3]],
        "beneficiary_bias": list((candidate_input or {}).get("beneficiary_chains", [])),
        "headwind_bias": list((candidate_input or {}).get("headwind_chains", [])),
        "evidence_block": evidence,
    }
```

- [ ] **Step 4: Attach the candidate block to enriched results without auto-overlay**

In `enrich_live_result_reporting(...)` and `merge_track_results(...)`, after `request_obj` is available, add:

```python
candidate_input = (
    request_obj.get("macro_geopolitics_candidate_input")
    if isinstance(request_obj, dict) and isinstance(request_obj.get("macro_geopolitics_candidate_input"), dict)
    else None
)
candidate_block = build_macro_geopolitics_candidate(candidate_input)
enriched["macro_geopolitics_candidate"] = candidate_block
```

Do **not** assign anything into `request_obj["macro_geopolitics_overlay"]`.

- [ ] **Step 5: Re-run the screening tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_screening_coverage_optimization.py -q
```

Expected:
- PASS

- [ ] **Step 6: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" add "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py" "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_screening_coverage_optimization.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" commit -m "feat: add geopolitics regime candidate synthesis"
```

### Task 4: Surface the candidate lightly in the report without stealing the stage

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Write failing report tests for the candidate block**

Add tests in `tests/test_month_end_shortlist_degraded_reporting.py` such as:

```python
def test_decision_flow_markdown_surfaces_geopolitics_candidate_summary(self) -> None:
    enriched = self._build_enriched_for_geopolitics_overlay()
    enriched["request"]["macro_geopolitics_candidate_input"] = {
        "news_signals": [{"headline": "Shipping risk rises", "summary": "Disruption fears climb", "direction_hint": "escalation"}],
        "x_signals": [{"account": "MacroDesk", "summary": "Supply risk repricing resumes", "direction_hint": "escalation"}],
        "market_signals": {"oil": "up", "gold": "up", "shipping": "up", "risk_style": "risk_off", "airlines": "down"},
    }
    enriched = module_under_test.enrich_live_result_reporting(
        enriched["result"],
        [],
        enriched.get("assessed_candidates", []),
        enriched.get("discovery_candidates", []),
    )
    self.assertIn("地缘候选判断", enriched["report_markdown"])
    self.assertIn("信号对齐", enriched["report_markdown"])


def test_candidate_block_does_not_claim_formal_overlay_acceptance(self) -> None:
    enriched = self._build_enriched_for_geopolitics_overlay()
    enriched["request"].pop("macro_geopolitics_overlay", None)
    enriched["request"]["macro_geopolitics_candidate_input"] = {
        "news_signals": [{"headline": "Shipping risk rises", "summary": "Disruption fears climb", "direction_hint": "escalation"}],
        "x_signals": [{"account": "MacroDesk", "summary": "Supply risk repricing resumes", "direction_hint": "escalation"}],
        "market_signals": {"oil": "up", "gold": "up", "shipping": "up", "risk_style": "risk_off", "airlines": "down"},
    }
    enriched = module_under_test.enrich_live_result_reporting(
        enriched["result"],
        [],
        enriched.get("assessed_candidates", []),
        enriched.get("discovery_candidates", []),
    )
    self.assertIn("状态：候选判断，尚未写入正式 overlay", enriched["report_markdown"])
```

- [ ] **Step 2: Run degraded-reporting tests and confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_degraded_reporting.py -q
```

Expected:
- failures because candidate summary/report synthesis does not exist yet

- [ ] **Step 3: Add candidate-report helpers and wire them into markdown generation**

In `month_end_shortlist_runtime.py`, add helpers like:

```python
def build_geopolitics_candidate_summary_lines(candidate: dict[str, Any] | None, overlay: dict[str, Any] | None) -> list[str]:
    if not isinstance(candidate, dict):
        return []
    regime = clean_text(candidate.get("candidate_regime")) or "insufficient_signal"
    confidence = clean_text(candidate.get("confidence")) or "low"
    signal_alignment = clean_text(candidate.get("signal_alignment")) or "mixed"
    status = clean_text(candidate.get("status")) or "candidate_only"
    status_text = {
        "candidate_only": "候选判断，尚未写入正式 overlay",
        "accepted_as_overlay": "候选已被采纳为正式 overlay",
        "conflicts_with_overlay": "候选与正式 overlay 不一致",
        "insufficient_signal": "当前多源信号不足以形成稳定候选",
    }.get(status, "候选判断，尚未写入正式 overlay")
    lines = [
        f"- 地缘候选判断：`{regime}`（{confidence}）",
        f"- 信号对齐：{signal_alignment}",
        f"- 状态：{status_text}",
    ]
    if isinstance(overlay, dict) and clean_text(overlay.get('regime_label')):
        lines.append(f"- 正式 overlay：`{clean_text(overlay.get('regime_label'))}`")
    return lines
```

Then extend `build_decision_flow_markdown(...)` or the summary/meta builder to append these lines before the cards:

```python
candidate = (
    enriched.get("macro_geopolitics_candidate")
    if isinstance(enriched.get("macro_geopolitics_candidate"), dict)
    else None
)
lines.extend(build_geopolitics_candidate_summary_lines(candidate, geopolitics_overlay))
```

Keep card references minimal. Do not add a long dedicated section.

- [ ] **Step 4: Re-run degraded-reporting tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_degraded_reporting.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" add "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py" "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_degraded_reporting.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" commit -m "feat: surface geopolitics regime candidate in report"
```

### Task 5: Focused verification and deterministic smoke

**Files:**
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_profile_passthrough.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_screening_coverage_optimization.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_board_threshold_overrides.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_degraded_reporting.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_earnings_momentum_discovery.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_discovery_merge.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_x_style_assisted_shortlist.py`

- [ ] **Step 1: Run the focused shortlist suite**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_board_threshold_overrides.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_degraded_reporting.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_earnings_momentum_discovery.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_month_end_shortlist_discovery_merge.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\tests\test_x_style_assisted_shortlist.py -q
```

Expected:
- all tests pass

- [ ] **Step 2: Generate a deterministic smoke artifact**

Create a minimal runtime smoke script or fixture that feeds:

```python
request = {
    "target_date": "2026-04-21",
    "filter_profile": "month_end_event_support_transition",
    "macro_geopolitics_candidate_input": {
        "news_signals": [
            {
                "source": "ap",
                "headline": "Shipping disruption fears rise",
                "summary": "Hormuz disruption risk repriced.",
                "direction_hint": "escalation",
            }
        ],
        "x_signals": [
            {
                "account": "MacroDesk",
                "summary": "Energy traders lean toward renewed supply fear.",
                "direction_hint": "escalation",
            }
        ],
        "market_signals": {
            "oil": "up",
            "gold": "up",
            "shipping": "up",
            "risk_style": "risk_off",
            "airlines": "down",
            "industrials": "down",
        },
    },
}
```

Then call `enrich_live_result_reporting(...)` with one simple assessed candidate and write outputs to:

- `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\.tmp\geopolitics-candidate-smoke\result.json`
- `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate\.tmp\geopolitics-candidate-smoke\report.md`

- [ ] **Step 3: Verify smoke artifact content**

Check that:

- `result.json` contains `macro_geopolitics_candidate`
- `macro_geopolitics_candidate.candidate_regime == "escalation"` or a justified conservative fallback
- `result.json` still lacks auto-written `macro_geopolitics_overlay` unless it was supplied explicitly
- `report.md` contains:
  - `地缘候选判断`
  - `信号对齐`
  - `状态`

- [ ] **Step 4: Commit only if a durable fixture was added**

If a reusable fixture or helper script was added under tracked repo paths, commit it:

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" add <tracked-fixture-or-helper>
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-geopolitics-regime-candidate" commit -m "test: add geopolitics regime candidate smoke fixture"
```

If the smoke artifacts only live under `.tmp`, do not commit them.

## Self-Review

- Spec coverage:
  - mixed candidate input contract: Task 2
  - evidence-block synthesis: Task 3
  - deterministic regime scoring and conservative fallback: Task 3
  - candidate separate from overlay: Tasks 2-4
  - lightweight report surfacing: Task 4
  - focused verification and smoke: Task 5
- Placeholder scan:
  - no `TODO`, `TBD`, or “similar to previous task” shortcuts
  - all code-touching steps include concrete code blocks
  - all verification steps include exact commands and expected outcomes
- Type consistency:
  - `macro_geopolitics_candidate_input`
  - `macro_geopolitics_candidate`
  - `candidate_regime`
  - `signal_alignment`
  - `status`
  - `evidence_summary`
  - `build_macro_geopolitics_candidate(...)`
  - `synthesize_geopolitics_evidence_block(...)`
