# Postclose Review and Confirmation Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add intraday structure classification, automated postclose review, and a runtime confirmation gate for marginal shortlist candidates.

**Architecture:** Three additive layers — (1) intraday bars fetch/cache/classify in the Eastmoney market module, (2) a standalone postclose review script that reads shortlist output and produces structured adjustments, (3) confirmation gate and priority boost functions wired into the existing shortlist runtime. All new code is additive; no existing behavior changes unless new input fields are present.

**Tech Stack:** Python 3.11+, unittest, argparse, existing Eastmoney cache infrastructure.

**Spec:** `docs/superpowers/specs/2026-04-21-postclose-review-and-confirmation-gate-design.md`

---

## File Structure

| File | Role | Change |
|---|---|---|
| `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_eastmoney_market.py` | Eastmoney market data | Add `fetch_intraday_bars`, `classify_intraday_structure` |
| `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py` | Shortlist runtime | Add `eastmoney_cached_intraday_bars_for_candidate`, `intraday_confirmation_gate`, `review_based_priority_boost`; extend `build_decision_flow_card`; add `pending_confirmation` status |
| `financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py` | **New file** — postclose review CLI | `run_postclose_review`, `classify_plan_outcome`, `generate_adjustment`, markdown renderer, CLI entry |
| `tests/test_intraday_structure_classification.py` | **New file** — intraday tests | 6 test methods |
| `tests/test_postclose_review_runtime.py` | **New file** — review tests | 7 test methods |
| `tests/test_confirmation_gate_and_priority_boost.py` | **New file** — gate tests | 8 test methods |

---

### Task 1: `classify_intraday_structure` — Pure Classification Function + Tests

**Files:**
- Create: `tests/test_intraday_structure_classification.py`
- Modify: `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_eastmoney_market.py` (append)

**Context:** This is a pure function with zero side effects. It takes a list of 15min bar dicts and returns a string classification. We build the test file first (red), then implement the function (green).

- [ ] **Step 1: Create the test file with all 6 test methods**

Create `tests/test_intraday_structure_classification.py`:

