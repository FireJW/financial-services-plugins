# Cache-First Execution Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing Eastmoney cache fallback, non-trading-day baseline, and degraded rescue pieces into one coherent cache-first execution path that keeps more names alive, downgrades one-day-stale cache honestly, and surfaces live/cache/blocked state in the final shortlist output.

**Architecture:** Keep the work inside `month_end_shortlist_runtime.py`. Add one small execution-state classifier, reuse the existing fresh-cache and stale-cache rescue hooks, prune rescued names out of the blocked wall after tier assembly, and attach a merged `bars_source_summary` to `filter_summary` so the report and decision-flow cards can describe cache-first closure consistently. Do not add a new runtime entrypoint or a new provider.

**Tech Stack:** Python, pytest, `month_end_shortlist_runtime.py`, existing Eastmoney cache helpers, existing shortlist reporting / decision-flow rendering.

---

### Task 1: Standardize per-candidate execution-state classification

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Add failing tests for live / fresh-cache / stale-cache / blocked execution states**

Extend `tests/test_month_end_shortlist_candidate_fetch_fallback.py` with:

```python
    def test_infer_execution_state_defaults_plain_candidates_to_live(self) -> None:
        state = module_under_test.infer_execution_state(
            {
                "ticker": "601600.SS",
                "name": "中国铝业",
                "hard_filter_failures": [],
            }
        )
        self.assertEqual(state, "live")

    def test_bars_fetch_failure_record_is_marked_as_blocked_execution_state(self) -> None:
        failed = module_under_test.build_bars_fetch_failed_candidate(
            {"ticker": "601975.SS", "name": "招商南油"},
            RuntimeError("bars_fetch_failed for `601975.SS`: Eastmoney request failed"),
        )
        self.assertEqual(failed["execution_state"], "blocked")

    def test_wrap_assess_candidate_recovers_from_same_day_eastmoney_cache(self) -> None:
        rows = [
            {"date": "2026-04-17", "close": 5.5},
            {"date": "2026-04-18", "close": 5.8},
        ]

        def base_assess(candidate, request, benchmark_rows, *, bars_fetcher, html_fetcher):
            fetched_rows = bars_fetcher(candidate["ticker"], "2026-04-01", "2026-04-18")
            return {
                "ticker": candidate["ticker"],
                "name": candidate["name"],
                "keep": True,
                "hard_filter_failures": [],
                "scores": {"adjusted_total_score": 75.0},
                "score_components": {"adjusted_total_score": 75.0},
                "bars_row_count": len(fetched_rows),
            }

        wrapped = module_under_test.wrap_assess_candidate_with_bars_failure_fallback(base_assess)

        with patch.object(module_under_test, "eastmoney_cached_bars_for_candidate", return_value=rows):
            result = wrapped(
                {"ticker": "601975.SS", "name": "招商南油"},
                {"analysis_time": "2026-04-18T15:00:00+08:00"},
                [],
                bars_fetcher=lambda *args, **kwargs: (_ for _ in ()).throw(
                    RuntimeError("bars_fetch_failed for `601975.SS`: Eastmoney request failed")
                ),
                html_fetcher=lambda *args, **kwargs: "",
            )

        self.assertTrue(result["keep"])
        self.assertEqual(result["bars_source"], "eastmoney_cache")
        self.assertEqual(result["execution_state"], "fresh_cache")
```

Then extend `tests/test_screening_coverage_optimization.py` by tightening the stale-cache rescue assertion:

```python
    def test_one_day_stale_cache_with_support_can_rescue_into_low_confidence_t3(self):
        candidate = self._make_failed_candidate(
            structured_catalyst_snapshot={
                "structured_company_events": [{"date": "2026-04-21", "event_type": "油运景气跟踪"}]
            }
        )
        rows = [
            {"date": "2026-04-17", "close": 5.5, "pct_chg": 0.8, "boll": 5.3, "close_50_sma": 5.1, "rsi": 56.0, "volume_ratio": 1.2},
            {"date": "2026-04-18", "close": 5.8, "pct_chg": 1.2, "boll": 5.5, "close_50_sma": 5.3, "rsi": 58.0, "volume_ratio": 1.4},
        ]
        recovered = runtime.build_bars_cache_rescue_candidate(candidate, rows, "2026-04-19")
        self.assertIsNotNone(recovered)
        self.assertIn("low_confidence_fallback", recovered["tier_tags"])
        self.assertIn("fallback_cache_only", recovered["tier_tags"])
        self.assertEqual(recovered["fallback_support_reason"], "structured_catalyst")
        self.assertEqual(recovered["execution_state"], "stale_cache")
```

