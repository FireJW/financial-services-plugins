# Eastmoney Cache Preheat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small standalone command that preheats Eastmoney cache for a chosen ticker set so later shortlist runs can benefit from existing cache fallback behavior.

**Architecture:** Create a focused CLI script under `financial-analysis/skills/month-end-shortlist/scripts` that parses ticker input from direct CLI arguments or files, reuses the existing Eastmoney fetch/cache-writing path, and prints per-ticker statuses plus a final summary. Keep it separate from `month_end_shortlist.py` so the shortlist main path stays clean.

**Tech Stack:** Python, pytest, Eastmoney cache helpers, `tradingagents_eastmoney_market.py`, shortlist scripts.

---

### Task 1: Add ticker input parsing tests and helpers

**Files:**
- Create: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py`
- Create: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py`

- [ ] **Step 1: Write failing tests for ticker parsing**

Create `tests/test_eastmoney_cache_preheat.py` with tests like:

```python
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
import sys
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import preheat_eastmoney_cache as module_under_test


class EastmoneyCachePreheatParsingTests(unittest.TestCase):
    def test_parse_cli_tickers_splits_and_deduplicates(self) -> None:
        tickers = module_under_test.parse_cli_tickers("000988.SZ, 002384.SZ,000988.SZ")
        self.assertEqual(tickers, ["000988.SZ", "002384.SZ"])

    def test_parse_tickers_file_reads_txt_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tickers.txt"
            path.write_text("000988.SZ\n\n002384.SZ\n", encoding="utf-8")
            tickers = module_under_test.parse_tickers_file(path)
        self.assertEqual(tickers, ["000988.SZ", "002384.SZ"])

    def test_parse_tickers_file_reads_json_array(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "tickers.json"
            path.write_text(json.dumps(["000988.SZ", "002384.SZ"]), encoding="utf-8")
            tickers = module_under_test.parse_tickers_file(path)
        self.assertEqual(tickers, ["000988.SZ", "002384.SZ"])
```

- [ ] **Step 2: Run the new test file to verify failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- FAIL because `preheat_eastmoney_cache.py` does not exist yet

- [ ] **Step 3: Create the minimal parsing script**