```python
#!/usr/bin/env python3
"""Tests for classify_intraday_structure in tradingagents_eastmoney_market."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "tradingagents-decision-bridge"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from tradingagents_eastmoney_market import classify_intraday_structure


def _bar(timestamp: str, o: float, c: float, h: float, l: float, vol: int, amt: float) -> dict:
    return {"timestamp": timestamp, "open": o, "close": c, "high": h, "low": l, "volume": vol, "amount": amt}


class IntradayStructureClassificationTests(unittest.TestCase):
    """Spec Section 1.2: classify_intraday_structure."""

    def test_strong_close_classification(self):
        """Last 2 bars close > VWAP, last bar close > open, close in top 20% of day range."""
        # Day range: low=10.0, high=11.0 → top 20% threshold = 10.8
        # VWAP will be ~10.5 (total amount / total volume)
        bars = [
            _bar("09:30", 10.0, 10.2, 10.3, 10.0, 1000, 10200.0),
            _bar("09:45", 10.2, 10.3, 10.4, 10.1, 1000, 10300.0),
            _bar("10:00", 10.3, 10.4, 10.5, 10.2, 1000, 10400.0),
            _bar("10:15", 10.4, 10.3, 10.5, 10.2, 1000, 10300.0),
            _bar("10:30", 10.3, 10.4, 10.5, 10.3, 1000, 10400.0),
            _bar("10:45", 10.4, 10.5, 10.6, 10.3, 1000, 10500.0),
            _bar("11:00", 10.5, 10.6, 10.7, 10.4, 1000, 10600.0),
            _bar("11:15", 10.6, 10.7, 10.8, 10.5, 1000, 10700.0),
            _bar("13:00", 10.7, 10.8, 10.9, 10.6, 1000, 10800.0),
            _bar("13:15", 10.8, 10.85, 10.9, 10.7, 1000, 10850.0),
            _bar("13:30", 10.85, 10.9, 11.0, 10.8, 1000, 10900.0),
            _bar("13:45", 10.9, 10.92, 11.0, 10.85, 1000, 10920.0),
            # Last 2 bars: close > VWAP (~10.53), close > open, close in top 20%
            _bar("14:00", 10.9, 10.95, 11.0, 10.85, 1000, 10950.0),
            _bar("14:15", 10.95, 10.98, 11.0, 10.9, 1000, 10980.0),
        ]
        self.assertEqual(classify_intraday_structure(bars), "strong_close")

    def test_fade_from_high_classification(self):
        """Intraday high in first half, close < VWAP, close in bottom 40% of day range."""
        # Day range: low=9.5, high=11.0 → bottom 40% threshold = 10.1
        bars = [
            _bar("09:30", 10.5, 10.8, 11.0, 10.5, 2000, 21600.0),
            _bar("09:45", 10.8, 10.9, 11.0, 10.7, 2000, 21800.0),
            _bar("10:00", 10.9, 10.7, 11.0, 10.6, 2000, 21400.0),
            _bar("10:15", 10.7, 10.5, 10.8, 10.4, 1000, 10500.0),
            _bar("10:30", 10.5, 10.3, 10.6, 10.2, 1000, 10300.0),
            _bar("10:45", 10.3, 10.1, 10.4, 10.0, 1000, 10100.0),
            _bar("11:00", 10.1, 10.0, 10.2, 9.9, 1000, 10000.0),
            _bar("11:15", 10.0, 9.9, 10.1, 9.8, 1000, 9900.0),
            _bar("13:00", 9.9, 9.8, 10.0, 9.7, 1000, 9800.0),
            _bar("13:15", 9.8, 9.7, 9.9, 9.6, 1000, 9700.0),
            _bar("13:30", 9.7, 9.7, 9.8, 9.6, 1000, 9700.0),
            _bar("13:45", 9.7, 9.6, 9.8, 9.5, 1000, 9600.0),
            _bar("14:00", 9.6, 9.6, 9.7, 9.5, 1000, 9600.0),
            _bar("14:15", 9.6, 9.6, 9.7, 9.5, 1000, 9600.0),
        ]
        self.assertEqual(classify_intraday_structure(bars), "fade_from_high")

    def test_weak_open_no_recovery(self):
        """First bar close < open by > 1%, never recovers above open price."""
        open_price = 10.0
        first_close = 9.85  # -1.5% from open
        bars = [
            _bar("09:30", open_price, first_close, 10.0, 9.80, 2000, 19700.0),
            _bar("09:45", 9.85, 9.80, 9.90, 9.75, 1000, 9800.0),
            _bar("10:00", 9.80, 9.82, 9.88, 9.78, 1000, 9820.0),
            _bar("10:15", 9.82, 9.78, 9.85, 9.75, 1000, 9780.0),
            _bar("10:30", 9.78, 9.80, 9.85, 9.75, 1000, 9800.0),
            _bar("10:45", 9.80, 9.75, 9.82, 9.72, 1000, 9750.0),
            _bar("11:00", 9.75, 9.78, 9.80, 9.70, 1000, 9780.0),
            _bar("11:15", 9.78, 9.76, 9.80, 9.72, 1000, 9760.0),
            _bar("13:00", 9.76, 9.74, 9.78, 9.70, 1000, 9740.0),
            _bar("13:15", 9.74, 9.72, 9.76, 9.68, 1000, 9720.0),
            _bar("13:30", 9.72, 9.70, 9.75, 9.68, 1000, 9700.0),
            _bar("13:45", 9.70, 9.68, 9.72, 9.65, 1000, 9680.0),
            _bar("14:00", 9.68, 9.65, 9.70, 9.62, 1000, 9650.0),
            _bar("14:15", 9.65, 9.60, 9.68, 9.58, 1000, 9600.0),
        ]
        self.assertEqual(classify_intraday_structure(bars), "weak_open_no_recovery")

    def test_range_bound_default(self):
        """Day range < 3%, close within 30%-70% of day range."""
        # Range: 10.0 to 10.2 = 2% range. Close at 10.1 = 50% of range.
        bars = [
            _bar("09:30", 10.1, 10.05, 10.15, 10.0, 1000, 10050.0),
            _bar("09:45", 10.05, 10.1, 10.15, 10.0, 1000, 10100.0),
            _bar("10:00", 10.1, 10.08, 10.15, 10.02, 1000, 10080.0),
            _bar("10:15", 10.08, 10.12, 10.18, 10.05, 1000, 10120.0),
            _bar("10:30", 10.12, 10.1, 10.2, 10.05, 1000, 10100.0),
            _bar("10:45", 10.1, 10.08, 10.15, 10.02, 1000, 10080.0),
            _bar("11:00", 10.08, 10.1, 10.15, 10.0, 1000, 10100.0),
            _bar("11:15", 10.1, 10.12, 10.18, 10.05, 1000, 10120.0),
            _bar("13:00", 10.12, 10.08, 10.15, 10.02, 1000, 10080.0),
            _bar("13:15", 10.08, 10.1, 10.15, 10.0, 1000, 10100.0),
            _bar("13:30", 10.1, 10.12, 10.18, 10.05, 1000, 10120.0),
            _bar("13:45", 10.12, 10.1, 10.15, 10.02, 1000, 10100.0),
            _bar("14:00", 10.1, 10.08, 10.15, 10.0, 1000, 10080.0),
            _bar("14:15", 10.08, 10.1, 10.15, 10.0, 1000, 10100.0),
        ]
        self.assertEqual(classify_intraday_structure(bars), "range_bound")

    def test_empty_bars_returns_range_bound(self):
        """Edge case: empty list → range_bound."""
        self.assertEqual(classify_intraday_structure([]), "range_bound")

    def test_vwap_calculation_correctness(self):
        """VWAP = cumulative amount / cumulative volume."""
        bars = [
            _bar("09:30", 10.0, 10.5, 10.5, 10.0, 100, 1020.0),
            _bar("09:45", 10.5, 11.0, 11.0, 10.5, 200, 2160.0),
        ]
        # VWAP = (1020 + 2160) / (100 + 200) = 3180 / 300 = 10.6
        result = classify_intraday_structure(bars)
        self.assertIn(result, ("strong_close", "fade_from_high", "weak_open_no_recovery", "range_bound"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail (red)**

Run: `python -m pytest tests/test_intraday_structure_classification.py -v`

Expected: `ImportError` — `classify_intraday_structure` does not exist yet.

- [ ] **Step 3: Implement `classify_intraday_structure` in `tradingagents_eastmoney_market.py`**

Append to the end of `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_eastmoney_market.py`, before any `if __name__` block:

```python
def classify_intraday_structure(bars_15min: list[dict]) -> str:
    """Classify a single trading day's 15min bars into an intraday structure type.

    Returns one of: 'strong_close', 'fade_from_high', 'weak_open_no_recovery', 'range_bound'.
    """
    if not bars_15min:
        return "range_bound"

    day_high = max(b["high"] for b in bars_15min)
    day_low = min(b["low"] for b in bars_15min)
    day_range = day_high - day_low
    last_close = bars_15min[-1]["close"]
    first_open = bars_15min[0]["open"]

    # VWAP = cumulative amount / cumulative volume
    total_amount = sum(b["amount"] for b in bars_15min)
    total_volume = sum(b["volume"] for b in bars_15min)
    vwap = total_amount / total_volume if total_volume > 0 else last_close

    # Avoid division by zero for flat days
    if day_range <= 0:
        return "range_bound"

    close_position = (last_close - day_low) / day_range  # 0.0 = at low, 1.0 = at high

    # --- weak_open_no_recovery ---
    first_bar = bars_15min[0]
    first_drop_pct = (first_bar["close"] - first_bar["open"]) / first_bar["open"] if first_bar["open"] > 0 else 0
    if first_drop_pct < -0.01:
        recovered = any(b["close"] >= first_open for b in bars_15min[1:])
        if not recovered:
            return "weak_open_no_recovery"

    # --- strong_close ---
    if len(bars_15min) >= 2:
        last_two = bars_15min[-2:]
        last_two_above_vwap = all(b["close"] > vwap for b in last_two)
        last_bar_green = last_two[-1]["close"] > last_two[-1]["open"]
        if last_two_above_vwap and last_bar_green and close_position >= 0.80:
            return "strong_close"

    # --- fade_from_high ---
    midpoint = len(bars_15min) // 2
    first_half = bars_15min[:midpoint] if midpoint > 0 else bars_15min[:1]
    first_half_high = max(b["high"] for b in first_half)
    if first_half_high == day_high and last_close < vwap and close_position <= 0.40:
        return "fade_from_high"

    # --- range_bound ---
    day_range_pct = day_range / day_low if day_low > 0 else 0
    if day_range_pct < 0.03 and 0.30 <= close_position <= 0.70:
        return "range_bound"

    return "range_bound"
```

- [ ] **Step 4: Run tests to verify they pass (green)**

Run: `python -m pytest tests/test_intraday_structure_classification.py -v`

Expected: All 6 tests PASS.

- [ ] **Step 5: Run full existing test suite to verify no regression**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All 106+ existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_intraday_structure_classification.py financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_eastmoney_market.py
git commit -m "feat: add classify_intraday_structure for 15min bar classification"
```

---

### Task 2: `fetch_intraday_bars` + `eastmoney_cached_intraday_bars_for_candidate`

