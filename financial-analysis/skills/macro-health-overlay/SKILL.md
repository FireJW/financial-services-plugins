---
name: macro-health-overlay
description: Build a bounded macro-health overlay for risk-asset screening from real-yield, dollar, liquidity, financial-conditions, inflation-expectations, and equity-confirmation signals. Use when you want a reusable top-down risk window card rather than a full macro note.
---

# Macro Health Overlay

Use this skill when the goal is to answer:

- is the risk-asset window `favorable`, `tentative`, `mixed`, or `adverse`
- should downstream stock screening lean `risk-on`, `selective`, or
  `defensive`
- how should `10Y real yield + DXY + liquidity + financial conditions` be
  translated into a reusable request block

This is not a full macro-note workflow. It is a bounded overlay builder.

## Default Boundary

- prefer structured signal states over free-form narrative
- primary trigger cluster:
  - `real yield`
  - `DXY`
- confirmation cluster:
  - `financial conditions`
  - `liquidity`
  - `equity confirmation`
- false-positive controls:
  - `breakevens`
  - `oil`
  - `term premium`
- do not let this layer override stock-level hard filters by itself

## Local Helper

- `scripts\run_macro_health_overlay.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>] [--request-output <resolved-request.json>]`

Companion entrypoint:

- `financial-analysis\commands\macro-health-assisted-shortlist.md`

## Request Shape

Start from:

- `examples/macro-health-overlay-request.template.json`

Key fields:

- `analysis_time`
- `as_of`
- `live_data_provider`
- `live_fill_mode`
- `lookback_trading_days`
- `seed_snapshot_path`
- `seed_fill_mode`
- `write_live_seed_cache`
- `integration_mode`
- `signal_states`
- `signal_snapshot`
- `signal_notes`
- `source_frameworks`
- `evidence`
- `shortlist_request_path`

## Output Expectations

Return:

- `macro_health_overlay`
- `scorecard`
- `shortlist_guidance`
- `live_fetch_summary`
- `seed_summary`
- optional `resolved_shortlist_request`
- `report_markdown`

Current preferred live route:

- `public_macro_mix`
  - `Treasury real yield curve CSV`
  - `Treasury nominal yield curve CSV`
  - `Fed H10 broad dollar CSV`
  - `Chicago Fed NFCI CSV`
  - `Cboe VIX history CSV`

## References

- `docs/runtime/macro-health-overlay-framework.md`
- `docs/runtime/pb-flow-regime-overlay.md`
- `partner-built/lseg/skills/macro-rates-monitor/SKILL.md`
