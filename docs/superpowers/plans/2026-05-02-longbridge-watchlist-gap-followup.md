# Longbridge Watchlist Gap Follow-up Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining Longbridge watchlist evidence gaps after the 2026-05-02 dry-run and keep all account-side actions gated.

**Architecture:** Keep `longbridge-screen` as the read-only scoring and evidence layer. Use `longbridge-intraday-monitor` only for open-session P1 checks after trigger/stop levels exist. Use `longbridge-action-gateway` only for audited dry-run plans unless the user provides exact confirmation text for a real account write.

**Tech Stack:** Python runtime scripts under `financial-analysis/skills/longbridge/scripts`, command docs under `financial-analysis/commands`, pytest regression tests under `tests/test_longbridge*.py`, and local dry-run artifacts under `.tmp/longbridge-watchlist-2026-05-02`.

## Current Status as of 2026-05-03

- Landed and pushed `a7a5183 feat(longbridge): add watchlist qualitative dry-run workflow`.
- Landed and pushed `cd4a1c8 fix(longbridge): tighten qualitative report evidence`.
- Generated local handoff artifacts:
  - `.tmp/longbridge-watchlist-2026-05-02/result.longbridge-screen.qualitative.json`
  - `.tmp/longbridge-watchlist-2026-05-02/report.longbridge-screen.qualitative.md`
  - `.tmp/longbridge-watchlist-2026-05-02/review.action-gateway-dry-run-2026-05-03.json`
- Task 1 remains blocked by Longbridge CLI authentication refresh. `auth status` reports `refresh_pending`, while read-only `trading days` and `market-status` return `Authentication failed: Not authenticated. Please run 'longbridge auth login' first.`
- Task 2 is complete for nested/non-standard detail payload preservation. `compact_detail_payload()` now unwraps nested response containers and preserves PDF/plain/raw text previews.
- Task 3 is complete for normalized profit, EPS, revenue, and operating cash-flow aliases, including common camelCase fields.
- Task 4 is complete for valuation/target-price conflict tests: target below spot and expensive optimistic target are flagged; fair PE with positive target is not.
- Task 5 dry-run review is complete. The 2026-05-02 action gateway artifact has 12 plans, all `should_apply: false`, all `side_effects: "none"`, and no order or DCA operation.
- `longbridge_ownership_runtime.py` and `longbridge_quant_runtime.py` already have minimal CLI `main()` and `--help` behavior covered by tests; no broader CLI rewrite is recommended.
- No real watchlist, alert, order, or DCA side effect has been run.

---

## New Session Startup

Use this prompt in a new Codex session:

```text
Work in D:\Users\rickylu\dev\financial-services-plugins-clean.
Do not sync WSL Codex config.
Keep Longbridge watchlist work read-only unless I provide exact confirmation text.
Read docs/superpowers/plans/2026-05-02-longbridge-watchlist-gap-followup.md,
financial-analysis/commands/longbridge-screen.md,
financial-analysis/commands/longbridge-intraday-monitor.md,
financial-analysis/commands/longbridge-action-gateway.md, and
.tmp/longbridge-watchlist-2026-05-02/report.longbridge-screen.qualitative.md.
Continue from the remaining gaps: open-session P1 intraday rerun, news/filing detail parsing, cash-flow extraction, valuation/target conflict handling, and action-gateway dry-run review.
```

## Task 1: Open-session P1 intraday rerun

**Files:**
- Read: `.tmp/longbridge-watchlist-2026-05-02/request.intraday-monitor.json`
- Read: `financial-analysis/commands/longbridge-intraday-monitor.md`
- Modify only if needed: `financial-analysis/skills/longbridge/scripts/longbridge_intraday_monitor_runtime.py`
- Test: `tests/test_longbridge_intraday_monitor_runtime.py`

- [ ] Confirm the next run date is a trading day with `longbridge trading days CN --start YYYY-MM-DD --end YYYY-MM-DD --format json`.
- [ ] Run intraday monitor against the same three symbols after market data is live.
- [ ] Verify output still has `should_apply: false` and `side_effects: "none"`.
- [ ] Compare `plan_status`, `capital_flow.confirms`, `abnormal_volume.exists`, and `trade_stats` against the qualitative screen.
- [ ] If CLI behavior changes, add or update a failing test before modifying runtime code.
- [ ] Run `py -m pytest tests/test_longbridge_intraday_monitor_runtime.py -q`.

