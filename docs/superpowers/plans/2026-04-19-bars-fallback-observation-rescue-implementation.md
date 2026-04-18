# Bars Fallback Observation Rescue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a balanced bars-fallback rescue path so provider failures can preserve a small set of evidence-backed names as clearly labeled low-confidence `T3` observation candidates instead of collapsing them into mass `bars_fetch_failed` blocks.

**Architecture:** Keep the compiled shortlist core unchanged and implement the fallback entirely in wrapper/runtime space. When primary bars fail, consult an existing repo-local market snapshot path, evaluate whether the candidate has sufficient structured/discovery/chain support plus a non-broken snapshot, and rescue only those names into explicitly labeled low-confidence `T3`, never `T1`.

**Tech Stack:** Python, pytest, `month_end_shortlist_runtime.py`, existing tradingagents local-market snapshot helpers, markdown report synthesis.

---

### Task 1: Create an isolated worktree for the bars-fallback rescue branch

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean`

- [ ] **Step 1: Create a fresh feature worktree**

Run:

```bash
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" -c safe.directory="D:/Users/rickylu/dev/financial-services-plugins-clean" worktree add "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" -b feat/bars-fallback-rescue main
```

Expected:
- a new worktree exists at `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue`
- branch `feat/bars-fallback-rescue` points at current `main`

- [ ] **Step 2: Verify the worktree branch**

Run:

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" -c safe.directory="D:/Users/rickylu/dev/.worktrees/financial-services-plugins-clean/feat-bars-fallback-rescue" status --short --branch
```

Expected:

```text
## feat/bars-fallback-rescue
```

- [ ] **Step 3: Restore baseline compiled artifacts if the worktree cannot import runtime**

If baseline pytest fails with:

```text
Compiled month_end_shortlist_runtime artifact is missing
```

copy the two existing `.pyc` files from the main repo into the worktree:

```powershell
New-Item -ItemType Directory -Force "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\short-horizon-shortlist\scripts\__pycache__" | Out-Null
Copy-Item "D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\short-horizon-shortlist\scripts\__pycache__\month_end_shortlist_runtime.cpython-312.pyc" "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\short-horizon-shortlist\scripts\__pycache__\month_end_shortlist_runtime.cpython-312.pyc" -Force
Copy-Item "D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\short-horizon-shortlist\scripts\__pycache__\month_end_shortlist.cpython-312.pyc" "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\short-horizon-shortlist\scripts\__pycache__\month_end_shortlist.cpython-312.pyc" -Force
```

