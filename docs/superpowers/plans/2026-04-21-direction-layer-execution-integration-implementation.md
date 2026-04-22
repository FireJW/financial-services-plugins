# Direction Layer Execution Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate direction layer signals (from `weekend_market_candidate_runtime.py`) into the execution pipeline — ticker resolution, score boosting, tier promotion, confirmation gate bypass, and postclose review momentum feedback.

**Architecture:** Add ticker resolution at build-time (Eastmoney API) and execution-time (universe cross-check). Insert `direction_alignment_boost()` after `review_based_priority_boost()` and `direction_tier_promotion()` after `assign_tiers()` in `enrich_track_result()`. Modify `intraday_confirmation_gate()` for direction bypass. Extend `postclose_review_runtime.py` with `direction_momentum` output. All new logic is additive — no-op when direction data is absent.

**Tech Stack:** Python 3.11+, unittest, Eastmoney suggest API

**Spec:** `docs/superpowers/specs/2026-04-21-direction-layer-execution-integration-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py` | Modify | Add `resolve_direction_tickers()`, `default_ticker_resolver()`; call in `build_weekend_market_candidate()` |
| `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py` | Modify | Add `cross_check_direction_tickers()`, `direction_alignment_boost()`, `direction_tier_promotion()`; modify `intraday_confirmation_gate()`, `build_decision_flow_card()`, `build_weekend_market_candidate_markdown()`; update `__all__` |
| `financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py` | Modify | Add direction fields to `candidates_reviewed`; add `direction_momentum` output; extend `build_review_markdown()` |
| `tests/test_direction_layer_integration.py` | Create | 18 tests covering all new functions |

### Key Existing Code References

- **Eastmoney ticker resolver:** `x_stock_picker_style_runtime.py:347` → `resolve_name_live(stock_name)` returns `{"ticker", "code", "resolved_name", "board"}`
- **`EASTMONEY_SUGGEST_URL`:** `x_stock_picker_style_runtime.py:26`
- **`build_weekend_market_candidate()`:** `weekend_market_candidate_runtime.py:332` → returns `(candidate_dict, direction_reference_map)`
- **`direction_reference_map` structure:** list of `{"direction_key", "direction_label", "leaders": [{"ticker":"","name":...}], "high_beta_names": [...], "mapping_note"}`
- **`TIER_CAPS`:** `month_end_shortlist_runtime.py:177` → `{"T1": 10, "T2": 5, "T3": 8, "T4": 5}`
- **`assign_tiers()`:** `month_end_shortlist_runtime.py:1932`
- **`intraday_confirmation_gate()`:** `month_end_shortlist_runtime.py:2354`
- **`review_based_priority_boost()`:** `month_end_shortlist_runtime.py:2400`
- **`build_decision_flow_card()`:** `month_end_shortlist_runtime.py:3065`
- **`enrich_track_result()`:** `month_end_shortlist_runtime.py:4062` — tier assignment at line 4190
- **`run_postclose_review()`:** `postclose_review_runtime.py:98`
- **Test pattern:** `unittest.TestCase`, `sys.path` insert to scripts dir, `_base_candidate(**overrides)` helper

---

## Tasks

### Task 1: Build-Time Ticker Resolution (`weekend_market_candidate_runtime.py`)

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py`
- Test: `tests/test_direction_layer_integration.py`

- [ ] **Step 1: Create test file with ticker resolution tests**

Create `tests/test_direction_layer_integration.py`:

```python
#!/usr/bin/env python3
"""Tests for direction layer execution integration."""
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