- [ ] **Step 2: Run the two focused files to verify failure**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py" -q
```

Expected:
- FAIL because `infer_execution_state` does not exist yet
- FAIL because fresh-cache and stale-cache candidates do not yet carry `execution_state`

- [ ] **Step 3: Implement the minimal execution-state classifier and propagate it through existing cache paths**

Add this helper near the current cache helpers in `month_end_shortlist_runtime.py`:

```python
def infer_execution_state(candidate: dict[str, Any]) -> str:
    tier_tags = set(candidate.get("tier_tags", []) or [])
    failures = set(candidate.get("hard_filter_failures", []) or [])
    if candidate.get("fallback_cache_only") or "fallback_cache_only" in tier_tags:
        return "stale_cache"
    if clean_text(candidate.get("bars_source")) == "eastmoney_cache":
        return "fresh_cache"
    if candidate.get("fallback_snapshot_only") or "bars_fetch_failed" in failures:
        return "blocked"
    return "live"
```

Update the existing runtime-produced candidate shapes so they carry the field explicitly:

```python
def build_bars_fetch_failed_candidate(candidate: dict[str, Any], error: Exception | str) -> dict[str, Any]:
    ticker = str(candidate.get("ticker", "")).strip()
    name = str(candidate.get("name", "")).strip()
    return {
        "ticker": ticker,
        "name": name,
        "code": str(candidate.get("code", "")).strip(),
        "sector": str(candidate.get("sector", "")).strip(),
        "board": str(candidate.get("board", "")).strip(),
        "price": candidate.get("price"),
        "open": candidate.get("open"),
        "high": candidate.get("high"),
        "low": candidate.get("low"),
        "pre_close": candidate.get("pre_close"),
        "day_pct": candidate.get("day_pct"),
        "pct_from_60d": candidate.get("pct_from_60d"),
        "pct_from_ytd": candidate.get("pct_from_ytd"),
        "pe_ttm": candidate.get("pe_ttm"),
        "pb": candidate.get("pb"),
        "free_float_market_cap": candidate.get("free_float_market_cap"),
        "total_market_cap": candidate.get("total_market_cap"),
        "turnover_rate_pct": candidate.get("turnover_rate_pct"),
        "day_turnover_cny": candidate.get("day_turnover_cny"),
        "day_volume_shares": candidate.get("day_volume_shares"),
        "keep": False,
        "top_pick_eligible": False,
        "hard_filter_failures": ["bars_fetch_failed"],
        "scores": {},
        "score_components": {
            "trend_template_score": 0.0,
            "rs_and_leadership_score": 0.0,
            "fundamental_acceleration_score": 0.0,
            "structured_catalyst_score": 0.0,
            "vcp_or_contraction_score": 0.0,
            "liquidity_and_participation_score": 0.0,
            "cap_multiplier": 1.0,
            "raw_total_score": 0.0,
            "adjusted_total_score": 0.0,
        },
        "price_snapshot": {},
        "trend_template": {},
        "structured_catalyst_snapshot": {},
        "fundamental_snapshot": {},
        "vcp_snapshot": {},
        "cap_snapshot": {},
        "price_paths": {},
        "backtest_summary": {},
        "trade_card": {},
        "bars_fetch_error": str(error or "").strip(),
        "execution_state": "blocked",
    }