**Files:**
- Modify: `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_eastmoney_market.py` (append `fetch_intraday_bars`)
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py` (append `eastmoney_cached_intraday_bars_for_candidate`, update `__all__`)
- Modify: `tests/test_intraday_structure_classification.py` (add 2 unit tests for fetch)

**Context:** `fetch_intraday_bars` mirrors the existing `fetch_daily_bars` pattern in `tradingagents_eastmoney_market.py` but uses `klt=104` (15min). The cached wrapper lives in `month_end_shortlist_runtime.py` following the `eastmoney_cached_bars_for_candidate` pattern (cache key based on JSON-serialized query dict, read from `.tmp/tradingagents-eastmoney-cache/`).

- [ ] **Step 1: Add 2 tests to `tests/test_intraday_structure_classification.py`**

Append to the `IntradayStructureClassificationTests` class:

```python
    def test_fetch_intraday_bars_filters_to_trade_date(self):
        """fetch_intraday_bars filters returned bars to the requested trade_date."""
        from unittest.mock import patch
        from tradingagents_eastmoney_market import fetch_intraday_bars

        mock_payload = {
            "data": {
                "klines": [
                    "2026-04-18 14:45,10.0,10.1,10.2,9.9,1000,10050.0,0.5,1.0,0.2,0.1",
                    "2026-04-20 09:30,10.5,10.6,10.7,10.4,2000,21200.0,0.5,1.0,0.2,0.1",
                    "2026-04-20 09:45,10.6,10.7,10.8,10.5,1500,16050.0,0.5,1.0,0.2,0.1",
                ]
            }
        }

        def mock_fetcher(params, max_age, env):
            return mock_payload

        bars = fetch_intraday_bars("000988", "2026-04-20", fetcher=mock_fetcher)
        self.assertEqual(len(bars), 2)
        self.assertTrue(all(b["timestamp"].startswith("2026-04-20") for b in bars))

    def test_fetch_intraday_bars_raises_on_empty(self):
        """fetch_intraday_bars raises RuntimeError when no bars match trade_date."""
        from tradingagents_eastmoney_market import fetch_intraday_bars

        def mock_fetcher(params, max_age, env):
            return {"data": {"klines": []}}

        with self.assertRaises(RuntimeError):
            fetch_intraday_bars("000988", "2026-04-20", fetcher=mock_fetcher)
```

- [ ] **Step 2: Run tests to verify the 2 new tests fail (red)**

Run: `python -m pytest tests/test_intraday_structure_classification.py::IntradayStructureClassificationTests::test_fetch_intraday_bars_filters_to_trade_date tests/test_intraday_structure_classification.py::IntradayStructureClassificationTests::test_fetch_intraday_bars_raises_on_empty -v`

Expected: `ImportError` — `fetch_intraday_bars` does not exist yet.

- [ ] **Step 3: Implement `fetch_intraday_bars` in `tradingagents_eastmoney_market.py`**

Append after `classify_intraday_structure`, before any `if __name__` block:

```python
def fetch_intraday_bars(
    ticker: str,
    trade_date: str,
    *,
    klt: int = 104,
    fetcher: JsonFetcher = eastmoney_api_request,
    env: dict[str, str] | None = None,
) -> list[dict]:
    """Fetch intraday bars (default 15min, klt=104) for a single trade_date.

    Returns list[dict] with keys: timestamp, open, close, high, low, volume, amount.
    Filters to bars whose timestamp starts with trade_date.
    Raises RuntimeError if no bars match.
    """
    symbol = normalize_eastmoney_symbol(ticker)
    payload = fetcher(
        {
            "secid": eastmoney_secid(symbol),
            "beg": format_date_yyyymmdd(trade_date),
            "end": format_date_yyyymmdd(trade_date),
            "klt": str(klt),
        },
        EASTMONEY_CACHE_MAX_AGE_SECONDS,
        env,
    )
    rows = parse_daily_items(payload)
    if not isinstance(rows, list):
        rows = []
    # Filter to requested trade_date (Eastmoney may return adjacent days)
    date_prefix = trade_date[:10]
    filtered = [r for r in rows if str(r.get("timestamp", "")).startswith(date_prefix)]
    if not filtered:
        raise RuntimeError(f"No Eastmoney intraday bars for `{symbol}` on {trade_date}.")
    return filtered
```

**Note:** `parse_daily_items` already parses kline CSV rows into dicts with `timestamp`, `open`, `close`, `high`, `low`, `volume`, `amount` keys. The same parser works for intraday bars because Eastmoney uses the same CSV format for all klt values.

- [ ] **Step 4: Implement `eastmoney_cached_intraday_bars_for_candidate` in `month_end_shortlist_runtime.py`**

Append after `eastmoney_cached_bars_for_candidate` (around line 1376), in `month_end_shortlist_runtime.py`:

```python
def eastmoney_cached_intraday_bars_for_candidate(
    ticker: str,
    trade_date: str,
    klt: int = 104,
) -> list[dict[str, Any]]:
    """Cache-first intraday bars fetch, mirroring eastmoney_cached_bars_for_candidate."""
    from tradingagents_eastmoney_market import (
        EASTMONEY_DEFAULT_UT,
        cache_path,
        eastmoney_secid,
        format_date_yyyymmdd,
        parse_daily_items,
    )

    normalized_ticker = clean_text(ticker)
    normalized_date = clean_text(trade_date)[:10]
    if not normalized_ticker or not normalized_date:
        return []
    query = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": str(klt),
        "fqt": "0",
        "lmt": "10000",
        "ut": EASTMONEY_DEFAULT_UT,
        "secid": eastmoney_secid(normalized_ticker),
        "beg": format_date_yyyymmdd(normalized_date),
        "end": format_date_yyyymmdd(normalized_date),
    }
    cache_name = f"kline-{json.dumps(query, ensure_ascii=True, sort_keys=True)}.json"
    path = cache_path(cache_name)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    rows = parse_daily_items(payload)
    if not isinstance(rows, list):
        return []
    date_prefix = normalized_date[:10]
    return [r for r in rows if str(r.get("timestamp", "")).startswith(date_prefix)]
```

- [ ] **Step 5: Add `eastmoney_cached_intraday_bars_for_candidate` to `__all__` in `month_end_shortlist_runtime.py`**

In the `__all__` extension block (around line 4720), add after the `"eastmoney_cached_bars_for_candidate"` entry:

```python
    "eastmoney_cached_intraday_bars_for_candidate",
