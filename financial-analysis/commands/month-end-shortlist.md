---
description: Run the A-share `月底短线` shortlist workflow
argument-hint: "[request-json]"
---

# Month-End Shortlist

Use this command when you want a broad A-share shortlist for a short horizon,
especially when the task is:

- `月底短线`
- `筛一批月底最有希望涨的`
- `按 Minervini / Kell strict 过滤`

What it does:

1. builds a broad candidate pool
2. enforces exchange-scope rules
3. applies `themes -> driver fit / business transmission` as a real filter
4. can accept an optional `macro_health_overlay`
   so the workflow can frame risk posture from real yields, DXY, liquidity,
   financial conditions, and growth / inflation regime before it ranks sectors
5. can accept an optional `market_regime_overlay` plus `sector_views`
   so the workflow can judge sectors first and core leaders second
6. can also accept optional `x_style_overlays` exported from
   `x-stock-picker-style`, so learned X-user selection styles influence ranking
   without overriding hard filters
7. runs trend-template, RS, and VCP-like checks
8. enforces a minimum `risk/reward` check before a name can stay in the kept set
9. uses structured catalysts from public pages as hard filters
10. produces shortlist scorecard + top picks + trade cards + recent validation
11. renders the final top picks as fuller analysis cards with:
   - executive summary
   - scenario price table
   - trading strategy table
   - score breakdown
   - strengths / risks / invalidation

Notes:

- top-pick selection now has three tiers:
  - `strict`
  - `near_strict`
  - `weak_fallback`
- when the strict gate is empty, the workflow will prefer `near_strict`
  candidates before dropping to `weak_fallback`
- small-universe RS percentile is smoothed to avoid the old `0 / 50 / 100`
  cliff on 3-5 names
- for larger broad scans, you can set `working_set_limit` to prefilter by
  turnover before pulling full history, which reduces Eastmoney history misses
- if `universe_limit >= 60` and `working_set_limit = 0`, the runtime will
  auto-apply a bounded working set on Eastmoney-backed broad scans
- if you need to inspect named stocks inside a broad scan, add
  `focus_tickers` so they stay in scope and show up in `Focus Diagnostics`
- if a name has valid trend / RS / recent structured-event support but still
  fails strict scoring, try `filter_profile = month_end_event_support_transition`
- if you already have a PB / prime-book style flow read, attach it via
  `market_regime_overlay` and `sector_views` instead of burying it inside free
  text
- if you already have a macro-health read, attach it via
  `macro_health_overlay`; this is the preferred place for
  `10Y real yield + DXY + breakeven + liquidity + term premium` style views
- leave `macro_health_overlay.integration_mode = advisory_only` by default
- switch to `score_light` only when you explicitly want a very small macro
  posture adjustment to ranking
- if you already ran `x-stock-picker-style`, attach its `overlay_pack` output
  via `x_style_overlays`; it is advisory-only and should shape ranking and
  commentary rather than hard pass/fail
- if you have a full `x-stock-picker-style` batch result instead of copied
  overlay packs, attach it via `x_style_batch_result_path` plus optional
  `x_style_selected_handles`
- other useful profiles:
  - `repair_rebound`
  - `earnings_catalyst_strict`
- `VCP` is a ranking signal, not a hard gate
- `structured catalyst` is the only hard catalyst pass/fail layer in v1
- the default `min_risk_reward_ratio` is `1.5`
- when `themes` are active, a stronger business / transmission match also adds
  a bounded score bonus instead of only acting as pass/fail

Local helper:

- `financial-analysis\skills\month-end-shortlist\scripts\run_month_end_shortlist.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Canonical template:

- `financial-analysis\skills\month-end-shortlist\examples\month-end-shortlist-request.template.json`
- `financial-analysis\skills\month-end-shortlist\examples\month-end-shortlist-x-style-assisted.template.json`

Base-template note:

- `month-end-shortlist-request.template.json` is now the clean base request
- prefer `macro-health-assisted-shortlist` when you want macro-health attached
  by default

Companion entrypoint:

- `financial-analysis\commands\x-style-assisted-shortlist.md`
- `financial-analysis\commands\macro-health-assisted-shortlist.md`