```

```python
def build_bars_fallback_rescue_candidate(candidate: dict[str, Any], snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    support_reason = classify_fallback_support_reason(candidate)
    if not support_reason or not snapshot_allows_fallback_observation(snapshot):
        return None
    rescued = deepcopy(candidate)
    rescued["keep"] = False
    rescued["midday_status"] = "near_miss"
    rescued["wrapper_tier"] = "T3"
    rescued["fallback_support_reason"] = support_reason
    rescued["fallback_snapshot"] = deepcopy(snapshot)
    rescued["fallback_snapshot_only"] = True
    rescued["execution_state"] = "blocked"
    rescued["tier_tags"] = unique_strings(
        list(rescued.get("tier_tags", [])) + ["low_confidence_fallback", "fallback_snapshot_only"]
    )
    return rescued
```

```python
def build_bars_cache_rescue_candidate(
    candidate: dict[str, Any],
    cached_rows: list[dict[str, Any]] | None,
    target_trade_date: str,
) -> dict[str, Any] | None:
    cache_mode = classify_eastmoney_cache_freshness(cached_rows or [], target_trade_date)
    if cache_mode.get("mode") != "stale_one_day":
        return None
    snapshot_rows = list(cached_rows or [])
    if not snapshot_rows:
        return None
    latest = snapshot_rows[-1]
    snapshot = {
        "close": latest.get("close"),
        "pct_chg": latest.get("pct_chg"),
        "sma20": latest.get("boll"),
        "sma50": latest.get("close_50_sma"),
        "rsi14": latest.get("rsi"),
        "volume_ratio": latest.get("volume_ratio"),
    }
    rescued = build_bars_fallback_rescue_candidate(candidate, snapshot)
    if not rescued:
        return None
    rescued["bars_source"] = "eastmoney_cache"
    rescued["fallback_cache_only"] = True
    rescued["execution_state"] = "stale_cache"
    rescued["tier_tags"] = unique_strings(
        list(rescued.get("tier_tags", [])) + ["fallback_cache_only"]
    )
    return rescued
```

And when same-day cache successfully replays the base assess flow, tag it before returning:

```python
                        try:
                            assessed = base_assess_candidate(
                                candidate,
                                request,
                                benchmark_rows,
                                bars_fetcher=cached_bars_fetcher,
                                html_fetcher=html_fetcher,
                            )
                            assessed["bars_source"] = "eastmoney_cache"
                            assessed["execution_state"] = "fresh_cache"
                            if assessed_log is not None:
                                assessed_log.append(deepcopy(assessed))
                            return assessed
```

Export `infer_execution_state` in `__all__`.

- [ ] **Step 4: Re-run the focused tests**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py" -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- `
  "tests/test_month_end_shortlist_candidate_fetch_fallback.py" `
  "tests/test_screening_coverage_optimization.py" `
  "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: classify shortlist execution states"
```

### Task 2: Remove rescued cache candidates from the blocked wall

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Add failing tests for blocked-section pruning after stale-cache rescue**

Extend `tests/test_month_end_shortlist_degraded_reporting.py` with:

```python
    def test_prune_rescued_blocked_candidates_removes_cache_rescues_from_blocked_wall(self) -> None:
        enriched = {
            "filter_summary": {
                "blocked_candidate_count": 1,
                "bars_fetch_failed_tickers": ["601975.SS"],
            },
            "blocked_candidates": [
                {
                    "ticker": "601975.SS",
                    "name": "招商南油",
                    "bars_fetch_error": "bars_fetch_failed for `601975.SS`: Eastmoney request failed",
                }
            ],
            "report_markdown": "# Test Report\n\n## Blocked Candidates\n\n- `601975.SS` 招商南油: `bars_fetch_failed for `601975.SS`: Eastmoney request failed`\n",
        }

        pruned = module_under_test.prune_rescued_blocked_candidates(
            enriched,
            [
                {
                    "ticker": "601975.SS",
                    "execution_state": "stale_cache",
                    "fallback_cache_only": True,
                }
            ],
        )

        self.assertEqual(pruned["filter_summary"]["blocked_candidate_count"], 0)
        self.assertEqual(pruned["filter_summary"]["bars_fetch_failed_tickers"], [])
        self.assertEqual(pruned["blocked_candidates"], [])
        self.assertNotIn("## Blocked Candidates", pruned["report_markdown"])
```

- [ ] **Step 2: Run the reporting test file to confirm failure**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- FAIL because `prune_rescued_blocked_candidates` does not exist yet

- [ ] **Step 3: Add a blocked-section renderer plus a pruning helper, then call it after tier rescue**

Refactor the blocked-section rendering in `month_end_shortlist_runtime.py` so it is reusable:

```python
def render_blocked_candidates_section(blocked_candidates: list[dict[str, Any]]) -> str:
    if not blocked_candidates:
        return ""
    lines = ["## Blocked Candidates", ""]
    for item in blocked_candidates:
        ticker = clean_text(item.get("ticker")) or "unknown"
        name = clean_text(item.get("name")) or ticker
        reason = clean_text(item.get("bars_fetch_error")) or "bars_fetch_failed"
        lines.append(f"- `{ticker}` {name}: `{reason}`")
    return "\n".join(lines).strip()


def replace_blocked_candidates_section(report_markdown: str, blocked_candidates: list[dict[str, Any]]) -> str:
    body = str(report_markdown or "").rstrip()
    marker = "\n## Blocked Candidates"
    if marker in body:
        body = body.split(marker, 1)[0].rstrip()
    section = render_blocked_candidates_section(blocked_candidates)
    if not section:
        return body + ("\n" if body else "")
    return "\n\n".join(part for part in [body, section] if part).strip() + "\n"
```

Use the renderer inside `enrich_degraded_live_result` instead of hand-building the section inline, then add:

```python
def prune_rescued_blocked_candidates(
    enriched: dict[str, Any],
    rescued_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    rescued_tickers = {
        clean_text(item.get("ticker"))
        for item in rescued_rows
        if isinstance(item, dict) and clean_text(item.get("ticker"))
    }
    if not rescued_tickers:
        return enriched

    updated = deepcopy(enriched)
    blocked_candidates = [
        item
        for item in updated.get("blocked_candidates", [])
        if isinstance(item, dict) and clean_text(item.get("ticker")) not in rescued_tickers
    ]
    updated["blocked_candidates"] = blocked_candidates

    filter_summary = dict(updated.get("filter_summary") or {})
    filter_summary["blocked_candidate_count"] = len(blocked_candidates)
    filter_summary["bars_fetch_failed_tickers"] = [
        clean_text(item.get("ticker"))
        for item in blocked_candidates
        if clean_text(item.get("ticker"))
    ]
    updated["filter_summary"] = filter_summary
    updated["report_markdown"] = replace_blocked_candidates_section(
        updated.get("report_markdown") or "",
        blocked_candidates,
    )
    return updated
```

After `rescued_by_ticker` is assembled in both rescue loops, replace the existing block with:

```python
        if rescued_by_ticker:
            enriched["bars_fallback_rescues"] = list(rescued_by_ticker.values())
            for tier_name in ("T1", "T2", "T4"):
                tiers[tier_name] = [
                    item
                    for item in tiers.get(tier_name, [])
                    if clean_text(item.get("ticker")) not in rescued_by_ticker
                ]
            t3_rows = [
                item
                for item in tiers.get("T3", [])
                if clean_text(item.get("ticker")) not in rescued_by_ticker
            ]
            t3_rows.extend(rescued_by_ticker.values())
            tiers["T3"] = t3_rows
            enriched = prune_rescued_blocked_candidates(enriched, list(rescued_by_ticker.values()))
```

Export `prune_rescued_blocked_candidates`, `render_blocked_candidates_section`, and `replace_blocked_candidates_section` in `__all__`.

- [ ] **Step 4: Re-run the reporting tests**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- `
  "tests/test_month_end_shortlist_degraded_reporting.py" `
  "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: keep cache rescues out of blocked reporting"
```

### Task 3: Add global `bars_source_summary` and spec-aligned cache annotations

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\month_end_shortlist_runtime.py`

- [ ] **Step 1: Add failing tests for execution-state counts and lighter per-name labels**

Extend `tests/test_month_end_shortlist_degraded_reporting.py` with:

```python
    def test_build_bars_source_summary_counts_live_fresh_stale_and_blocked(self) -> None:
        result = {
            "top_picks": [
                {"ticker": "000001.SZ", "name": "平安银行", "score": 82.0},
                {"ticker": "002384.SZ", "name": "东山精密", "score": 79.0, "bars_source": "eastmoney_cache"},
            ],
            "tier_output": {
                "T3": [
                    {
                        "ticker": "601975.SS",
                        "name": "招商南油",
                        "score": 60.0,
                        "bars_source": "eastmoney_cache",
                        "fallback_cache_only": True,
                        "tier_tags": ["low_confidence_fallback", "fallback_cache_only"],
                    }
                ]
            },
            "diagnostic_scorecard": [
                {
                    "ticker": "600123.SS",
                    "name": "兰花科创",
                    "score": 0.0,
                    "midday_status": "blocked",
                    "hard_filter_failures": ["bars_fetch_failed"],
                }
            ],
        }

        summary = module_under_test.build_bars_source_summary(result)

        self.assertEqual(summary["live_count"], 1)
        self.assertEqual(summary["fresh_cache_count"], 1)
        self.assertEqual(summary["stale_cache_count"], 1)
        self.assertEqual(summary["blocked_count"], 1)

    def test_report_includes_execution_state_summary_and_preheat_hint(self) -> None:
        result = {
            "filter_summary": {
                "cache_baseline_trade_date": "2026-04-18",
                "cache_baseline_only": True,
                "live_supplement_status": "unavailable",
                "bars_source_summary": {
                    "live_count": 1,
                    "fresh_cache_count": 2,
                    "stale_cache_count": 1,
                    "blocked_count": 2,
                },
            },
            "report_markdown": "# Month-End Shortlist Report: 2026-04-20\n",
            "top_picks": [],
            "dropped": [],
        }

        enriched = module_under_test.enrich_degraded_live_result(result, [])

        self.assertIn("执行闭环：live=1，fresh_cache=2，stale_cache=1，blocked=2", enriched["report_markdown"])
        self.assertIn("preheat_eastmoney_cache.py", enriched["report_markdown"])

    def test_decision_flow_marks_stale_cache_rescue_with_spec_labels(self) -> None:
        card = module_under_test.build_decision_flow_card(
            {
                "ticker": "601975.SS",
                "name": "招商南油",
                "action": "继续观察",
                "score": 60.0,
                "keep_threshold_gap": -10.0,
                "execution_state": "stale_cache",
                "bars_source": "eastmoney_cache",
                "tier_tags": ["low_confidence_fallback", "fallback_cache_only"],
                "fallback_support_reason": "structured_catalyst",
            },
            keep_threshold=70.0,
            event_card=None,
            chain_entry=None,
        )

        self.assertEqual(card["action_label"], "继续观察（low-confidence fallback）")
        self.assertIn("数据状态：低置信度 fallback", card["operation_reminder"])
        self.assertIn("数据路径：cache baseline only", card["operation_reminder"])
```

- [ ] **Step 2: Run the reporting test file to verify failure**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- FAIL because `build_bars_source_summary` does not exist yet
- FAIL because the report metadata and decision-flow card do not expose the new labels yet

- [ ] **Step 3: Compute merged counts from final decision factors and surface them in report metadata + card reminders**

Add the summary helper:

```python
def build_bars_source_summary(result: dict[str, Any]) -> dict[str, int]:
    decision_factors = result.get("decision_factors")
    if not isinstance(decision_factors, dict):
        decision_factors = build_decision_factors_from_result(result)

    summary = {
        "live_count": 0,
        "fresh_cache_count": 0,
        "stale_cache_count": 0,
        "blocked_count": 0,
    }
    seen: set[str] = set()
    for section in ("qualified", "near_miss", "blocked"):
        for item in decision_factors.get(section, []):
            if not isinstance(item, dict):
                continue
            ticker = clean_text(item.get("ticker"))
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)
            state = clean_text(item.get("execution_state")) or infer_execution_state(item)
            if state == "fresh_cache":
                summary["fresh_cache_count"] += 1
            elif state == "stale_cache":
                summary["stale_cache_count"] += 1
            elif state == "blocked":
                summary["blocked_count"] += 1
            else:
                summary["live_count"] += 1
    return summary
```

Attach it when cache baseline metadata is finalized:

```python
def attach_cache_baseline_metadata(
    result: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    enriched = deepcopy(result)
    request_obj = dict(enriched.get("request") or {})
    target_trade_date = clean_text(request_obj.get("analysis_time") or request_obj.get("target_date"))[:10]
    if not target_trade_date or not candidates:
        return enriched

    target_dt = parse_date(target_trade_date)
    if not target_dt:
        return enriched

    start_date = (target_dt - timedelta(days=420)).isoformat()
    row_sets: list[list[dict[str, Any]]] = []
    for candidate in candidates:
        ticker = clean_text(candidate.get("ticker"))
        if not ticker:
            continue
        row_sets.append(eastmoney_cached_bars_for_candidate(ticker, start_date, target_trade_date))

    metadata = resolve_cache_baseline_metadata(target_trade_date, row_sets)
    filter_summary = dict(enriched.get("filter_summary") or {})
    filter_summary["cache_baseline_trade_date"] = metadata["baseline_trade_date"]
    filter_summary["cache_baseline_only"] = bool(metadata["cache_baseline_only"])
    filter_summary["live_supplement_status"] = metadata["live_supplement_status"]
    filter_summary["bars_source_summary"] = build_bars_source_summary(enriched)
    enriched["filter_summary"] = filter_summary
    enriched["report_markdown"] = prepend_report_metadata_lines(
        enriched.get("report_markdown") or "",
        build_cache_baseline_report_lines(enriched),
    )
    return enriched
```

Thread the execution state into decision-factor entries:

```python
    return {
        "ticker": clean_text(candidate.get("ticker")),
        "name": clean_text(candidate.get("name")) or clean_text(candidate.get("ticker")),
        "action": action,
        "status": status,
        "score": candidate.get("score"),
        "keep_threshold_gap": candidate.get("keep_threshold_gap"),
        "technical_summary": build_technical_factor_summary(candidate),
        "event_summary": build_event_factor_summary(candidate),
        "likely_next_summary": build_likely_next_summary(candidate, action),
        "logic_summary": build_logic_factor_summary(candidate, action),
        "trade_layer_summary": build_trade_layer_summary(candidate, action),
        "next_watch_items": build_next_watch_items(candidate, action),
        "hard_filter_failures": deepcopy(candidate.get("hard_filter_failures", [])),
        "tier_tags": deepcopy(candidate.get("tier_tags", [])),
        "fallback_support_reason": clean_text(candidate.get("fallback_support_reason")),
        "fallback_snapshot_only": bool(candidate.get("fallback_snapshot_only")),
        "fallback_cache_only": bool(candidate.get("fallback_cache_only")),
        "bars_source": clean_text(candidate.get("bars_source")),
        "execution_state": clean_text(candidate.get("execution_state")) or infer_execution_state(candidate),
    }
```

Extend `build_cache_baseline_report_lines`:

```python
def build_cache_baseline_report_lines(result: dict[str, Any]) -> list[str]:
    summary = dict(result.get("filter_summary") or {})
    baseline_trade_date = clean_text(summary.get("cache_baseline_trade_date"))
    lines: list[str] = []
    if baseline_trade_date:
        lines.append(f"- 数据基线：最近交易日盘后缓存（{baseline_trade_date}）")
    status = clean_text(summary.get("live_supplement_status"))
    if status == "unavailable":
        lines.append("- 实时补充：不可用，沿用缓存基线")
    elif status == "updated":
        lines.append("- 实时补充：已更新部分数据")

    bars_source_summary = summary.get("bars_source_summary") if isinstance(summary.get("bars_source_summary"), dict) else {}
    if bars_source_summary:
        lines.append(
            "- 执行闭环：live={live_count}，fresh_cache={fresh_cache_count}，stale_cache={stale_cache_count}，blocked={blocked_count}".format(
                live_count=int(bars_source_summary.get("live_count") or 0),
                fresh_cache_count=int(bars_source_summary.get("fresh_cache_count") or 0),
                stale_cache_count=int(bars_source_summary.get("stale_cache_count") or 0),
                blocked_count=int(bars_source_summary.get("blocked_count") or 0),
            )
        )
        if int(bars_source_summary.get("blocked_count") or 0) > 0:
            lines.append("- 缓存覆盖偏薄：可先运行 `preheat_eastmoney_cache.py` 预热后再重试 shortlist。")
    return lines
```

Finally, update `build_decision_flow_card` so the per-name labels match the spec language:

```python
    execution_state = clean_text(card.get("execution_state")) or infer_execution_state(card)
    if execution_state == "stale_cache":
        operation_parts.append("数据状态：低置信度 fallback")
        operation_parts.append("数据路径：cache baseline only")
        fallback_reason = clean_text(card.get("fallback_support_reason"))
        if fallback_reason:
            operation_parts.append(f"保留原因：{fallback_reason}")
    elif execution_state == "fresh_cache":
        operation_parts.append("数据来源：Eastmoney cache")
    elif is_fallback:
        operation_parts.append("数据路径降级：local market snapshot only")
```

Export `build_bars_source_summary` in `__all__`.

- [ ] **Step 4: Re-run the reporting tests**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```powershell
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- `
  "tests/test_month_end_shortlist_degraded_reporting.py" `
  "financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: surface cache-first execution closure state"
```

### Task 4: Run focused verification for the integrated closure path

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py`

- [ ] **Step 1: Run the three focused suites together**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py" -q
```

Expected:
- PASS
- Coverage should include fresh-cache replay, stale-cache downgrade, blocked-wall pruning, and top-level execution-state summary rendering

- [ ] **Step 2: Run a broader shortlist-regression pass**

Run:

```powershell
& "C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe" -m pytest `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_candidate_fetch_fallback.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_degraded_reporting.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_screening_coverage_optimization.py" `
  "D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_month_end_shortlist_benchmark_fallback.py" -q
```

Expected:
- PASS
- No regression in existing fallback wrappers while the new execution-state fields are threaded through the report path

- [ ] **Step 3: Leave the branch ready for review**

Success checklist:
- `filter_summary["bars_source_summary"]` is populated on merged shortlist runs
- stale-cache rescues land in `T3` without also surviving in `blocked_candidates`
- fresh-cache names stay on the normal execution path
- reports show baseline date, live supplement status, execution-state counts, and a preheat hint only when blocked names remain