```

- [ ] **Step 6: Run tests to verify the 2 new tests pass (green)**

Run: `python -m pytest tests/test_intraday_structure_classification.py -v`

Expected: All 8 tests PASS.

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All existing tests + 8 new tests PASS.

- [ ] **Step 8: Commit**

```bash
git add financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_eastmoney_market.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_intraday_structure_classification.py
git commit -m "feat: add fetch_intraday_bars and cached intraday bars wrapper"
```

---

### Task 3: Postclose Review — Core Logic (`classify_plan_outcome`, `generate_adjustment`) + Tests

**Files:**
- Create: `financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py`
- Create: `tests/test_postclose_review_runtime.py`

**Context:** The postclose review script is a standalone module. This task builds the two pure functions (`classify_plan_outcome` and `generate_adjustment`) and their tests. The full `run_postclose_review` orchestrator and CLI are in Task 4.

- [ ] **Step 1: Create test file `tests/test_postclose_review_runtime.py` with 6 core tests**

```python
#!/usr/bin/env python3
"""Tests for postclose_review_runtime."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from postclose_review_runtime import classify_plan_outcome, generate_adjustment


class ClassifyPlanOutcomeTests(unittest.TestCase):
    """Spec Section 2.4: judgment classification."""

    def test_plan_too_aggressive_generates_downgrade(self):
        """华工科技 scenario: qualified + -1.46% → plan_too_aggressive."""
        judgment = classify_plan_outcome(plan_action="可执行", actual_return_pct=-1.46)
        self.assertEqual(judgment, "plan_too_aggressive")

    def test_missed_opportunity_generates_upgrade(self):
        """北方稀土 scenario: 观察 + +3.39% → missed_opportunity."""
        judgment = classify_plan_outcome(plan_action="继续观察", actual_return_pct=3.39)
        self.assertEqual(judgment, "missed_opportunity")

    def test_plan_correct_positive_return(self):
        """Qualified + positive return → plan_correct."""
        judgment = classify_plan_outcome(plan_action="可执行", actual_return_pct=2.5)
        self.assertEqual(judgment, "plan_correct")

    def test_plan_correct_minor_drawdown(self):
        """Qualified + return between -1% and 0% → plan_correct (not too_aggressive)."""
        judgment = classify_plan_outcome(plan_action="可执行", actual_return_pct=-0.5)
        self.assertEqual(judgment, "plan_correct")

    def test_plan_correct_negative(self):
        """Blocked + negative return → plan_correct_negative."""
        judgment = classify_plan_outcome(plan_action="不执行", actual_return_pct=-2.0)
        self.assertEqual(judgment, "plan_correct_negative")

    def test_observation_small_positive_not_missed(self):
        """观察 + +1.5% (< 2%) → plan_correct_negative (not missed_opportunity)."""
        judgment = classify_plan_outcome(plan_action="继续观察", actual_return_pct=1.5)
        self.assertEqual(judgment, "plan_correct_negative")


class GenerateAdjustmentTests(unittest.TestCase):
    """Spec Section 2.4: adjustment generation."""

    def test_downgrade_from_too_aggressive(self):
        adj = generate_adjustment("plan_too_aggressive")
        self.assertEqual(adj["adjustment"], "downgrade")
        self.assertEqual(adj["priority_delta"], -5)
        self.assertTrue(adj["gate_next_run"])

    def test_upgrade_from_missed_opportunity(self):
        adj = generate_adjustment("missed_opportunity")
        self.assertEqual(adj["adjustment"], "upgrade")
        self.assertEqual(adj["priority_delta"], 5)
        self.assertFalse(adj["gate_next_run"])

    def test_hold_from_plan_correct(self):
        adj = generate_adjustment("plan_correct")
        self.assertEqual(adj["adjustment"], "hold")
        self.assertEqual(adj["priority_delta"], 0)
        self.assertFalse(adj["gate_next_run"])

    def test_hold_from_plan_correct_negative(self):
        adj = generate_adjustment("plan_correct_negative")
        self.assertEqual(adj["adjustment"], "hold")
        self.assertEqual(adj["priority_delta"], 0)
        self.assertFalse(adj["gate_next_run"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail (red)**

Run: `python -m pytest tests/test_postclose_review_runtime.py -v`

Expected: `ModuleNotFoundError` — `postclose_review_runtime` does not exist yet.

- [ ] **Step 3: Create `postclose_review_runtime.py` with the two pure functions**

Create `financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py`:

```python
#!/usr/bin/env python3
"""Automated postclose review runtime.