Create `financial-analysis/skills/month-end-shortlist/scripts/preheat_eastmoney_cache.py` with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def unique_tickers(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in values:
        ticker = " ".join(str(raw or "").split()).strip().upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        ordered.append(ticker)
    return ordered


def parse_cli_tickers(raw: str) -> list[str]:
    return unique_tickers(part for part in str(raw or "").split(","))


def parse_tickers_file(path: Path) -> list[str]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".json":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("Ticker json file must contain an array of strings.")
        return unique_tickers(payload)
    return unique_tickers(text.splitlines())


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Preheat Eastmoney cache for selected tickers.")
    parser.add_argument("--tickers", default="", help="Comma-separated ticker list.")
    parser.add_argument("--tickers-file", default="", help="Path to txt/json ticker file.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    tickers = parse_cli_tickers(args.tickers)
    if args.tickers_file:
        tickers.extend(parse_tickers_file(Path(args.tickers_file)))
    tickers = unique_tickers(tickers)
    if not tickers:
        parser.error("Provide --tickers or --tickers-file.")
    for ticker in tickers:
        print(ticker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Re-run the parsing tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- "financial-analysis/skills/month-end-shortlist/scripts/preheat_eastmoney_cache.py" "tests/test_eastmoney_cache_preheat.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: add eastmoney cache preheat input parsing"
```

### Task 2: Reuse the existing Eastmoney cache-writing path for a 120-day preheat

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py`

- [ ] **Step 1: Add failing tests for per-ticker preheat classification**

Extend `tests/test_eastmoney_cache_preheat.py` with:

```python
from unittest.mock import patch


class EastmoneyCachePreheatStatusTests(unittest.TestCase):
    def test_preheat_ticker_reports_cache_written_when_fetch_succeeds(self) -> None:
        with patch.object(module_under_test, "fetch_eastmoney_daily_bars", return_value=[{"date": "2026-04-19"}]):
            result = module_under_test.preheat_ticker("000988.SZ", "2026-04-19")
        self.assertEqual(result["status"], "cache_written")
        self.assertEqual(result["ticker"], "000988.SZ")

    def test_preheat_ticker_reports_failed_when_fetch_raises(self) -> None:
        with patch.object(module_under_test, "fetch_eastmoney_daily_bars", side_effect=RuntimeError("boom")):
            result = module_under_test.preheat_ticker("000988.SZ", "2026-04-19")
        self.assertEqual(result["status"], "failed")
        self.assertIn("boom", result["message"])
```

- [ ] **Step 2: Run the test file to verify failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- FAIL because `preheat_ticker` does not exist yet

- [ ] **Step 3: Add minimal preheat logic with a 120-day window**

Modify `preheat_eastmoney_cache.py`:

```python
from datetime import date, timedelta
from tradingagents_eastmoney_market import fetch_daily_bars as fetch_eastmoney_daily_bars


DEFAULT_LOOKBACK_DAYS = 120


def preheat_ticker(ticker: str, target_date: str) -> dict[str, str]:
    ticker = unique_tickers([ticker])[0]
    target_dt = date.fromisoformat(target_date[:10])
    start_date = (target_dt - timedelta(days=DEFAULT_LOOKBACK_DAYS)).isoformat()
    try:
        rows = fetch_eastmoney_daily_bars(ticker, start_date, target_dt.isoformat())
    except Exception as exc:
        return {"ticker": ticker, "status": "failed", "message": str(exc)}
    if not rows:
        return {"ticker": ticker, "status": "failed", "message": "No rows returned"}
    return {"ticker": ticker, "status": "cache_written", "message": ""}
```

Use local date in `main()`:

```python
from datetime import datetime

target_date = datetime.now().date().isoformat()
```

- [ ] **Step 4: Re-run the preheat tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- "financial-analysis/skills/month-end-shortlist/scripts/preheat_eastmoney_cache.py" "tests/test_eastmoney_cache_preheat.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: add eastmoney cache preheat fetch path"
```

### Task 3: Distinguish cache hit from cache written

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py`

- [ ] **Step 1: Add failing tests for cache_hit vs cache_written**

Extend the test file with:

```python
    def test_preheat_ticker_reports_cache_hit_when_cache_already_exists(self) -> None:
        with patch.object(module_under_test, "eastmoney_cache_already_exists", return_value=True):
            result = module_under_test.preheat_ticker("000988.SZ", "2026-04-19")
        self.assertEqual(result["status"], "cache_hit")

    def test_preheat_ticker_reports_cache_written_when_cache_missing_but_fetch_succeeds(self) -> None:
        with patch.object(module_under_test, "eastmoney_cache_already_exists", return_value=False), patch.object(
            module_under_test, "fetch_eastmoney_daily_bars", return_value=[{"date": "2026-04-19"}]
        ):
            result = module_under_test.preheat_ticker("000988.SZ", "2026-04-19")
        self.assertEqual(result["status"], "cache_written")
```

- [ ] **Step 2: Run the preheat tests to confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- FAIL because cache-hit detection does not exist yet

- [ ] **Step 3: Add a cache existence helper**

Modify `preheat_eastmoney_cache.py`:

```python
from tradingagents_eastmoney_market import (
    EASTMONEY_DEFAULT_UT,
    cache_path,
    eastmoney_secid,
    format_date_yyyymmdd,
)


def eastmoney_cache_already_exists(ticker: str, start_date: str, end_date: str) -> bool:
    query = {
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "0",
        "lmt": "10000",
        "ut": EASTMONEY_DEFAULT_UT,
        "secid": eastmoney_secid(ticker),
        "beg": format_date_yyyymmdd(start_date),
        "end": format_date_yyyymmdd(end_date),
    }
    cache_name = f"kline-{json.dumps(query, ensure_ascii=True, sort_keys=True)}.json"
    return cache_path(cache_name).exists()
```

Update `preheat_ticker(...)`:

```python
    if eastmoney_cache_already_exists(ticker, start_date, target_dt.isoformat()):
        return {"ticker": ticker, "status": "cache_hit", "message": ""}
```

- [ ] **Step 4: Re-run the preheat tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- "financial-analysis/skills/month-end-shortlist/scripts/preheat_eastmoney_cache.py" "tests/test_eastmoney_cache_preheat.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: classify eastmoney cache preheat hits and writes"
```

### Task 4: Add per-ticker output and summary

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py`
- Modify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py`

- [ ] **Step 1: Add failing tests for stdout-style reporting**

Add tests like:

```python
    def test_build_summary_counts_statuses(self) -> None:
        summary = module_under_test.build_summary(
            [
                {"ticker": "000988.SZ", "status": "cache_written", "message": ""},
                {"ticker": "002384.SZ", "status": "cache_hit", "message": ""},
                {"ticker": "300476.SZ", "status": "failed", "message": "boom"},
            ]
        )
        self.assertEqual(summary["total"], 3)
        self.assertEqual(summary["cache_written"], 1)
        self.assertEqual(summary["cache_hit"], 1)
        self.assertEqual(summary["failed"], 1)
```

- [ ] **Step 2: Run the test file to confirm failure**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- FAIL because `build_summary` does not exist yet

- [ ] **Step 3: Add output helpers and wire them into main()**

Modify `preheat_eastmoney_cache.py`:

```python
def build_summary(results: list[dict[str, str]]) -> dict[str, int]:
    summary = {"total": len(results), "cache_hit": 0, "cache_written": 0, "failed": 0}
    for row in results:
        status = row.get("status")
        if status in summary:
            summary[status] += 1
    return summary


def print_results(results: list[dict[str, str]]) -> None:
    for row in results:
        status = row["status"]
        ticker = row["ticker"]
        message = row.get("message", "")
        if message:
            print(f"[{status}] {ticker} - {message}")
        else:
            print(f"[{status}] {ticker}")
    summary = build_summary(results)
    print("Summary:")
    print(f"- total: {summary['total']}")
    print(f"- cache_hit: {summary['cache_hit']}")
    print(f"- cache_written: {summary['cache_written']}")
    print(f"- failed: {summary['failed']}")
```

Then in `main()`:

```python
    results = [preheat_ticker(ticker, target_date) for ticker in tickers]
    print_results(results)
    return 0 if any(row["status"] != "failed" for row in results) else 1
```

- [ ] **Step 4: Re-run the preheat tests**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- PASS

- [ ] **Step 5: Commit**

```bash
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" add -- "financial-analysis/skills/month-end-shortlist/scripts/preheat_eastmoney_cache.py" "tests/test_eastmoney_cache_preheat.py"
git -C "D:\Users\rickylu\dev\financial-services-plugins-clean" commit -m "feat: add eastmoney cache preheat reporting"
```

### Task 5: Focused verification and a real preheat smoke

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py`

- [ ] **Step 1: Run the dedicated preheat test file**

Run:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe -m pytest D:\Users\rickylu\dev\financial-services-plugins-clean\tests\test_eastmoney_cache_preheat.py -q
```

Expected:
- PASS

- [ ] **Step 2: Run a small real preheat smoke**

Use a tiny ticker set:

```bash
C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe D:\Users\rickylu\dev\financial-services-plugins-clean\financial-analysis\skills\month-end-shortlist\scripts\preheat_eastmoney_cache.py --tickers 000988.SZ,002384.SZ,300476.SZ
```

Expected:
- each ticker prints one of:
  - `cache_hit`
  - `cache_written`
  - `failed`
- final summary prints counts

- [ ] **Step 3: Verify cache directory now contains files when preheat succeeds**

Check:

```bash
Get-ChildItem -LiteralPath "D:\Users\rickylu\dev\financial-services-plugins-clean\.tmp\tradingagents-eastmoney-cache" -Force
```

Expected:
- at least one cache file exists if any ticker succeeded

- [ ] **Step 4: Do not commit `.tmp` artifacts**

If cache files are created under `.tmp`, leave them uncommitted.

## Self-Review

- Spec coverage:
  - standalone command: Tasks 1-4
  - `--tickers` and `--tickers-file`: Task 1
  - txt/json file support: Task 1
  - 120-day default window: Task 2
  - success definitions `cache_hit` / `cache_written`: Tasks 2-3
  - per-ticker output + summary: Task 4
  - real smoke: Task 5
- Placeholder scan:
  - no `TODO`, `TBD`, or “implement later” placeholders
  - code steps include concrete snippets
  - test steps include actual test cases and commands
- Type consistency:
  - `parse_cli_tickers(...)`
  - `parse_tickers_file(...)`
  - `preheat_ticker(...)`
  - `eastmoney_cache_already_exists(...)`
  - `build_summary(...)`
  - statuses: `cache_hit`, `cache_written`, `failed`