- [ ] **Step 4: Verify baseline with a small focused test**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py -q
```

Expected:
- baseline test imports and passes

### Task 2: Introduce local-market snapshot rescue helpers and failing tests

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py`
- Test: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py`

- [ ] **Step 1: Add failing tests for rescue eligibility**

Extend `tests/test_screening_coverage_optimization.py` with a new test class, for example:

```python
class TestBarsFallbackRescue(unittest.TestCase):
    def _make_failed_candidate(self, ticker="601975.SS", **overrides):
        base = {
            "ticker": ticker,
            "name": ticker,
            "adjusted_total_score": 0.0,
            "score": 0.0,
            "keep": False,
            "midday_status": "blocked",
            "hard_filter_failures": ["bars_fetch_failed"],
            "bars_fetch_error": f"bars_fetch_failed for `{ticker}`: boom",
            "tier_tags": [],
            "structured_catalyst_snapshot": {},
            "track_name": "main_board",
        }
        base.update(overrides)
        return base

    def test_bars_failed_candidate_with_structured_support_and_snapshot_is_rescued_to_t3(self):
        candidate = self._make_failed_candidate(
            structured_catalyst_snapshot={"structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]},
        )
        snapshot = {
            "close": 5.8,
            "pct_chg": 1.2,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 58.0,
            "volume_ratio": 1.4,
        }
        rescued = runtime.build_bars_fallback_rescue_candidate(candidate, snapshot)
        self.assertIsNotNone(rescued)
        self.assertIn("low_confidence_fallback", rescued["tier_tags"])
        self.assertEqual(rescued["fallback_support_reason"], "structured_catalyst")

    def test_bars_failed_candidate_without_support_is_not_rescued(self):
        candidate = self._make_failed_candidate()
        snapshot = {
            "close": 5.8,
            "pct_chg": 1.2,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 58.0,
            "volume_ratio": 1.4,
        }
        rescued = runtime.build_bars_fallback_rescue_candidate(candidate, snapshot)
        self.assertIsNone(rescued)

    def test_bars_failed_candidate_with_broken_snapshot_is_not_rescued(self):
        candidate = self._make_failed_candidate(
            discovery_bucket="watch",
        )
        snapshot = {
            "close": 4.2,
            "pct_chg": -6.0,
            "sma20": 5.5,
            "sma50": 5.3,
            "rsi14": 31.0,
            "volume_ratio": 0.6,
        }
        rescued = runtime.build_bars_fallback_rescue_candidate(candidate, snapshot)
        self.assertIsNone(rescued)
```

Also extend `tests/test_month_end_shortlist_candidate_fetch_fallback.py` with a failing test proving the wrapper still converts raw provider exceptions into a failed candidate first:

```python
def test_bars_fetch_failure_record_keeps_original_error_text(self) -> None:
    wrapped = module_under_test.wrap_assess_candidate_with_bars_failure_fallback(
        lambda candidate, request, benchmark_rows, *, bars_fetcher, html_fetcher: (_ for _ in ()).throw(
            RuntimeError("bars_fetch_failed for `601975.SS`: Eastmoney request failed: Remote end closed connection without response")
        )
    )

    result = wrapped(
        {"ticker": "601975.SS", "name": "招商南油"},
        {},
        [],
        bars_fetcher=lambda *args, **kwargs: [],
        html_fetcher=lambda *args, **kwargs: "",
    )

    self.assertIn("bars_fetch_failed", result["hard_filter_failures"])
    self.assertIn("Eastmoney request failed", result["bars_fetch_error"])
```

- [ ] **Step 2: Run the two targeted test files to confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py -q
```

Expected:
- at least one failure because rescue helpers do not exist yet

- [ ] **Step 3: Add secondary snapshot and rescue helpers**

In `month_end_shortlist_runtime.py`, add small pure helpers:

```python
def local_market_snapshot_for_candidate(ticker: str, analysis_date: str) -> dict[str, Any] | None:
    from tradingagents_decision_bridge_runtime import smart_free_profile_name, summarize_local_market_snapshot

    normalized_ticker = clean_text(ticker)
    if not normalized_ticker:
        return None
    profile_name = smart_free_profile_name(normalized_ticker)
    if profile_name != "free_eastmoney_market":
        return None
    try:
        snapshot = summarize_local_market_snapshot(
            profile_name=profile_name,
            normalized_ticker=normalized_ticker,
            analysis_date=analysis_date,
            failure_message="month_end_shortlist bars fallback",
        )
    except Exception:
        return None
    if not isinstance(snapshot, dict):
        return None
    return {
        "profile_name": profile_name,
        "close": snapshot.get("latest_close"),
        "pct_chg": snapshot.get("latest_pct_chg"),
        "sma20": snapshot.get("sma20"),
        "sma50": snapshot.get("sma50"),
        "rsi14": snapshot.get("rsi14"),
        "volume_ratio": snapshot.get("volume_ratio"),
    }


def classify_fallback_support_reason(candidate: dict[str, Any]) -> str:
    structured = safe_dict(candidate.get("structured_catalyst_snapshot"))
    if safe_list(structured.get("structured_company_events")):
        return "structured_catalyst"
    bucket = clean_text(candidate.get("discovery_bucket"))
    if bucket == "qualified":
        return "discovery_qualified"
    if bucket == "watch":
        return "discovery_watch"
    if clean_text(candidate.get("chain_name")) or clean_text(candidate.get("trading_profile_bucket")):
        return "chain_support"
    return ""


def snapshot_allows_fallback_observation(snapshot: dict[str, Any] | None) -> bool:
    if not isinstance(snapshot, dict):
        return False
    close = snapshot.get("close")
    sma20 = snapshot.get("sma20")
    sma50 = snapshot.get("sma50")
    rsi14 = snapshot.get("rsi14")
    pct_chg = snapshot.get("pct_chg")
    try:
        close_f = float(close)
        sma20_f = float(sma20)
        sma50_f = float(sma50)
        rsi_f = float(rsi14)
        pct_f = float(pct_chg)
    except (TypeError, ValueError):
        return False
    if close_f < min(sma20_f, sma50_f):
        return False
    if rsi_f < 35.0:
        return False
    if pct_f <= -5.0:
        return False
    return True


def build_bars_fallback_rescue_candidate(candidate: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    reason = classify_fallback_support_reason(candidate)
    if not reason or not snapshot_allows_fallback_observation(snapshot):
        return None
    rescued = deepcopy(candidate)
    rescued["fallback_support_reason"] = reason
    rescued["fallback_snapshot"] = deepcopy(snapshot)
    rescued["tier_tags"] = unique_strings(list(rescued.get("tier_tags", [])) + ["low_confidence_fallback", "fallback_snapshot_only"])
    rescued["midday_status"] = "near_miss"
    rescued["wrapper_tier"] = "T3"
    return rescued
```

- [ ] **Step 4: Re-run the two targeted test files**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" add -- "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py" "tests/test_screening_coverage_optimization.py" "tests/test_month_end_shortlist_candidate_fetch_fallback.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" commit -m "feat: add bars fallback rescue helpers"
```

### Task 3: Rescue supported `bars_fetch_failed` names into low-confidence `T3`

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py`

- [ ] **Step 1: Add failing integration tests for track-level rescue**

Extend `tests/test_screening_coverage_optimization.py` with tests such as:

```python
def test_enrich_track_result_rescues_structured_support_name_into_low_confidence_t3(self):
    result = {
        "filter_summary": {"kept_count": 0, "keep_threshold": 58.0, "profile": "month_end_event_support_transition"},
        "request": {"analysis_time": "2026-04-19T12:00:00+08:00"},
        "dropped": [],
        "report_markdown": "# Test\\n",
    }
    assessed = [{
        "ticker": "601975.SS",
        "name": "招商南油",
        "adjusted_total_score": 0.0,
        "keep": False,
        "hard_filter_failures": ["bars_fetch_failed"],
        "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
        "structured_catalyst_snapshot": {"structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]},
        "tier_tags": [],
    }]
    enriched = runtime.enrich_track_result(
        result,
        [],
        assessed_candidates=assessed,
        track_name="main_board",
        track_config=runtime.TRACK_CONFIGS["main_board"],
    )
    tickers = [row["ticker"] for row in enriched["tier_output"]["T3"]]
    self.assertIn("601975.SS", tickers)
    rescued = next(row for row in enriched["tier_output"]["T3"] if row["ticker"] == "601975.SS")
    self.assertIn("low_confidence_fallback", rescued["tier_tags"])
    self.assertEqual(rescued["fallback_support_reason"], "structured_catalyst")


def test_enrich_track_result_never_promotes_fallback_name_to_t1(self):
    result = {
        "filter_summary": {"kept_count": 0, "keep_threshold": 58.0, "profile": "month_end_event_support_transition"},
        "request": {"analysis_time": "2026-04-19T12:00:00+08:00"},
        "dropped": [],
        "report_markdown": "# Test\\n",
    }
    assessed = [{
        "ticker": "601975.SS",
        "name": "招商南油",
        "adjusted_total_score": 88.0,
        "keep": False,
        "hard_filter_failures": ["bars_fetch_failed"],
        "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
        "structured_catalyst_snapshot": {"structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]},
        "tier_tags": [],
    }]
    enriched = runtime.enrich_track_result(
        result,
        [],
        assessed_candidates=assessed,
        track_name="main_board",
        track_config=runtime.TRACK_CONFIGS["main_board"],
    )
    self.assertNotIn("601975.SS", [row["ticker"] for row in enriched["tier_output"]["T1"]])
```

- [ ] **Step 2: Run the screening test file and confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py -q
```

Expected:
- failure because the current track enrichment still leaves `bars_fetch_failed` names blocked

- [ ] **Step 3: Integrate rescue into track enrichment**

In `month_end_shortlist_runtime.py`, inside `enrich_track_result(...)`, after track-level assessed candidates are available and before final tier assembly, rescue supported failed names:

```python
analysis_date = clean_text((result.get("request") or {}).get("analysis_time") or (result.get("request") or {}).get("target_date") or "")
rescued_fallback_rows: list[dict[str, Any]] = []
for candidate in diagnostic_scorecard:
    failures = set(candidate.get("hard_filter_failures", []))
    if "bars_fetch_failed" not in failures:
        continue
    snapshot = local_market_snapshot_for_candidate(clean_text(candidate.get("ticker")), analysis_date)
    rescued = build_bars_fallback_rescue_candidate(candidate, snapshot)
    if rescued:
        rescued_fallback_rows.append(rescued)
        if clean_text(candidate.get("ticker")) not in {clean_text(row.get("ticker")) for row in near_miss_candidates}:
            near_miss_candidates.append(rescued)
```

Then ensure these rescued rows are only ever appended into the observation source for `T3`, not passed into `T1` as kept names. If needed, preserve a dedicated field such as:

```python
enriched["bars_fallback_rescues"] = rescued_fallback_rows
```

- [ ] **Step 4: Re-run the screening test file**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" add -- "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py" "tests/test_screening_coverage_optimization.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" commit -m "feat: rescue supported bars failures into low-confidence T3"
```

### Task 4: Surface fallback identity clearly in decision flow and report cards

**Files:**
- Modify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`
- Test: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py`

- [ ] **Step 1: Add failing report-label tests**

Extend `tests/test_month_end_shortlist_degraded_reporting.py` with assertions like:

```python
def test_decision_flow_marks_rescued_name_as_low_confidence_fallback(self) -> None:
    result = {
        "filter_summary": {"kept_count": 0, "keep_threshold": 70.0},
        "request": {"analysis_time": "2026-04-19T12:00:00+08:00"},
        "dropped": [],
        "top_picks": [],
        "report_markdown": "# Month-End Shortlist Report: 2026-04-21\\n",
    }
    assessed_candidates = [{
        "ticker": "601975.SS",
        "name": "招商南油",
        "adjusted_total_score": 0.0,
        "keep": False,
        "hard_filter_failures": ["bars_fetch_failed"],
        "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
        "structured_catalyst_snapshot": {"structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]},
        "tier_tags": [],
    }]
    enriched = module_under_test.enrich_live_result_reporting(result, [], assessed_candidates)
    flow = enriched["report_markdown"].split("## 决策流", 1)[1]
    self.assertIn("继续观察（low-confidence fallback）", flow)
    self.assertIn("数据路径降级：local market snapshot only", flow)
```

- [ ] **Step 2: Run degraded-reporting tests and confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py -q
```

Expected:
- failure because the current report path does not distinguish fallback rescues

- [ ] **Step 3: Add fallback-specific title and card phrasing**

In `month_end_shortlist_runtime.py`, update decision/report synthesis helpers so rescued names render differently.

In `build_decision_flow_card(...)`, add logic like:

```python
is_fallback = "low_confidence_fallback" in set(card.get("tier_tags", []))
action_label = action
if is_fallback and action == "继续观察":
    action_label = "继续观察（low-confidence fallback）"

operation_parts = [build_trading_profile_playbook(card), clean_text(card.get("trade_card", {}).get("watch_action"))]
if is_fallback:
    operation_parts.append("数据路径降级：local market snapshot only")
    reason = clean_text(card.get("fallback_support_reason"))
    if reason:
        operation_parts.append(f"保留原因：{reason}")
```

Then make sure the markdown title line uses `action_label`, not the raw action:

```python
f"### {item.get('ticker')} | {item.get('action_label', item.get('action'))} | ..."
```

If the card object does not yet carry `action_label`, add it in the flow-card output.

- [ ] **Step 4: Re-run degraded-reporting tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" add -- "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py" "tests/test_month_end_shortlist_degraded_reporting.py"
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" commit -m "feat: label bars fallback rescue candidates in reports"
```

### Task 5: Focused verification and real shortlist smoke

**Files:**
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_profile_passthrough.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_board_threshold_overrides.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_earnings_momentum_discovery.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_discovery_merge.py`
- Verify: `D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_x_style_assisted_shortlist.py`

- [ ] **Step 1: Run the focused shortlist suite**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_candidate_fetch_fallback.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_screening_coverage_optimization.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_degraded_reporting.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_profile_passthrough.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_board_threshold_overrides.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_earnings_momentum_discovery.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_month_end_shortlist_discovery_merge.py D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\tests\test_x_style_assisted_shortlist.py -q
```

Expected:
- all tests pass

- [ ] **Step 2: Run a real shortlist smoke with the existing geopolitics-candidate request**

Use the existing real request:

```text
D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\request.full.geopolitics-candidate.json
```

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist.py D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\next-session-2026-04-21\request.full.geopolitics-candidate.json --output D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\.tmp\next-session-2026-04-21\result.full.fallback.json --markdown-output D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue\.tmp\next-session-2026-04-21\report.full.fallback.md
```

Expected:
- the run completes successfully
- some names that previously became mass `bars_fetch_failed` now appear as low-confidence fallback `T3`
- the report contains:
  - `继续观察（low-confidence fallback）`
  - `数据路径降级：local market snapshot only`

- [ ] **Step 3: Verify smoke artifacts**

Check:

- `result.full.fallback.json` contains rescued rows with:
  - `low_confidence_fallback`
  - `fallback_support_reason`
  - `fallback_snapshot_only`
- rescued rows are in `T3`, not `T1`
- `report.full.fallback.md` shows fallback labeling clearly

- [ ] **Step 4: Commit only if a tracked helper/fixture was added**

If you add any durable tracked helper or fixture file outside `.tmp`, commit it:

```bash
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" add <tracked-helper-or-fixture>
git -C "D:\Users\rickylu\dev\.worktrees\financial-services-plugins-clean\feat-bars-fallback-rescue" commit -m "test: add bars fallback rescue smoke fixture"
```

If smoke artifacts remain under `.tmp` only, do not commit them.

## Self-Review

- Spec coverage:
  - secondary source reuse: Tasks 2-3
  - support-based rescue gating: Tasks 2-3
  - low-confidence `T3` only: Tasks 3-4
  - explicit report labeling: Task 4
  - focused verification and smoke: Task 5
- Placeholder scan:
  - no `TODO`, `TBD`, or “similar to previous task” shortcuts
  - all code steps include concrete code blocks
  - all verification steps include exact commands and expected outcomes
- Type consistency:
  - `low_confidence_fallback`
  - `fallback_support_reason`
  - `fallback_snapshot_only`
  - `local_market_snapshot_for_candidate(...)`
  - `classify_fallback_support_reason(...)`
  - `snapshot_allows_fallback_observation(...)`
  - `build_bars_fallback_rescue_candidate(...)`