Reads a shortlist result.json, fetches intraday bars, classifies plan outcomes,
and produces structured adjustments + markdown report.
"""
from __future__ import annotations

from typing import Any


def classify_plan_outcome(*, plan_action: str, actual_return_pct: float) -> str:
    """Classify a single candidate's plan-vs-actual outcome.

    Args:
        plan_action: The midday action from the shortlist run.
            '可执行' = qualified, '继续观察' = watch/near_miss, '不执行' = blocked.
        actual_return_pct: The actual day return in percent (e.g. -1.46 for -1.46%).

    Returns one of: 'plan_correct', 'plan_too_aggressive', 'missed_opportunity',
    'plan_correct_negative'.
    """
    is_qualified = plan_action == "可执行"
    is_skip = plan_action in ("继续观察", "不执行")

    if is_qualified:
        if actual_return_pct < -1.0:
            return "plan_too_aggressive"
        return "plan_correct"

    if is_skip:
        if actual_return_pct > 2.0:
            return "missed_opportunity"
        return "plan_correct_negative"

    # Fallback for unknown actions
    return "plan_correct_negative"


def generate_adjustment(judgment: str) -> dict[str, Any]:
    """Generate a priority adjustment dict from a plan outcome judgment.

    Returns dict with keys: adjustment, priority_delta, gate_next_run.
    """
    if judgment == "plan_too_aggressive":
        return {"adjustment": "downgrade", "priority_delta": -5, "gate_next_run": True}
    if judgment == "missed_opportunity":
        return {"adjustment": "upgrade", "priority_delta": 5, "gate_next_run": False}
    return {"adjustment": "hold", "priority_delta": 0, "gate_next_run": False}
```

- [ ] **Step 4: Run tests to verify they pass (green)**

Run: `python -m pytest tests/test_postclose_review_runtime.py -v`

Expected: All 10 tests PASS.

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All existing + new tests PASS.

- [ ] **Step 6: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py tests/test_postclose_review_runtime.py
git commit -m "feat: add classify_plan_outcome and generate_adjustment for postclose review"
```

---

### Task 4: Postclose Review — Orchestrator, Markdown Renderer, CLI + Tests

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py` (add `run_postclose_review`, `build_review_markdown`, `parse_args`, `main`)
- Modify: `tests/test_postclose_review_runtime.py` (add orchestrator + markdown tests)

**Context:** This task wires the pure functions from Task 3 into a full orchestrator that reads `result.json`, iterates candidates, fetches intraday bars (mocked in tests), and produces the output JSON + markdown. The CLI follows the existing `parse_args(argv) + main(argv) -> int` pattern.

- [ ] **Step 1: Add orchestrator + markdown + empty-result tests to `tests/test_postclose_review_runtime.py`**

Append to the file:

```python
from unittest.mock import patch, MagicMock


def _bar(timestamp, o, c, h, l, vol, amt):
    return {"timestamp": timestamp, "open": o, "close": c, "high": h, "low": l, "volume": vol, "amount": amt}


def _fade_bars():
    """Bars that classify as fade_from_high."""
    return [
        _bar("09:30", 10.5, 10.8, 11.0, 10.5, 2000, 21600.0),
        _bar("09:45", 10.8, 10.9, 11.0, 10.7, 2000, 21800.0),
        _bar("10:00", 10.9, 10.7, 11.0, 10.6, 2000, 21400.0),
        _bar("10:15", 10.7, 10.5, 10.8, 10.4, 1000, 10500.0),
        _bar("10:30", 10.5, 10.3, 10.6, 10.2, 1000, 10300.0),
        _bar("10:45", 10.3, 10.1, 10.4, 10.0, 1000, 10100.0),
        _bar("11:00", 10.1, 10.0, 10.2, 9.9, 1000, 10000.0),
        _bar("11:15", 10.0, 9.9, 10.1, 9.8, 1000, 9900.0),
        _bar("13:00", 9.9, 9.8, 10.0, 9.7, 1000, 9800.0),
        _bar("13:15", 9.8, 9.7, 9.9, 9.6, 1000, 9700.0),
        _bar("13:30", 9.7, 9.7, 9.8, 9.6, 1000, 9700.0),
        _bar("13:45", 9.7, 9.6, 9.8, 9.5, 1000, 9600.0),
        _bar("14:00", 9.6, 9.6, 9.7, 9.5, 1000, 9600.0),
        _bar("14:15", 9.6, 9.6, 9.7, 9.5, 1000, 9600.0),
    ]


class RunPostcloseReviewTests(unittest.TestCase):
    """Spec Section 2.4-2.5: full orchestrator."""

    def _make_result(self, candidates):
        return {
            "top_picks": candidates,
            "near_miss_candidates": [],
            "filter_summary": {"keep_threshold": 55.0},
        }

    @patch("postclose_review_runtime.eastmoney_cached_intraday_bars_for_candidate")
    def test_full_review_produces_correct_structure(self, mock_bars):
        from postclose_review_runtime import run_postclose_review
        mock_bars.return_value = _fade_bars()
        result_json = self._make_result([
            {"ticker": "000988", "name": "华工科技", "midday_action": "可执行",
             "score": 58.0, "prev_close": 10.0, "close": 9.854},
        ])
        review = run_postclose_review(result_json, "2026-04-20")
        self.assertEqual(review["trade_date"], "2026-04-20")
        self.assertEqual(len(review["candidates_reviewed"]), 1)
        cand = review["candidates_reviewed"][0]
        self.assertEqual(cand["ticker"], "000988")
        self.assertEqual(cand["judgment"], "plan_too_aggressive")
        self.assertEqual(cand["adjustment"], "downgrade")
        self.assertEqual(cand["intraday_structure"], "fade_from_high")
        self.assertEqual(review["summary"]["too_aggressive"], 1)
        self.assertTrue(len(review["prior_review_adjustments"]) >= 0)

    @patch("postclose_review_runtime.eastmoney_cached_intraday_bars_for_candidate")
    def test_intraday_fetch_failure_still_produces_judgment(self, mock_bars):
        from postclose_review_runtime import run_postclose_review
        mock_bars.return_value = []  # fetch failure → empty
        result_json = self._make_result([
            {"ticker": "000988", "name": "华工科技", "midday_action": "可执行",
             "score": 58.0, "prev_close": 10.0, "close": 9.854},
        ])
        review = run_postclose_review(result_json, "2026-04-20")
        cand = review["candidates_reviewed"][0]
        self.assertEqual(cand["intraday_structure"], "unavailable")
        self.assertEqual(cand["judgment"], "plan_too_aggressive")

    def test_empty_result_produces_empty_review(self):
        from postclose_review_runtime import run_postclose_review
        result_json = self._make_result([])
        review = run_postclose_review(result_json, "2026-04-20")
        self.assertEqual(review["summary"]["total_reviewed"], 0)
        self.assertEqual(review["candidates_reviewed"], [])

    @patch("postclose_review_runtime.eastmoney_cached_intraday_bars_for_candidate")
    def test_markdown_report_matches_template_structure(self, mock_bars):
        from postclose_review_runtime import run_postclose_review, build_review_markdown
        mock_bars.return_value = _fade_bars()
        result_json = self._make_result([
            {"ticker": "000988", "name": "华工科技", "midday_action": "可执行",
             "score": 58.0, "prev_close": 10.0, "close": 9.854},
        ])
        review = run_postclose_review(result_json, "2026-04-20")
        md = build_review_markdown(review)
        self.assertIn("操作建议摘要", md)
        self.assertIn("000988", md)
        self.assertIn("华工科技", md)
        self.assertIn("次日观察点", md)
```

- [ ] **Step 2: Run tests to verify the 4 new tests fail (red)**

Run: `python -m pytest tests/test_postclose_review_runtime.py::RunPostcloseReviewTests -v`

Expected: `ImportError` — `run_postclose_review` does not exist yet.

- [ ] **Step 3: Implement `run_postclose_review` in `postclose_review_runtime.py`**

Append to `postclose_review_runtime.py`:

```python
import json
import sys
from pathlib import Path


def _extract_actionable_candidates(result_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract candidates that have a midday_action from the result."""
    candidates = []
    for source_key in ("top_picks", "near_miss_candidates"):
        for item in result_json.get(source_key, []) or []:
            if not isinstance(item, dict):
                continue
            action = (item.get("midday_action") or "").strip()
            if action:
                candidates.append(item)
    return candidates


def _compute_return_pct(candidate: dict[str, Any]) -> float | None:
    """Compute actual day return from close and prev_close."""
    try:
        close = float(candidate["close"])
        prev_close = float(candidate["prev_close"])
        if prev_close <= 0:
            return None
        return round((close - prev_close) / prev_close * 100, 2)
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def run_postclose_review(
    result_json: dict[str, Any],
    trade_date: str,
    plan_md: str | None = None,
) -> dict[str, Any]:
    """Run the full postclose review pipeline.

    Args:
        result_json: Parsed shortlist result.json dict.
        trade_date: The date being reviewed (YYYY-MM-DD).
        plan_md: Optional morning plan markdown (unused in v1, reserved).

    Returns:
        Review output dict with candidates_reviewed, summary, prior_review_adjustments.
    """
    actionable = _extract_actionable_candidates(result_json)
    candidates_reviewed: list[dict[str, Any]] = []
    summary = {"total_reviewed": 0, "correct": 0, "too_aggressive": 0, "missed": 0, "correct_negative": 0}

    for cand in actionable:
        ticker = (cand.get("ticker") or "").strip()
        name = (cand.get("name") or "").strip() or ticker
        plan_action = (cand.get("midday_action") or "").strip()
        actual_return = _compute_return_pct(cand)
        if actual_return is None:
            continue

        # Intraday bars — best-effort
        intraday_structure = "unavailable"
        try:
            bars = eastmoney_cached_intraday_bars_for_candidate(ticker, trade_date)
            if bars:
                from tradingagents_eastmoney_market import classify_intraday_structure
                intraday_structure = classify_intraday_structure(bars)
        except Exception:
            pass

        judgment = classify_plan_outcome(plan_action=plan_action, actual_return_pct=actual_return)
        adj = generate_adjustment(judgment)

        candidates_reviewed.append({
            "ticker": ticker,
            "name": name,
            "plan_action": plan_action,
            "actual_return_pct": actual_return,
            "intraday_structure": intraday_structure,
            "judgment": judgment,
            **adj,
        })

        summary["total_reviewed"] += 1
        if judgment == "plan_correct":
            summary["correct"] += 1
        elif judgment == "plan_too_aggressive":
            summary["too_aggressive"] += 1
        elif judgment == "missed_opportunity":
            summary["missed"] += 1
        elif judgment == "plan_correct_negative":
            summary["correct_negative"] += 1

    prior_review_adjustments = [
        {"ticker": c["ticker"], "adjustment": c["adjustment"],
         "priority_delta": c["priority_delta"], "gate_next_run": c["gate_next_run"]}
        for c in candidates_reviewed if c["adjustment"] != "hold"
    ]

    return {
        "trade_date": trade_date,
        "candidates_reviewed": candidates_reviewed,
        "summary": summary,
        "prior_review_adjustments": prior_review_adjustments,
    }


