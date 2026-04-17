---
description: Build a reusable macro-health overlay for shortlist and trade-card workflows
argument-hint: "[request-json]"
---

# Macro Health Overlay

Use this command when you want a bounded top-down risk window card instead of a
full macro note.

What it does:

1. normalizes `real yield / DXY / financial conditions / liquidity /
   breakeven / oil / term premium / equity confirmation` inputs
2. can optionally fetch a public live snapshot through `live_data_provider`
   before normalizing signals
3. classifies the broad market window into
   `favorable / tentative / mixed / adverse`
4. emits a `macro_health_overlay` block that can be pasted into or merged into
   `month-end-shortlist`
5. optionally writes a resolved shortlist request when
   `shortlist_request_path` is supplied

Notes:

- default `integration_mode` is `advisory_only`
- supported live providers currently:
  - `fred_public`
  - `public_macro_mix`
- preferred live provider in the current environment:
  - `public_macro_mix`
  - uses `Treasury real + nominal yields`, `Fed H10 broad dollar`,
    `Chicago Fed ANFCI`, and `Cboe VIX`
- default live mode is still safe:
  - `live_data_provider = none`
  - `live_fill_mode = missing_only`
- set `integration_mode = score_light` only when you want downstream shortlist
  ranking to use a very small macro posture adjustment
- this command is the preferred place for
  `10Y real yield + DXY + liquidity + financial conditions` style top-down
  judgment

Local helper:

- `financial-analysis\skills\macro-health-overlay\scripts\run_macro_health_overlay.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>] [--request-output <resolved-request.json>]`

Canonical template:

- `financial-analysis\skills\macro-health-overlay\examples\macro-health-overlay-request.template.json`