class ResolveDirectionTickersTests(unittest.TestCase):
    """Spec Section 1.2: build-time ticker resolution."""

    def _make_direction_map(self):
        return [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [
                    {"ticker": "", "name": "中际旭创"},
                    {"ticker": "", "name": "新易盛"},
                ],
                "high_beta_names": [
                    {"ticker": "", "name": "天孚通信"},
                ],
                "mapping_note": "Direction reference only. Not a formal execution layer.",
            }
        ]

    def test_resolve_direction_tickers_fills_known_names(self):
        """Mock resolver returns tickers for known names, verify tickers are filled."""
        from weekend_market_candidate_runtime import resolve_direction_tickers

        direction_map = self._make_direction_map()
        mock_results = {"中际旭创": "300308", "新易盛": "300502", "天孚通信": "300394"}

        def mock_resolver(name: str) -> str | None:
            return mock_results.get(name)

        resolved = resolve_direction_tickers(direction_map, resolver=mock_resolver)
        entry = resolved[0]
        self.assertEqual(entry["leaders"][0]["ticker"], "300308")
        self.assertEqual(entry["leaders"][1]["ticker"], "300502")
        self.assertEqual(entry["high_beta_names"][0]["ticker"], "300394")
        self.assertIn("Tickers resolved", entry["mapping_note"])

    def test_resolve_direction_tickers_keeps_empty_on_failure(self):
        """Resolver returns None → ticker stays empty string."""
        from weekend_market_candidate_runtime import resolve_direction_tickers

        direction_map = self._make_direction_map()

        def failing_resolver(name: str) -> str | None:
            return None

        resolved = resolve_direction_tickers(direction_map, resolver=failing_resolver)
        entry = resolved[0]
        self.assertEqual(entry["leaders"][0]["ticker"], "")
        self.assertEqual(entry["leaders"][1]["ticker"], "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::ResolveDirectionTickersTests -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_direction_tickers'`

- [ ] **Step 3: Implement `default_ticker_resolver` and `resolve_direction_tickers`**

In `weekend_market_candidate_runtime.py`, add after the existing imports (line 9):

```python
from typing import Callable
```

Add before `build_weekend_market_candidate()` (before line 332):

```python
def default_ticker_resolver(name: str) -> str | None:
    """Resolve a Chinese company name to a 6-digit ticker code via Eastmoney suggest API.

    Returns ticker string like '300308' or None if not found.
    """
    try:
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen

        url = (
            "https://searchapi.eastmoney.com/api/suggest/get?"
            + urlencode({"input": name, "type": "14", "token": "D43BF722C8E33BDC906FB84D85E326E8"})
        )
        req = Request(url, headers={"Referer": "https://quote.eastmoney.com/"})
        with urlopen(req, timeout=5) as resp:
            import json as _json
            payload = _json.loads(resp.read())
        data = payload.get("QuotationCodeTable", {}).get("Data") or []
        for item in data:
            code = (item.get("Code") or "").strip()
            if code and re.fullmatch(r"\d{6}", code):
                return code
    except Exception:
        pass
    return None


def resolve_direction_tickers(
    direction_reference_map: list[dict[str, Any]],
    *,
    resolver: Callable[[str], str | None] | None = None,
) -> list[dict[str, Any]]:
    """Resolve empty ticker fields in direction_reference_map.

    For each leader/high_beta entry with ticker == "", calls the resolver.
    If resolution succeeds, fills the ticker field.
    Updates mapping_note to indicate resolution was attempted.
    """
    if resolver is None:
        resolver = default_ticker_resolver
    result = deepcopy(direction_reference_map)
    for entry in result:
        any_resolved = False
        for group_key in ("leaders", "high_beta_names"):
            for item in entry.get(group_key, []):
                if item.get("ticker") == "" and item.get("name"):
                    resolved_ticker = resolver(item["name"])
                    if resolved_ticker:
                        item["ticker"] = resolved_ticker
                        any_resolved = True
        if any_resolved:
            entry["mapping_note"] = "Tickers resolved at build time."
    return result
```

- [ ] **Step 4: Call `resolve_direction_tickers` in `build_weekend_market_candidate`**

In `weekend_market_candidate_runtime.py`, modify the return section (line 459). Change:

```python
    return candidate, direction_reference_map
```

to:

```python
    direction_reference_map = resolve_direction_tickers(direction_reference_map)
    return candidate, direction_reference_map
```

- [ ] **Step 5: Update `__all__` in `weekend_market_candidate_runtime.py`**

Change (lines 462-465):

```python
__all__ = [
    "build_weekend_market_candidate",
    "normalize_weekend_market_candidate_input",
]
```

to:

```python
__all__ = [
    "build_weekend_market_candidate",
    "normalize_weekend_market_candidate_input",
    "default_ticker_resolver",
    "resolve_direction_tickers",
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::ResolveDirectionTickersTests -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Run full test suite regression check**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -5`
Expected: All existing tests pass

- [ ] **Step 8: Commit**

```bash
git add tests/test_direction_layer_integration.py financial-analysis/skills/month-end-shortlist/scripts/weekend_market_candidate_runtime.py
git commit -m "feat: add build-time ticker resolution for direction_reference_map"
```

---

### Task 2: Execution-Time Universe Cross-Check (`month_end_shortlist_runtime.py`)

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Test: `tests/test_direction_layer_integration.py`

- [ ] **Step 1: Add cross-check test**

Append to `tests/test_direction_layer_integration.py`:

```python
class CrossCheckDirectionTickersTests(unittest.TestCase):
    """Spec Section 1.3: execution-time cross-check against universe."""

    def test_cross_check_direction_tickers_against_universe(self):
        """Names matched against universe by name, in_universe flag set correctly."""
        import month_end_shortlist_runtime as runtime

        direction_map = [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [
                    {"ticker": "300308", "name": "中际旭创"},
                    {"ticker": "", "name": "未知公司"},
                ],
                "high_beta_names": [
                    {"ticker": "300394", "name": "天孚通信"},
                ],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]
        universe = [
            {"ticker": "300308", "name": "中际旭创", "f12": "300308", "f14": "中际旭创"},
            {"ticker": "300394", "name": "天孚通信", "f12": "300394", "f14": "天孚通信"},
            {"ticker": "002236", "name": "大华股份", "f12": "002236", "f14": "大华股份"},
        ]

        enriched = runtime.cross_check_direction_tickers(direction_map, universe)
        entry = enriched[0]
        # 300308 is in universe
        self.assertTrue(entry["leaders"][0]["in_universe"])
        # 未知公司 has no ticker and no name match
        self.assertFalse(entry["leaders"][1]["in_universe"])
        # 300394 is in universe
        self.assertTrue(entry["high_beta_names"][0]["in_universe"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::CrossCheckDirectionTickersTests -v`
Expected: FAIL — `AttributeError: module 'month_end_shortlist_runtime' has no attribute 'cross_check_direction_tickers'`

- [ ] **Step 3: Implement `cross_check_direction_tickers`**

In `month_end_shortlist_runtime.py`, add after `review_based_priority_boost()` (after line ~2450):

```python
def cross_check_direction_tickers(
    direction_reference_map: list[dict[str, Any]],
    universe: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Cross-check direction tickers against the fetched stock universe.

    For entries with a ticker: verify ticker exists in universe.
    For entries without a ticker: attempt match by name.
    Adds ``in_universe: bool`` to each leader/high_beta entry.
    """
    universe_tickers = {
        clean_text(row.get("ticker") or row.get("f12"))
        for row in universe
        if clean_text(row.get("ticker") or row.get("f12"))
    }
    universe_names: dict[str, str] = {}
    for row in universe:
        name = clean_text(row.get("name") or row.get("f14"))
        ticker = clean_text(row.get("ticker") or row.get("f12"))
        if name and ticker:
            universe_names[name] = ticker

    result = deepcopy(direction_reference_map)
    for entry in result:
        for group_key in ("leaders", "high_beta_names"):
            for item in entry.get(group_key, []):
                ticker = clean_text(item.get("ticker"))
                name = clean_text(item.get("name"))
                if ticker and ticker in universe_tickers:
                    item["in_universe"] = True
                elif not ticker and name and name in universe_names:
                    item["ticker"] = universe_names[name]
                    item["in_universe"] = True
                else:
                    item["in_universe"] = False
    return result
```

- [ ] **Step 4: Add to `__all__`**

In the `__all__` extras loop (around line 4910), add `"cross_check_direction_tickers"` to the `_extra` tuple.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::CrossCheckDirectionTickersTests -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tests/test_direction_layer_integration.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: add execution-time direction ticker cross-check against universe"
```

---

### Task 3: Two-Tier Direction Alignment Scoring (`month_end_shortlist_runtime.py`)

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Test: `tests/test_direction_layer_integration.py`

- [ ] **Step 1: Add scoring tests**

Append to `tests/test_direction_layer_integration.py`:

```python
class DirectionAlignmentBoostTests(unittest.TestCase):
    """Spec Section 2: two-tier direction alignment scoring."""

    def _make_weekend_candidate(self, signal_strength="high", status="candidate_only"):
        return {
            "candidate_topics": [{"topic_name": "optical_interconnect", "topic_label": "光通信 / 光模块"}],
            "signal_strength": signal_strength,
            "status": status,
        }

    def _make_direction_map(self, leader_ticker="300308", hb_ticker="300394"):
        return [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [{"ticker": leader_ticker, "name": "中际旭创", "in_universe": True}],
                "high_beta_names": [{"ticker": hb_ticker, "name": "天孚通信", "in_universe": True}],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]

    def _make_candidate(self, ticker="300308", score=50.0, matched_themes=None):
        return {
            "ticker": ticker,
            "name": "中际旭创",
            "score": score,
            "adjusted_total_score": score,
            "matched_themes": matched_themes or [],
            "tier_tags": [],
        }

    def test_theme_alignment_boost_high_signal(self):
        """Theme match + high signal → +3."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="999999", matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["theme_delta"], 3)
        self.assertEqual(boost["reference_delta"], 0)

    def test_theme_alignment_boost_medium_signal(self):
        """Theme match + medium signal → +1."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="999999", matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("medium"),
        )
        self.assertEqual(result[0]["direction_boost"]["theme_delta"], 1)

    def test_reference_map_leader_boost(self):
        """Leader ticker match → +6."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", matched_themes=[])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["reference_delta"], 6)
        self.assertEqual(boost["direction_role"], "leader")

    def test_reference_map_high_beta_boost(self):
        """High-beta ticker match → +4."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300394", matched_themes=[])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["reference_delta"], 4)
        self.assertEqual(boost["direction_role"], "high_beta")

    def test_leader_and_theme_boost_stack(self):
        """Both match → +3 + +6 = +9."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0, matched_themes=["optical_interconnect"])
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), self._make_weekend_candidate("high"),
        )
        boost = result[0]["direction_boost"]
        self.assertEqual(boost["theme_delta"], 3)
        self.assertEqual(boost["reference_delta"], 6)
        self.assertEqual(boost["total_delta"], 9)
        self.assertEqual(result[0]["adjusted_total_score"], 59.0)

    def test_no_boost_when_insufficient_signal(self):
        """Direction status insufficient → candidates unchanged."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0)
        wmc = self._make_weekend_candidate(status="insufficient_signal")
        result = runtime.direction_alignment_boost(
            [cand], self._make_direction_map(), wmc,
        )
        self.assertNotIn("direction_boost", result[0])
        self.assertEqual(result[0]["adjusted_total_score"], 50.0)

    def test_no_boost_when_no_direction(self):
        """weekend_market_candidate is None → no-op."""
        import month_end_shortlist_runtime as runtime

        cand = self._make_candidate(ticker="300308", score=50.0)
        result = runtime.direction_alignment_boost([cand], [], None)
        self.assertNotIn("direction_boost", result[0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::DirectionAlignmentBoostTests -v`
Expected: FAIL — `AttributeError: module 'month_end_shortlist_runtime' has no attribute 'direction_alignment_boost'`

- [ ] **Step 3: Implement `direction_alignment_boost`**

In `month_end_shortlist_runtime.py`, add after `cross_check_direction_tickers()`:

```python
_DIRECTION_THEME_BOOST = {"high": 3, "medium": 1, "low": 0}
_DIRECTION_REFERENCE_BOOST = {"leader": 6, "high_beta": 4}
_DIRECTION_MOMENTUM_HALVED = {"theme": 1, "leader": 3, "high_beta": 2}


def direction_alignment_boost(
    candidates: list[dict[str, Any]],
    direction_reference_map: list[dict[str, Any]],
    weekend_market_candidate: dict[str, Any] | None,
    *,
    direction_momentum: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Apply two-tier direction alignment scoring to candidates.

    Tier 1: theme intersection boost (matched_themes ∩ direction topics).
    Tier 2: reference map match boost (ticker match in leaders/high_beta).
    Momentum modulation from prior review adjusts boost values.

    Returns a new list of (possibly modified) candidate copies.
    """
    if not weekend_market_candidate or not isinstance(weekend_market_candidate, dict):
        return [dict(c) for c in candidates]
    if weekend_market_candidate.get("status") == "insufficient_signal":
        return [dict(c) for c in candidates]
    if not direction_reference_map:
        return [dict(c) for c in candidates]

    signal_strength = clean_text(weekend_market_candidate.get("signal_strength")) or "low"

    # Build direction topic set from candidate_topics
    direction_topics: set[str] = set()
    for topic in weekend_market_candidate.get("candidate_topics", []):
        tn = clean_text(topic.get("topic_name"))
        if tn:
            direction_topics.add(tn)

    # Build ticker→(direction_key, role) lookup
    ticker_to_direction: dict[str, tuple[str, str, str]] = {}  # ticker → (key, label, role)
    direction_labels: dict[str, str] = {}
    for entry in direction_reference_map:
        dk = clean_text(entry.get("direction_key"))
        dl = clean_text(entry.get("direction_label")) or dk
        direction_labels[dk] = dl
        for item in entry.get("leaders", []):
            t = clean_text(item.get("ticker"))
            if t:
                ticker_to_direction[t] = (dk, dl, "leader")
        for item in entry.get("high_beta_names", []):
            t = clean_text(item.get("ticker"))
            if t and t not in ticker_to_direction:  # leader takes precedence
                ticker_to_direction[t] = (dk, dl, "high_beta")

    # Build momentum lookup: direction_key → momentum_signal
    momentum_by_key: dict[str, str] = {}
    for m in (direction_momentum or []):
        mk = clean_text(m.get("direction_key"))
        if mk:
            momentum_by_key[mk] = clean_text(m.get("momentum_signal")) or ""

    result = []
    for cand in candidates:
        c = dict(cand)
        matched_themes = set(c.get("matched_themes") or [])

        # Tier 1: theme intersection
        theme_delta = 0
        matched_direction_key = ""
        for dk in direction_topics:
            if dk in matched_themes:
                theme_delta = _DIRECTION_THEME_BOOST.get(signal_strength, 0)
                matched_direction_key = dk
                break

        # Tier 2: reference map match
        reference_delta = 0
        direction_role = ""
        ticker = clean_text(c.get("ticker"))
        if ticker in ticker_to_direction:
            dk, dl, role = ticker_to_direction[ticker]
            reference_delta = _DIRECTION_REFERENCE_BOOST.get(role, 0)
            direction_role = role
            if not matched_direction_key:
                matched_direction_key = dk

        if theme_delta == 0 and reference_delta == 0:
            result.append(c)
            continue

        # Momentum modulation
        momentum_signal = momentum_by_key.get(matched_direction_key, "")
        if momentum_signal == "fading":
            theme_delta = 0
            reference_delta = 0
        elif momentum_signal == "caution":
            theme_delta = _DIRECTION_MOMENTUM_HALVED["theme"] if theme_delta > 0 else 0
            if direction_role == "leader":
                reference_delta = _DIRECTION_MOMENTUM_HALVED["leader"] if reference_delta > 0 else 0
            elif direction_role == "high_beta":
                reference_delta = _DIRECTION_MOMENTUM_HALVED["high_beta"] if reference_delta > 0 else 0

        total_delta = theme_delta + reference_delta
        if total_delta > 0:
            try:
                current = float(c.get("adjusted_total_score") or c.get("score") or 0)
                c["adjusted_total_score"] = round(current + total_delta, 2)
            except (TypeError, ValueError):
                pass

            tags = list(c.get("tier_tags") or [])
            if theme_delta > 0:
                tags.append("direction_theme_aligned")
            if direction_role:
                tags.append(f"direction_{direction_role}")
            c["tier_tags"] = tags

        c["direction_boost"] = {
            "theme_delta": theme_delta,
            "reference_delta": reference_delta,
            "total_delta": theme_delta + reference_delta,
            "direction_key": matched_direction_key,
            "direction_role": direction_role or None,
            "signal_strength": signal_strength,
        }
        if momentum_signal:
            c["direction_boost"]["momentum_signal"] = momentum_signal

        result.append(c)
    return result
```

- [ ] **Step 4: Add to `__all__`**

Add `"direction_alignment_boost"` to the `_extra` tuple in the `__all__` section.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::DirectionAlignmentBoostTests -v`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add tests/test_direction_layer_integration.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: add two-tier direction alignment scoring"
```

---

### Task 4: Direction-Based Tier Promotion (`month_end_shortlist_runtime.py`)

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`
- Test: `tests/test_direction_layer_integration.py`

- [ ] **Step 1: Add tier promotion tests**

Append to `tests/test_direction_layer_integration.py`:

```python
class DirectionTierPromotionTests(unittest.TestCase):
    """Spec Section 3: direction-based tier promotion."""

    def _make_weekend_candidate(self, signal_strength="high"):
        return {
            "candidate_topics": [{"topic_name": "optical_interconnect", "topic_label": "光通信 / 光模块"}],
            "signal_strength": signal_strength,
            "status": "candidate_only",
        }

    def _make_direction_map(self):
        return [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [{"ticker": "300308", "name": "中际旭创", "in_universe": True}],
                "high_beta_names": [{"ticker": "300394", "name": "天孚通信", "in_universe": True}],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]

    def _make_tiered(self, t1_count=3, t2_count=2, t3_count=2):
        tiers = {"T1": [], "T2": [], "T3": [], "T4": []}
        for i in range(t1_count):
            tiers["T1"].append({"ticker": f"T1_{i:03d}", "name": f"T1股{i}", "tier_tags": [], "wrapper_tier": "T1"})
        for i in range(t2_count):
            tiers["T2"].append({"ticker": f"T2_{i:03d}", "name": f"T2股{i}", "tier_tags": [], "wrapper_tier": "T2"})
        for i in range(t3_count):
            tiers["T3"].append({"ticker": f"T3_{i:03d}", "name": f"T3股{i}", "tier_tags": [], "wrapper_tier": "T3"})
        return tiers

    def test_tier_promotion_t2_to_t1_leader(self):
        """Leader in T2 promoted to T1 when T1 < 10."""
        import month_end_shortlist_runtime as runtime

        tiers = self._make_tiered(t1_count=3, t2_count=2)
        tiers["T2"].append({"ticker": "300308", "name": "中际旭创", "tier_tags": ["direction_leader"], "wrapper_tier": "T2"})
        result = runtime.direction_tier_promotion(tiers, self._make_direction_map(), self._make_weekend_candidate())
        t1_tickers = [c["ticker"] for c in result["T1"]]
        self.assertIn("300308", t1_tickers)
        promoted = [c for c in result["T1"] if c["ticker"] == "300308"][0]
        self.assertIn("direction_promoted", promoted["tier_tags"])

    def test_tier_promotion_respects_cap(self):
        """No promotion when T1 is full (10)."""
        import month_end_shortlist_runtime as runtime

        tiers = self._make_tiered(t1_count=10, t2_count=2)
        tiers["T2"].append({"ticker": "300308", "name": "中际旭创", "tier_tags": ["direction_leader"], "wrapper_tier": "T2"})
        result = runtime.direction_tier_promotion(tiers, self._make_direction_map(), self._make_weekend_candidate())
        t1_tickers = [c["ticker"] for c in result["T1"]]
        self.assertNotIn("300308", t1_tickers)

    def test_tier_promotion_max_2_per_run(self):
        """Third promotion blocked by max-2 cap."""
        import month_end_shortlist_runtime as runtime

        tiers = self._make_tiered(t1_count=3, t2_count=0)
        for i, ticker in enumerate(["300308", "300394", "300999"]):
            tiers["T2"].append({"ticker": ticker, "name": f"Stock{i}", "tier_tags": ["direction_leader"], "wrapper_tier": "T2"})
        drm = [
            {
                "direction_key": "optical_interconnect",
                "direction_label": "光通信 / 光模块",
                "leaders": [
                    {"ticker": "300308", "name": "A", "in_universe": True},
                    {"ticker": "300394", "name": "B", "in_universe": True},
                    {"ticker": "300999", "name": "C", "in_universe": True},
                ],
                "high_beta_names": [],
                "mapping_note": "Tickers resolved at build time.",
            }
        ]
        result = runtime.direction_tier_promotion(tiers, drm, self._make_weekend_candidate())
        promoted_count = sum(1 for c in result["T1"] if "direction_promoted" in c.get("tier_tags", []))
        self.assertEqual(promoted_count, 2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::DirectionTierPromotionTests -v`
Expected: FAIL

- [ ] **Step 3: Implement `direction_tier_promotion`**

In `month_end_shortlist_runtime.py`, add after `direction_alignment_boost()`:

```python
def direction_tier_promotion(
    tiered_candidates: dict[str, list[dict[str, Any]]],
    direction_reference_map: list[dict[str, Any]],
    weekend_market_candidate: dict[str, Any] | None,
    *,
    direction_momentum: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Promote direction-aligned candidates between tiers.

    Only when signal_strength == "high":
    - T2 leader/high_beta → T1 (if T1 < 10)
    - T3 leader → T2 (if T2 < 5)
    Max 2 promotions per run.
    Momentum "caution" disables promotion for that direction.
    """
    if not weekend_market_candidate or not isinstance(weekend_market_candidate, dict):
        return dict(tiered_candidates)
    signal_strength = clean_text(weekend_market_candidate.get("signal_strength"))
    if signal_strength != "high":
        return dict(tiered_candidates)

    # Build momentum caution set
    caution_keys: set[str] = set()
    for m in (direction_momentum or []):
        if clean_text(m.get("momentum_signal")) == "caution":
            caution_keys.add(clean_text(m.get("direction_key")))

    # Build ticker→direction_key lookup
    ticker_to_key: dict[str, str] = {}
    for entry in direction_reference_map:
        dk = clean_text(entry.get("direction_key"))
        for item in entry.get("leaders", []):
            t = clean_text(item.get("ticker"))
            if t:
                ticker_to_key[t] = dk
        for item in entry.get("high_beta_names", []):
            t = clean_text(item.get("ticker"))
            if t and t not in ticker_to_key:
                ticker_to_key[t] = dk

    result = {k: list(v) for k, v in tiered_candidates.items()}
    promotions = 0
    max_promotions = 2

    # T2 → T1
    if promotions < max_promotions:
        remaining_t2 = []
        for c in result.get("T2", []):
            tags = set(c.get("tier_tags") or [])
            ticker = clean_text(c.get("ticker"))
            dk = ticker_to_key.get(ticker, "")
            is_direction = "direction_leader" in tags or "direction_high_beta" in tags
            if (
                is_direction
                and promotions < max_promotions
                and len(result.get("T1", [])) < TIER_CAPS["T1"]
                and dk not in caution_keys
            ):
                promoted = dict(c)
                promoted_tags = list(promoted.get("tier_tags") or [])
                promoted_tags.append("direction_promoted")
                promoted["tier_tags"] = promoted_tags
                promoted["wrapper_tier"] = "T1"
                result.setdefault("T1", []).append(promoted)
                promotions += 1
            else:
                remaining_t2.append(c)
        result["T2"] = remaining_t2

    # T3 → T2 (leaders only)
    if promotions < max_promotions:
        remaining_t3 = []
        for c in result.get("T3", []):
            tags = set(c.get("tier_tags") or [])
            ticker = clean_text(c.get("ticker"))
            dk = ticker_to_key.get(ticker, "")
            is_leader = "direction_leader" in tags
            if (
                is_leader
                and promotions < max_promotions
                and len(result.get("T2", [])) < TIER_CAPS["T2"]
                and dk not in caution_keys
            ):
                promoted = dict(c)
                promoted_tags = list(promoted.get("tier_tags") or [])
                promoted_tags.append("direction_promoted")
                promoted["tier_tags"] = promoted_tags
                promoted["wrapper_tier"] = "T2"
                result.setdefault("T2", []).append(promoted)
                promotions += 1
            else:
                remaining_t3.append(c)
        result["T3"] = remaining_t3

    return result
```

- [ ] **Step 4: Add to `__all__`**

Add `"direction_tier_promotion"` to the `_extra` tuple.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::DirectionTierPromotionTests -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add tests/test_direction_layer_integration.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: add direction-based tier promotion with cap and momentum guard"
```

---

### Task 5: Confirmation Gate Bypass (`month_end_shortlist_runtime.py`)

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py:2354-2397`
- Test: `tests/test_direction_layer_integration.py`

- [ ] **Step 1: Add gate bypass tests**

Append to `tests/test_direction_layer_integration.py`:

```python
class ConfirmationGateBypassTests(unittest.TestCase):
    """Spec Section 4: confirmation gate bypass for direction-aligned candidates."""

    def _base_candidate(self, **overrides):
        base = {
            "ticker": "300308",
            "name": "中际旭创",
            "keep": True,
            "score": 58.0,
            "keep_threshold_gap": 1.5,  # marginal — would normally trigger gate
            "midday_status": "qualified",
            "midday_action": "可执行",
            "structured_catalyst_score": 15.0,
            "execution_state": "live",
            "hard_filter_failures": [],
            "tier_tags": ["direction_leader"],
            "direction_boost": {
                "signal_strength": "high",
                "direction_key": "optical_interconnect",
            },
        }
        base.update(overrides)
        return base

    def test_gate_bypass_for_direction_leader_high_signal(self):
        """Direction leader + high signal → stays 可执行 despite marginal gap."""
        import month_end_shortlist_runtime as runtime

        cand = self._base_candidate()
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "可执行")

    def test_gate_bypass_blocked_by_review_force_gate(self):
        """review_force_gate overrides direction bypass → gate triggers."""
        import month_end_shortlist_runtime as runtime

        cand = self._base_candidate(review_force_gate=True)
        result = runtime.intraday_confirmation_gate(cand)
        self.assertEqual(result["midday_action"], "待确认")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::ConfirmationGateBypassTests -v`
Expected: FAIL — the first test will show `待确认` instead of `可执行` (bypass not yet implemented)

- [ ] **Step 3: Modify `intraday_confirmation_gate` to add direction bypass**

In `month_end_shortlist_runtime.py`, modify `intraday_confirmation_gate()` (line 2354). After the early return for non-可执行 (line 2373: `if action != "可执行": return result`), add the direction bypass check **before** the marginal condition checks:

Find this block (around lines 2370-2375):

```python
    result = dict(candidate)
    action = clean_text(result.get("midday_action"))
    if action != "可执行":
        return result
```

Replace with:

```python
    result = dict(candidate)
    action = clean_text(result.get("midday_action"))
    if action != "可执行":
        return result

    # Direction bypass: leader/high_beta + high signal → skip gate
    # Priority: review_force_gate always wins (checked first below)
    force_gate = bool(result.get("review_force_gate"))
    if not force_gate:
        tags = set(result.get("tier_tags") or [])
        direction_boost = result.get("direction_boost") if isinstance(result.get("direction_boost"), dict) else {}
        is_direction_ref = "direction_leader" in tags or "direction_high_beta" in tags
        is_high_signal = clean_text(direction_boost.get("signal_strength")) == "high"
        if is_direction_ref and is_high_signal:
            return result  # bypass gate
```

Then update the existing `force_gate` line (around line 2388) — since we already computed it above, remove the duplicate:

Find:

```python
    execution_state = clean_text(result.get("execution_state")) or infer_execution_state(result)
    force_gate = bool(result.get("review_force_gate"))
```

Replace with:

```python
    execution_state = clean_text(result.get("execution_state")) or infer_execution_state(result)
    # force_gate already computed above for direction bypass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::ConfirmationGateBypassTests -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run existing gate tests for regression**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_confirmation_gate_and_priority_boost.py -v --tb=short`
Expected: All existing gate tests still pass

- [ ] **Step 6: Commit**

```bash
git add tests/test_direction_layer_integration.py financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: add direction-based confirmation gate bypass"
```

---

### Task 6: Postclose Review Momentum Proxy (`postclose_review_runtime.py`)

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py`
- Test: `tests/test_direction_layer_integration.py`

- [ ] **Step 1: Add momentum tests**

Append to `tests/test_direction_layer_integration.py`:

```python
class MomentumProxyTests(unittest.TestCase):
    """Spec Section 5: postclose review as momentum proxy."""

    def _make_review_output(self, candidates_reviewed):
        return {
            "trade_date": "2026-04-21",
            "candidates_reviewed": candidates_reviewed,
            "summary": {},
            "prior_review_adjustments": [],
        }

    def test_momentum_confirmed_full_boost(self):
        """>=50% correct, zero too_aggressive → confirmed."""
        from postclose_review_runtime import compute_direction_momentum

        candidates = [
            {"ticker": "300308", "judgment": "plan_correct", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "leader"},
            {"ticker": "300394", "judgment": "plan_correct", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "high_beta"},
        ]
        momentum = compute_direction_momentum(candidates)
        entry = [m for m in momentum if m["direction_key"] == "optical_interconnect"][0]
        self.assertEqual(entry["momentum_signal"], "confirmed")
        self.assertEqual(entry["aligned_correct"], 2)
        self.assertEqual(entry["aligned_too_aggressive"], 0)

    def test_momentum_caution_halves_boost(self):
        """Any too_aggressive among aligned → caution."""
        from postclose_review_runtime import compute_direction_momentum

        candidates = [
            {"ticker": "300308", "judgment": "plan_correct", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "leader"},
            {"ticker": "300394", "judgment": "plan_too_aggressive", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "high_beta"},
        ]
        momentum = compute_direction_momentum(candidates)
        entry = [m for m in momentum if m["direction_key"] == "optical_interconnect"][0]
        self.assertEqual(entry["momentum_signal"], "caution")

    def test_momentum_fading_zeros_boost(self):
        """All aligned are correct_negative → fading."""
        from postclose_review_runtime import compute_direction_momentum

        candidates = [
            {"ticker": "300308", "judgment": "plan_correct_negative", "direction_aligned": True,
             "direction_key": "optical_interconnect", "direction_role": "leader"},
        ]
        momentum = compute_direction_momentum(candidates)
        entry = [m for m in momentum if m["direction_key"] == "optical_interconnect"][0]
        self.assertEqual(entry["momentum_signal"], "fading")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::MomentumProxyTests -v`
Expected: FAIL — `ImportError: cannot import name 'compute_direction_momentum'`

- [ ] **Step 3: Implement `compute_direction_momentum`**

In `postclose_review_runtime.py`, add before `build_review_markdown()` (before line 172):

```python
def compute_direction_momentum(
    candidates_reviewed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compute direction momentum signals from reviewed candidates.

    Groups direction-aligned candidates by direction_key and produces
    a momentum_signal for each direction based on judgment distribution.

    Returns list of direction momentum entries (empty for directions with
    zero aligned candidates).
    """
    # Group by direction_key
    by_key: dict[str, dict[str, Any]] = {}
    for c in candidates_reviewed:
        if not c.get("direction_aligned"):
            continue
        dk = (c.get("direction_key") or "").strip()
        if not dk:
            continue
        if dk not in by_key:
            by_key[dk] = {
                "direction_key": dk,
                "direction_label": dk,
                "aligned_candidates_count": 0,
                "aligned_correct": 0,
                "aligned_too_aggressive": 0,
                "aligned_missed": 0,
            }
        entry = by_key[dk]
        entry["aligned_candidates_count"] += 1
        judgment = (c.get("judgment") or "").strip()
        if judgment == "plan_correct":
            entry["aligned_correct"] += 1
        elif judgment == "plan_too_aggressive":
            entry["aligned_too_aggressive"] += 1
        elif judgment == "missed_opportunity":
            entry["aligned_missed"] += 1

    result = []
    for dk, entry in by_key.items():
        count = entry["aligned_candidates_count"]
        if count == 0:
            continue
        # Evaluation order: caution → strengthening → confirmed → fading
        if entry["aligned_too_aggressive"] > 0:
            signal = "caution"
        elif entry["aligned_missed"] > 0 and entry["aligned_too_aggressive"] == 0:
            signal = "strengthening"
        elif entry["aligned_correct"] / count >= 0.5:
            signal = "confirmed"
        else:
            signal = "fading"
        entry["momentum_signal"] = signal
        result.append(entry)
    return result
```

- [ ] **Step 4: Integrate into `run_postclose_review`**

In `postclose_review_runtime.py`, modify `run_postclose_review()`. In the candidate loop (around line 138), after building the `candidates_reviewed` entry, add direction fields:

Find the `candidates_reviewed.append({` block (line 138-146). Change:

```python
        candidates_reviewed.append({
            "ticker": ticker,
            "name": name,
            "plan_action": plan_action,
            "actual_return_pct": actual_return,
            "intraday_structure": intraday_structure,
            "judgment": judgment,
            **adj,
        })
```

to:

```python
        direction_boost = cand.get("direction_boost") if isinstance(cand.get("direction_boost"), dict) else {}
        candidates_reviewed.append({
            "ticker": ticker,
            "name": name,
            "plan_action": plan_action,
            "actual_return_pct": actual_return,
            "intraday_structure": intraday_structure,
            "judgment": judgment,
            "direction_aligned": bool(direction_boost),
            "direction_key": direction_boost.get("direction_key") or None,
            "direction_role": direction_boost.get("direction_role") or None,
            **adj,
        })
```

Then, before the `return` statement (line 164), add momentum computation:

Find:

```python
    return {
        "trade_date": trade_date,
        "candidates_reviewed": candidates_reviewed,
        "summary": summary,
        "prior_review_adjustments": prior_review_adjustments,
    }
```

Replace with:

```python
    direction_momentum = compute_direction_momentum(candidates_reviewed)

    return {
        "trade_date": trade_date,
        "candidates_reviewed": candidates_reviewed,
        "summary": summary,
        "prior_review_adjustments": prior_review_adjustments,
        "direction_momentum": direction_momentum,
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::MomentumProxyTests -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run existing postclose review tests for regression**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_postclose_review_runtime.py -v --tb=short`
Expected: All existing tests pass

- [ ] **Step 7: Commit**

```bash
git add tests/test_direction_layer_integration.py financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py
git commit -m "feat: add direction momentum proxy to postclose review"
```

---

### Task 7: Decision Flow Card and Report Labels

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py:3065` (`build_decision_flow_card`)
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py:3325` (`build_weekend_market_candidate_markdown`)
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py:172` (`build_review_markdown`)
- Test: `tests/test_direction_layer_integration.py`

- [ ] **Step 1: Add decision flow card test**

Append to `tests/test_direction_layer_integration.py`:

```python
class DecisionFlowCardDirectionTests(unittest.TestCase):
    """Spec Section 6: decision flow card direction labels."""

    def test_decision_flow_card_direction_labels(self):
        """Card contains direction labels when direction_boost is present."""
        import month_end_shortlist_runtime as runtime

        factor = {
            "ticker": "300308",
            "name": "中际旭创",
            "action": "可执行",
            "score": 58.0,
            "keep_threshold_gap": 5.0,
            "tier_tags": ["direction_leader", "direction_theme_aligned", "direction_promoted"],
            "direction_boost": {
                "theme_delta": 3,
                "reference_delta": 6,
                "total_delta": 9,
                "direction_key": "optical_interconnect",
                "direction_role": "leader",
                "signal_strength": "high",
                "momentum_signal": "confirmed",
            },
            "wrapper_tier": "T1",
            "original_tier": "T2",
        }
        card = runtime.build_decision_flow_card(
            factor, keep_threshold=53.0, event_card=None, chain_entry=None,
        )
        card_str = str(card)
        self.assertIn("方向层加分", card_str)
        self.assertIn("方向信号强度", card_str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::DecisionFlowCardDirectionTests -v`
Expected: FAIL — card_str won't contain direction labels yet

- [ ] **Step 3: Add direction labels to `build_decision_flow_card`**

In `month_end_shortlist_runtime.py`, in `build_decision_flow_card()`, add direction label rendering. Find the end of the function (before the `return card` statement). Add before `return card`:

```python
    # Direction layer labels
    direction_boost = card.get("direction_boost") if isinstance(card.get("direction_boost"), dict) else {}
    if direction_boost:
        d_total = direction_boost.get("total_delta", 0)
        d_label = clean_text(direction_boost.get("direction_key")) or "unknown"
        d_role = clean_text(direction_boost.get("direction_role")) or ""
        d_signal = clean_text(direction_boost.get("signal_strength")) or ""
        d_momentum = clean_text(direction_boost.get("momentum_signal")) or ""

        role_label = {"leader": "龙头", "high_beta": "高弹性"}.get(d_role, d_role)
        direction_notes: list[str] = []
        if d_total > 0:
            direction_notes.append(f"方向层加分：+{d_total}（{d_label} {role_label}）")
            direction_notes.append(f"方向信号强度：{d_signal}")
            original_score = round(float(card.get("score") or 0) - d_total, 1)
            direction_notes.append(f"原始得分：{original_score} → 方向调整后：{card.get('score')}")
        if "direction_promoted" in tier_tags:
            original_tier = clean_text(card.get("original_tier")) or "?"
            current_tier = clean_text(card.get("wrapper_tier")) or "?"
            direction_notes.append(f"方向层晋级：{original_tier} → {current_tier}（{d_label} {role_label}，信号={d_signal}）")
        if d_momentum:
            momentum_labels = {
                "confirmed": "confirmed（前日复盘确认）",
                "strengthening": "strengthening（前日方向强化）",
                "caution": "caution（前日方向过激，加分减半）",
                "fading": "fading（前日方向衰退）",
            }
            direction_notes.append(f"方向动量：{momentum_labels.get(d_momentum, d_momentum)}")
        if direction_notes:
            existing_notes = card.get("direction_notes", [])
            card["direction_notes"] = existing_notes + direction_notes
```

- [ ] **Step 4: Add direction bypass note to gate section**

In `intraday_confirmation_gate()`, when bypass is applied, add a note. In the bypass block added in Task 5, change:

```python
        if is_direction_ref and is_high_signal:
            return result  # bypass gate
```

to:

```python
        if is_direction_ref and is_high_signal:
            dk = clean_text(direction_boost.get("direction_key")) or ""
            result["gate_bypass_note"] = f"方向层免确认：{dk} 信号强度=high"
            return result  # bypass gate
```

And in the `if force_gate` block, when force_gate is True and direction tags are present, add:

After `if not force_gate:` block, before the marginal condition checks, add:

```python
    # Note when direction bypass is blocked by review_force_gate
    if force_gate:
        tags = set(result.get("tier_tags") or [])
        if "direction_leader" in tags or "direction_high_beta" in tags:
            result["gate_bypass_note"] = "方向层免确认：不适用（复盘强制门控优先）"
```

- [ ] **Step 5: Extend `build_weekend_market_candidate_markdown` with direction integration section**

In `month_end_shortlist_runtime.py`, in `build_weekend_market_candidate_markdown()` (line 3325), add a new subsection at the end of the function, before the `return lines` statement. The function currently returns `lines` at line 3384. Add before that:

```python
    # Direction execution integration summary
    if direction_reference_map:
        lines.append("")
        lines.append("## 方向层执行整合")
        lines.append("")
        has_resolved = any(
            any(clean_text(item.get("ticker")) for item in entry.get("leaders", []))
            or any(clean_text(item.get("ticker")) for item in entry.get("high_beta_names", []))
            for entry in direction_reference_map
        )
        if has_resolved:
            lines.append("方向层已解析代码，可参与执行层评分、晋级和门控。")
        else:
            lines.append("方向层代码未解析，仅作参考。")
        lines.append("")
```

- [ ] **Step 6: Extend `build_review_markdown` with direction momentum section**

In `postclose_review_runtime.py`, in `build_review_markdown()`, add a direction momentum section before the final `return`. Find (around line 213-215):

```python
    else:
        lines.append("- 无需调整")
    lines.append("")

    return "\n".join(lines)
```

Replace with:

```python
    else:
        lines.append("- 无需调整")
    lines.append("")

    # Direction momentum section
    direction_momentum = review.get("direction_momentum", [])
    if direction_momentum:
        lines.append("## 方向动量信号")
        lines.append("")
        lines.append("| 方向 | 对齐数 | 正确 | 过激 | 错过 | 信号 |")
        lines.append("|---|---|---|---|---|---|")
        for m in direction_momentum:
            lines.append(
                f"| {m.get('direction_label', m.get('direction_key', '?'))} "
                f"| {m.get('aligned_candidates_count', 0)} "
                f"| {m.get('aligned_correct', 0)} "
                f"| {m.get('aligned_too_aggressive', 0)} "
                f"| {m.get('aligned_missed', 0)} "
                f"| {m.get('momentum_signal', '?')} |"
            )
        lines.append("")

    return "\n".join(lines)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py::DecisionFlowCardDirectionTests -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py financial-analysis/skills/month-end-shortlist/scripts/postclose_review_runtime.py tests/test_direction_layer_integration.py
git commit -m "feat: add direction labels to decision flow card, gate notes, and report"
```

---

### Task 8: Pipeline Integration — Wire Everything Into `enrich_track_result` and `run_month_end_shortlist`

**Files:**
- Modify: `financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py`

This task wires the new functions into the actual execution pipeline. No new tests — the existing 18 tests validate the functions; this task connects them.

- [ ] **Step 1: Update imports in `month_end_shortlist_runtime.py`**

The new functions are defined in the same file, so no import changes needed. But update the import from `weekend_market_candidate_runtime` (line 32-35). Change:

```python
from weekend_market_candidate_runtime import (
    build_weekend_market_candidate,
    normalize_weekend_market_candidate_input,
)
```

to:

```python
from weekend_market_candidate_runtime import (
    build_weekend_market_candidate,
    normalize_weekend_market_candidate_input,
    resolve_direction_tickers,
)
```

- [ ] **Step 2: Wire `cross_check_direction_tickers` into `run_month_end_shortlist`**

In `run_month_end_shortlist()`, after the universe fetch (line 4708: `full_universe = universe_fetcher(prepared_payload)`), add direction cross-check. Find (around line 4708):

```python
        full_universe = universe_fetcher(prepared_payload)
        request_tickers = {clean_text(row.get("ticker")) for row in request_market_strength if clean_text(row.get("ticker"))}
```

Insert between them:

```python
        # Cross-check direction tickers against fetched universe
        _, direction_ref_map = build_weekend_market_candidate(weekend_market_candidate_input)
        if direction_ref_map:
            direction_ref_map = cross_check_direction_tickers(direction_ref_map, full_universe)
```

Note: `build_weekend_market_candidate` is already called at line 4699. We need the `direction_ref_map` from that call. Modify line 4699 to capture it:

Find:

```python
        prepared_weekend_market_candidate, _ = build_weekend_market_candidate(
            weekend_market_candidate_input
        )
```

Replace with:

```python
        prepared_weekend_market_candidate, prepared_direction_ref_map = build_weekend_market_candidate(
            weekend_market_candidate_input
        )
```

Then after universe fetch (line 4708), add:

```python
        if prepared_direction_ref_map:
            prepared_direction_ref_map = cross_check_direction_tickers(prepared_direction_ref_map, full_universe)
```

- [ ] **Step 3: Wire `direction_alignment_boost` and `direction_tier_promotion` into `enrich_track_result`**

In `enrich_track_result()` (line 4062), the function needs access to direction data. Add parameters:

Change signature (line 4062-4068):

```python
def enrich_track_result(
    result: dict[str, Any],
    failure_candidates: list[dict[str, Any]],
    assessed_candidates: list[dict[str, Any]] | None = None,
    *,
    track_name: str = "",
    track_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

to:

```python
def enrich_track_result(
    result: dict[str, Any],
    failure_candidates: list[dict[str, Any]],
    assessed_candidates: list[dict[str, Any]] | None = None,
    *,
    track_name: str = "",
    track_config: dict[str, Any] | None = None,
    direction_reference_map: list[dict[str, Any]] | None = None,
    weekend_market_candidate: dict[str, Any] | None = None,
    prior_review_adjustments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
```

Then, in `enrich_track_result`, after `top_picks` is built (line 4181-4182) and before `assign_tiers` (line 4190), insert:

```python
        # Direction alignment boost (after review_based_priority_boost, before assign_tiers)
        if direction_reference_map and weekend_market_candidate:
            direction_momentum = None
            if prior_review_adjustments and isinstance(prior_review_adjustments, list):
                # Look for direction_momentum in the review data
                for adj in prior_review_adjustments:
                    if isinstance(adj, dict) and "direction_momentum" in adj:
                        direction_momentum = adj["direction_momentum"]
                        break
            top_picks = direction_alignment_boost(
                top_picks, direction_reference_map, weekend_market_candidate,
                direction_momentum=direction_momentum,
            )
            enriched["top_picks"] = top_picks
```

After `assign_tiers` and floor policy (around line 4200), before the rescued_by_ticker block, insert:

```python
        # Direction tier promotion (after assign_tiers)
        if direction_reference_map and weekend_market_candidate:
            tiers = direction_tier_promotion(
                tiers, direction_reference_map, weekend_market_candidate,
                direction_momentum=direction_momentum if 'direction_momentum' in dir() else None,
            )
```

- [ ] **Step 4: Pass direction data when calling `enrich_track_result`**

In `run_month_end_shortlist()`, where `enrich_track_result` is called (line 4804), update:

Find:

```python
            enriched = enrich_track_result(
                result,
                track_failure_log,
                track_assessed_log,
                track_name=track_name,
                track_config=track_cfg,
            )
```

Replace with:

```python
            enriched = enrich_track_result(
                result,
                track_failure_log,
                track_assessed_log,
                track_name=track_name,
                track_config=track_cfg,
                direction_reference_map=prepared_direction_ref_map if prepared_direction_ref_map else None,
                weekend_market_candidate=prepared_weekend_market_candidate,
            )
```

- [ ] **Step 5: Update `__all__` with all new exports**

Ensure these are all in the `_extra` tuple:

```python
    "cross_check_direction_tickers",
    "direction_alignment_boost",
    "direction_tier_promotion",
```

- [ ] **Step 6: Run full test suite**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/ -x -q --tb=short 2>&1 | tail -10`
Expected: All tests pass (346 existing + 18 new = 364)

- [ ] **Step 7: Commit**

```bash
git add financial-analysis/skills/month-end-shortlist/scripts/month_end_shortlist_runtime.py
git commit -m "feat: wire direction integration into execution pipeline"
```

---

### Task 9: Final Regression and Cleanup

- [ ] **Step 1: Run full test suite one more time**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/ -q --tb=short 2>&1 | tail -10`
Expected: All 364+ tests pass

- [ ] **Step 2: Verify test count**

Run: `cd D:\Users\rickylu\dev\financial-services-plugins-clean && python -m pytest tests/test_direction_layer_integration.py -v --tb=short 2>&1 | tail -25`
Expected: 18 tests, all PASSED

- [ ] **Step 3: Final commit if any cleanup needed**

```bash
git add -A
git status
# Only commit if there are changes
git commit -m "chore: direction layer integration cleanup"
```

---

## Verification

1. **Unit tests:** `python -m pytest tests/test_direction_layer_integration.py -v` → 18 tests pass
2. **Regression:** `python -m pytest tests/ -q` → all existing 346 tests + 18 new = 364 pass
3. **Specific regression files:**
   - `python -m pytest tests/test_confirmation_gate_and_priority_boost.py -v` → existing gate tests pass
   - `python -m pytest tests/test_postclose_review_runtime.py -v` → existing review tests pass
4. **Spot check:** Import the new functions in a Python REPL:
   ```python
   import sys; sys.path.insert(0, "financial-analysis/skills/month-end-shortlist/scripts")
   from month_end_shortlist_runtime import direction_alignment_boost, direction_tier_promotion, cross_check_direction_tickers
   from weekend_market_candidate_runtime import resolve_direction_tickers, default_ticker_resolver
   from postclose_review_runtime import compute_direction_momentum
   ```