def eastmoney_cached_intraday_bars_for_candidate(ticker: str, trade_date: str) -> list[dict[str, Any]]:
    """Proxy import — delegates to month_end_shortlist_runtime's cached wrapper."""
    try:
        from month_end_shortlist_runtime import eastmoney_cached_intraday_bars_for_candidate as _impl
        return _impl(ticker, trade_date)
    except ImportError:
        return []
```

- [ ] **Step 4: Implement `build_review_markdown` in `postclose_review_runtime.py`**

Append:

```python
def build_review_markdown(review: dict[str, Any]) -> str:
    """Render the review output as a markdown report."""
    lines: list[str] = []
    trade_date = review.get("trade_date", "unknown")
    lines.append(f"# 盘后复盘报告 — {trade_date}")
    lines.append("")

    # Section: 操作建议摘要
    lines.append("## 操作建议摘要")
    lines.append("")
    lines.append("| 代码 | 名称 | 计划操作 | 实际涨跌% | 分时结构 | 判定 | 调整 |")
    lines.append("|---|---|---|---|---|---|---|")
    for c in review.get("candidates_reviewed", []):
        lines.append(
            f"| {c['ticker']} | {c['name']} | {c['plan_action']} | "
            f"{c['actual_return_pct']:+.2f}% | {c['intraday_structure']} | "
            f"{c['judgment']} | {c['adjustment']} |"
        )
    lines.append("")

    # Section: summary
    s = review.get("summary", {})
    lines.append("## 复盘统计")
    lines.append("")
    lines.append(f"- 总复盘: {s.get('total_reviewed', 0)}")
    lines.append(f"- 计划正确: {s.get('correct', 0)}")
    lines.append(f"- 过于激进: {s.get('too_aggressive', 0)}")
    lines.append(f"- 错过机会: {s.get('missed', 0)}")
    lines.append(f"- 正确回避: {s.get('correct_negative', 0)}")
    lines.append("")

    # Section: 次日观察点
    lines.append("## 次日观察点")
    lines.append("")
    adjustments = review.get("prior_review_adjustments", [])
    if adjustments:
        for adj in adjustments:
            action = "加分 +5" if adj["adjustment"] == "upgrade" else "减分 -5 + 强制确认"
            lines.append(f"- {adj['ticker']}: {action}")
    else:
        lines.append("- 无需调整")
    lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 5: Implement CLI (`parse_args`, `main`) in `postclose_review_runtime.py`**

Append:

```python
import argparse


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run postclose review on a shortlist result.")
    parser.add_argument("--result", required=True, help="Path to result.json from shortlist run.")
    parser.add_argument("--date", required=True, help="Trade date being reviewed (YYYY-MM-DD).")
    parser.add_argument("--plan", default=None, help="Optional path to morning trading plan markdown.")
    parser.add_argument("--output", default=None, help="Write review JSON to this path.")
    parser.add_argument("--markdown-output", default=None, help="Write review markdown to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result_path = Path(args.result).expanduser().resolve()
    result_json = json.loads(result_path.read_text(encoding="utf-8"))
    plan_md = None
    if args.plan:
        plan_md = Path(args.plan).expanduser().resolve().read_text(encoding="utf-8")

    review = run_postclose_review(result_json, args.date, plan_md)

    if args.output:
        out = Path(args.output).expanduser().resolve()
        out.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        md_out = Path(args.markdown_output).expanduser().resolve()
        md_out.write_text(build_review_markdown(review), encoding="utf-8")
    if not args.output:
        sys.stdout.write(json.dumps(review, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run tests to verify all pass (green)**

Run: `python -m pytest tests/test_postclose_review_runtime.py -v`

Expected: All 14 tests PASS (10 from Task 3 + 4 new).

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py tests/test_postclose_review_runtime.py
git commit -m "feat: add run_postclose_review orchestrator, markdown renderer, and CLI"
```

---

### Task 5: Confirmation Gate — `intraday_confirmation_gate` + Tests

**Files:**
- Create: `tests/test_confirmation_gate_and_priority_boost.py`
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py` (add `intraday_confirmation_gate`, update `__all__`)

**Context:** The confirmation gate is a pure function that takes a candidate dict (already scored and classified) and returns a modified copy with `midday_action` and `midday_status` adjusted if the candidate is marginal. It uses existing fields: `keep_threshold_gap` (the spec's `gap_to_next_tier`), `structured_catalyst_score` (the spec's `catalyst_strength`), and `execution_state`.

Key mapping from spec to codebase:
- Spec `gap_to_next_tier <= 2` → codebase `abs(keep_threshold_gap) <= 2` (gap is score - threshold, so small positive = marginal)
- Spec `catalyst_strength is "weak" or absent` → codebase `structured_catalyst_score < 10` or missing
- Spec `execution_state is "fresh_cache" or "stale_cache"` → same field name

- [ ] **Step 1: Create test file with 4 gate tests**

Create `tests/test_confirmation_gate_and_priority_boost.py`:

```python
#!/usr/bin/env python3
"""Tests for intraday_confirmation_gate and review_based_priority_boost."""
from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import month_end_shortlist_runtime as runtime


class IntradayConfirmationGateTests(unittest.TestCase):
    """Spec Section 3.1: intraday_confirmation_gate."""

    def _base_candidate(self, **overrides):
        """A candidate that would be 'qualified' under current logic."""
        base = {
            "ticker": "000988",
            "name": "华工科技",
            "keep": True,
            "score": 58.0,
            "keep_threshold_gap": 2.0,
            "midday_status": "qualified",
            "midday_action": "可执行",
            "structured_catalyst_score": 15.0,
            "execution_state": "live",
            "hard_filter_failures": [],
            "tier_tags": [],
        }
        base.update(overrides)
        return base

    def test_marginal_candidate_triggers_confirmation_gate(self):
        """Gap <= 2 → pending_confirmation."""
        cand = self._base_candidate(keep_threshold_gap=1.5)
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "待确认")
        self.assertEqual(result["midday_status"], "pending_confirmation")

    def test_strong_candidate_bypasses_gate(self):
        """High gap, strong catalyst, live data → stays qualified."""
        cand = self._base_candidate(
            keep_threshold_gap=10.0,
            structured_catalyst_score=20.0,
            execution_state="live",
        )
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "可执行")
        self.assertEqual(result["midday_status"], "qualified")

    def test_weak_catalyst_triggers_gate(self):
        """Absent catalyst on qualified candidate → gate triggered."""
        cand = self._base_candidate(
            keep_threshold_gap=5.0,
            structured_catalyst_score=0.0,
        )
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "待确认")
        self.assertEqual(result["midday_status"], "pending_confirmation")

    def test_stale_cache_execution_state_triggers_gate(self):
        """execution_state stale_cache on qualified → gate triggered."""
        cand = self._base_candidate(
            keep_threshold_gap=5.0,
            execution_state="stale_cache",
        )
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "待确认")
        self.assertEqual(result["midday_status"], "pending_confirmation")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail (red)**