## Task 2: Parse news and filing detail more reliably

**Files:**
- Modify: `financial-analysis/skills/longbridge/scripts/longbridge_screen_runtime.py`
- Test: `tests/test_longbridge_screen_runtime.py`

- [ ] Add a failing test where `news detail` or `filing detail` returns plain text, PDF-like text, or non-standard JSON with useful body text.
- [ ] Extend `compact_detail_payload()` to preserve a meaningful `content_preview`, `content_length`, and `title` for those cases.
- [ ] Keep failures under `financial_event_analysis.unavailable` when detail cannot be parsed.
- [ ] Verify `missed_attention_priorities` removes `unparsed_news_or_filing_detail` only when both detail layers produce usable previews.
- [ ] Run `py -m pytest tests/test_longbridge_screen_runtime.py -q`.

## Task 3: Extract profit and operating cash-flow evidence

**Files:**
- Modify: `financial-analysis/skills/longbridge/scripts/longbridge_screen_runtime.py`
- Test: `tests/test_longbridge_screen_runtime.py`

- [ ] Add fixture cases for financial-report payloads with `net_income`, `net_income_yoy`, `operating_cash_flow`, and alternative field names.
- [ ] Normalize those fields into `financial_event_analysis.financial_reports`.
- [ ] Keep `profit_cashflow_divergence` as P0 when profit is positive but operating cash-flow is negative or missing after a profit-growth catalyst.
- [ ] Add Markdown output lines that show the cash-flow conclusion in `Qualitative Evaluation`.
- [ ] Run `py -m pytest tests/test_longbridge_screen_runtime.py -q`.

## Task 4: Tighten valuation and target-price conflict review

**Files:**
- Modify: `financial-analysis/skills/longbridge/scripts/longbridge_screen_runtime.py`
- Test: `tests/test_longbridge_screen_runtime.py`

- [ ] Add tests for three cases: target below spot, expensive PE with optimistic target, and fair PE with positive target.
- [ ] Keep `valuation_target_price_conflict` only for the first two cases.
- [ ] Ensure `qualitative_verdict` explains whether the conflict blocks escalation or only requires manual review.
- [ ] Run `py -m pytest tests/test_longbridge_screen_runtime.py -q`.

## Task 5: Review action gateway dry-run only

**Files:**
- Read: `.tmp/longbridge-watchlist-2026-05-02/result.action-gateway-dry-run.json`
- Read: `financial-analysis/commands/longbridge-action-gateway.md`
- Modify only if needed: `financial-analysis/skills/longbridge/scripts/longbridge_action_gateway_runtime.py`
- Test: `tests/test_longbridge_action_gateway_runtime.py`

- [ ] Confirm every generated action plan has `should_apply: false` and `side_effects: "none"`.
- [ ] Confirm no order or DCA plan can pass the apply gate.
- [ ] If real watchlist or alert writes are requested, stop and ask the user for exact confirmation text before running any apply path.
- [ ] Run `py -m pytest tests/test_longbridge_action_gateway_runtime.py -q`.

## Required Final Regression

Run all of these before claiming completion:

```powershell
py -m pytest tests/test_longbridge_screen_runtime.py tests/test_longbridge_action_gateway_runtime.py -q
py -m pytest tests/test_longbridge_intraday_monitor_runtime.py tests/test_longbridge_ownership_runtime.py tests/test_longbridge_quant_runtime.py -q
py -m pytest tests/test_tradingagents_longbridge_market.py tests/test_tradingagents_longbridge_integration.py -q
```

## Safety Gate

Do not run real Longbridge watchlist mutation, alert mutation, order, or DCA commands unless all of the following are true:

- the user explicitly asks for a real account write,
- the exact generated confirmation text is shown to the user,
- the user replies with the exact confirmation text,
- `LONGBRIDGE_ALLOW_WRITE=1` is intentionally set for that command,
- the operation is not order or DCA, which remain hard-blocked.