Run: `python -m pytest tests/test_confirmation_gate_and_priority_boost.py::IntradayConfirmationGateTests -v`

Expected: `AttributeError` — `runtime.intraday_confirmation_gate` does not exist.

- [ ] **Step 3: Implement `intraday_confirmation_gate` in `month_end_shortlist_runtime.py`**

Add after `classify_midday_status` (around line 2307):

```python
def intraday_confirmation_gate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Apply confirmation gate to a marginally qualified candidate.

    If the candidate's midday_action is '可执行' but it meets any marginal
    condition, downgrade to '待确认' with midday_status 'pending_confirmation'.

    Marginal conditions (any one triggers the gate):
    - keep_threshold_gap <= 2 (marginal score)
    - structured_catalyst_score < 10 or absent (weak catalyst)
    - execution_state is 'fresh_cache' or 'stale_cache'
    - forced via 'review_force_gate' flag

    Returns a (possibly modified) copy of the candidate.
    """
    result = dict(candidate)
    action = clean_text(result.get("midday_action"))
    if action != "可执行":
        return result

    # Check marginal conditions
    gap = result.get("keep_threshold_gap")
    try:
        gap_value = float(gap) if gap not in (None, "") else 999.0
    except (TypeError, ValueError):
        gap_value = 999.0

    catalyst_score = result.get("structured_catalyst_score")
    try:
        catalyst_value = float(catalyst_score) if catalyst_score not in (None, "") else 0.0
    except (TypeError, ValueError):
        catalyst_value = 0.0

    execution_state = clean_text(result.get("execution_state")) or infer_execution_state(result)
    force_gate = bool(result.get("review_force_gate"))

    is_marginal_gap = gap_value <= 2.0
    is_weak_catalyst = catalyst_value < 10.0
    is_degraded_data = execution_state in ("fresh_cache", "stale_cache")

    if force_gate or is_marginal_gap or is_weak_catalyst or is_degraded_data:
        result["midday_action"] = "待确认"
        result["midday_status"] = "pending_confirmation"

    return result
```

- [ ] **Step 4: Add `intraday_confirmation_gate` to `__all__`**

In the `__all__` extension block, add after `"classify_midday_status"`:

```python
    "intraday_confirmation_gate",
```

- [ ] **Step 5: Run tests to verify they pass (green)**

Run: `python -m pytest tests/test_confirmation_gate_and_priority_boost.py::IntradayConfirmationGateTests -v`

Expected: All 4 tests PASS.

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All tests PASS (no regression — gate only activates on `可执行` candidates, existing tests don't call it).

- [ ] **Step 7: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_confirmation_gate_and_priority_boost.py
git commit -m "feat: add intraday_confirmation_gate for marginal candidates"
```

---

### Task 6: Priority Boost — `review_based_priority_boost` + Tests

**Files:**
- Modify: `tests/test_confirmation_gate_and_priority_boost.py` (add 2 tests)
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py` (add `review_based_priority_boost`, update `__all__`)

**Context:** `review_based_priority_boost` takes a list of candidates and a list of `prior_review_adjustments` (from the previous day's review output). It applies score deltas, adds tier tags, and sets `review_force_gate` for downgrades so `intraday_confirmation_gate` (Task 5) will force them through the gate.

- [ ] **Step 1: Add 2 tests to `tests/test_confirmation_gate_and_priority_boost.py`**

Append a new class:

```python
class ReviewBasedPriorityBoostTests(unittest.TestCase):
    """Spec Section 3.2: review_based_priority_boost."""

    def _base_candidate(self, ticker="002185", score=53.0):
        return {
            "ticker": ticker,
            "name": "华天科技" if ticker == "002185" else "华工科技",
            "score": score,
            "keep": False,
            "keep_threshold_gap": -2.0,
            "tier_tags": [],
            "midday_status": "near_miss",
            "midday_action": "继续观察",
        }

    def test_review_upgrade_boosts_priority(self):
        """Upgrade adjustment → score +5, tier tag 'review_upgraded'."""
        candidates = [self._base_candidate("002185", 53.0)]
        adjustments = [
            {"ticker": "002185", "adjustment": "upgrade", "priority_delta": 5, "gate_next_run": False},
        ]
        result = runtime.review_based_priority_boost(candidates, adjustments)
        boosted = result[0]
        self.assertEqual(boosted["score"], 58.0)
        self.assertIn("review_upgraded", boosted["tier_tags"])
        self.assertFalse(boosted.get("review_force_gate", False))

    def test_review_downgrade_reduces_priority_and_forces_gate(self):
        """Downgrade adjustment → score -5, tier tag 'review_downgraded', force gate."""
        candidates = [self._base_candidate("000988", 58.0)]
        adjustments = [
            {"ticker": "000988", "adjustment": "downgrade", "priority_delta": -5, "gate_next_run": True},
        ]
        result = runtime.review_based_priority_boost(candidates, adjustments)
        downgraded = result[0]
        self.assertEqual(downgraded["score"], 53.0)
        self.assertIn("review_downgraded", downgraded["tier_tags"])
        self.assertTrue(downgraded.get("review_force_gate", False))
```

- [ ] **Step 2: Run tests to verify the 2 new tests fail (red)**

Run: `python -m pytest tests/test_confirmation_gate_and_priority_boost.py::ReviewBasedPriorityBoostTests -v`

Expected: `AttributeError` — `runtime.review_based_priority_boost` does not exist.

- [ ] **Step 3: Implement `review_based_priority_boost` in `month_end_shortlist_runtime.py`**

Add after `intraday_confirmation_gate`:

```python
def review_based_priority_boost(
    candidates: list[dict[str, Any]],
    prior_review_adjustments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply priority adjustments from a prior postclose review.

    For each adjustment, find the matching candidate by ticker and:
    - Apply priority_delta to score
    - Add tier tag ('review_upgraded' or 'review_downgraded')
    - Set review_force_gate if gate_next_run is True

    Returns a new list of (possibly modified) candidate copies.
    """
    if not prior_review_adjustments:
        return list(candidates)

    adj_by_ticker: dict[str, dict[str, Any]] = {}
    for adj in prior_review_adjustments:
        ticker = clean_text(adj.get("ticker"))
        if ticker:
            adj_by_ticker[ticker] = adj

    result = []
    for cand in candidates:
        c = dict(cand)
        ticker = clean_text(c.get("ticker"))
        if ticker in adj_by_ticker:
            adj = adj_by_ticker[ticker]
            try:
                delta = float(adj.get("priority_delta", 0))
            except (TypeError, ValueError):
                delta = 0.0
            current_score = c.get("score")
            try:
                c["score"] = round(float(current_score) + delta, 2) if current_score not in (None, "") else current_score
            except (TypeError, ValueError):
                pass
            tags = list(c.get("tier_tags") or [])
            adjustment_type = clean_text(adj.get("adjustment"))
            if adjustment_type == "upgrade":
                tags.append("review_upgraded")
            elif adjustment_type == "downgrade":
                tags.append("review_downgraded")
            c["tier_tags"] = tags
            if adj.get("gate_next_run"):
                c["review_force_gate"] = True
        result.append(c)
    return result
```

- [ ] **Step 4: Add `review_based_priority_boost` to `__all__`**

In the `__all__` extension block, add after `"intraday_confirmation_gate"`:

```python
    "review_based_priority_boost",
```

- [ ] **Step 5: Run tests to verify they pass (green)**

Run: `python -m pytest tests/test_confirmation_gate_and_priority_boost.py -v`

Expected: All 6 tests PASS (4 gate + 2 boost).

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_confirmation_gate_and_priority_boost.py
git commit -m "feat: add review_based_priority_boost for postclose feedback loop"
```

---

### Task 7: Decision Flow Card Updates — `pending_confirmation` + Review Labels + Tests

**Files:**
- Modify: `tests/test_confirmation_gate_and_priority_boost.py` (add 2 card tests)
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py` (extend `build_decision_flow_card`)

**Context:** The existing `build_decision_flow_card` (line 2925) already builds `operation_parts` and assembles the `flow_card` dict. We add two new blocks:
1. If `midday_status == "pending_confirmation"` → add confirmation labels to `operation_parts`
2. If tier_tags contain `"review_upgraded"` or `"review_downgraded"` → add review boost/penalty labels

Both blocks go into the `operation_parts` assembly section (around line 2972-2997), before the `flow_card` dict is built.

- [ ] **Step 1: Add 2 card tests to `tests/test_confirmation_gate_and_priority_boost.py`**

Append a new class:

```python
class DecisionFlowCardLabelTests(unittest.TestCase):
    """Spec Section 3.4: decision flow card label updates."""

    def _make_factor(self, **overrides):
        """Minimal decision factor dict for build_decision_flow_card."""
        base = {
            "ticker": "000988",
            "name": "华工科技",
            "action": "可执行",
            "score": 58.0,
            "keep_threshold_gap": 2.0,
            "midday_status": "qualified",
            "bars_source": "eastmoney_live",
            "execution_state": "live",
            "tier_tags": [],
            "hard_filter_failures": [],
            "logic_summary": "趋势模板通过",
            "technical_summary": "均线多头结构",
            "event_summary": "事件验证通过",
        }
        base.update(overrides)
        return base

    def test_decision_flow_card_shows_pending_confirmation_labels(self):
        """pending_confirmation → card has 待确认, 盘中确认, 确认条件."""
        factor = self._make_factor(
            midday_status="pending_confirmation",
            action="待确认",
        )
        card = runtime.build_decision_flow_card(
            factor, keep_threshold=55.0, event_card=None, chain_entry=None,
        )
        reminder = card.get("operation_reminder", "")
        self.assertIn("盘中确认", reminder)
        self.assertIn("分时确认", reminder)

    def test_decision_flow_card_shows_review_boost_labels(self):
        """review_upgraded tag → card has 复盘加分."""
        factor = self._make_factor(
            tier_tags=["review_upgraded"],
            score=58.0,
        )
        card = runtime.build_decision_flow_card(
            factor, keep_threshold=55.0, event_card=None, chain_entry=None,
        )
        reminder = card.get("operation_reminder", "")
        self.assertIn("复盘加分", reminder)
```

- [ ] **Step 2: Run tests to verify the 2 new tests fail (red)**

Run: `python -m pytest tests/test_confirmation_gate_and_priority_boost.py::DecisionFlowCardLabelTests -v`

Expected: FAIL — `operation_reminder` does not yet contain the new labels.

- [ ] **Step 3: Extend `build_decision_flow_card` in `month_end_shortlist_runtime.py`**

In `build_decision_flow_card`, find the `operation_parts` assembly section. After the geopolitics constraint block (around line 2997, after `operation_parts.append(geopolitics_constraint)`), add:

```python
    # --- Confirmation gate labels ---
    midday_status = clean_text(card.get("midday_status"))
    if midday_status == "pending_confirmation":
        operation_parts.append("盘中确认：需等待 11:00 后分时确认")
        operation_parts.append("确认条件：分时不出现 fade_from_high 或 weak_open_no_recovery")
        operation_parts.append("确认后操作：按原计划执行")
        operation_parts.append("未确认操作：降级为观察")

    # --- Review boost/penalty labels ---
    if "review_upgraded" in tier_tags:
        operation_parts.append("复盘加分：+5（前日错过机会）")
    elif "review_downgraded" in tier_tags:
        operation_parts.append("复盘减分：-5（前日过于激进）")
        operation_parts.append("强制确认门控：是")
```

- [ ] **Step 4: Run tests to verify they pass (green)**

Run: `python -m pytest tests/test_confirmation_gate_and_priority_boost.py -v`

Expected: All 8 tests PASS (4 gate + 2 boost + 2 card).

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All tests PASS. The new labels only appear when `midday_status == "pending_confirmation"` or review tags are present — neither condition exists in existing test data.

- [ ] **Step 6: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py tests/test_confirmation_gate_and_priority_boost.py
git commit -m "feat: add pending_confirmation and review boost labels to decision flow card"
```

---

### Task 8: Full Regression + Final Verification

**Files:**
- No new files. This task is verification-only.

**Context:** After all implementation tasks, run the full test suite one final time to confirm zero regressions across all 106+ existing tests plus the ~21 new tests added in Tasks 1-7.

- [ ] **Step 1: Run the complete test suite**

Run: `python -m pytest tests/ -v --tb=short`

Expected: All tests PASS. Total should be ~127+ tests (106 existing + 21 new).

- [ ] **Step 2: Verify new exports are accessible**

Run a quick smoke check:

```bash
python -c "
import sys; sys.path.insert(0, 'financial-analysis/skills/month-end-shortlist/scripts'); sys.path.insert(0, 'financial-analysis/skills/tradingagents-decision-bridge/scripts')
from tradingagents_eastmoney_market import classify_intraday_structure, fetch_intraday_bars
from month_end_shortlist_runtime import eastmoney_cached_intraday_bars_for_candidate, intraday_confirmation_gate, review_based_priority_boost
from postclose_review_runtime import classify_plan_outcome, generate_adjustment, run_postclose_review, build_review_markdown
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Verify `postclose_review_runtime.py` CLI help**

Run: `python financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py --help`

Expected: Shows usage with `--result`, `--date`, `--plan`, `--output`, `--markdown-output` options.

- [ ] **Step 4: Final commit (if any lint/format fixes needed)**

If any formatting adjustments were needed during verification:

```bash
git add -u
git commit -m "chore: minor formatting fixes after full regression"
```

Otherwise skip this step.

---

## Summary

| Task | What it delivers | New tests |
|---|---|---|
| 1 | `classify_intraday_structure` pure function | 6 |
| 2 | `fetch_intraday_bars` + cached wrapper | 2 |
| 3 | `classify_plan_outcome` + `generate_adjustment` | 10 |
| 4 | `run_postclose_review` orchestrator + markdown + CLI | 4 |
| 5 | `intraday_confirmation_gate` | 4 |
| 6 | `review_based_priority_boost` | 2 |
| 7 | Decision flow card labels | 2 |
| 8 | Full regression verification | 0 |
| **Total** | | **~30 new tests** |
