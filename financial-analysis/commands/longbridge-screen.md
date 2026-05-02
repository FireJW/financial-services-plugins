---
description: Screen a supplied watchlist with Longbridge market data and rank the strongest setups
argument-hint: "[longbridge-screen-request-json]"
---

# Longbridge Screen

Use this command when you already have a watchlist, basket, board shortlist, or
theme candidate set and want Longbridge to rank it as a screening-analysis
tool, not just as a raw data source.

Default flow:

1. read `financial-analysis/skills/longbridge/SKILL.md`
2. fetch `quote` and recent daily `kline` data for each supplied ticker
3. fetch optional analysis evidence through Longbridge:
   - catalyst layer: `news`, `topic`, `filing`
   - valuation layer: `valuation`, `institution-rating`, `forecast-eps`,
     `consensus`
   - watchlist/alert layer: `watchlist`, `alert`
   - portfolio layer: `portfolio`, `positions`, `assets`, `cash-flow`,
     `profit-analysis`
   - intraday confirmation layer: `capital`, `depth`, `trades`,
     `trade-stats`, `anomaly`, `market-temp`
   - theme-chain layer: `company`, `industry-valuation`, `constituent`,
     `shareholder`, `fund-holder`, `corp-action`
   - account-health layer: `statement list`, `fund-positions`,
     `exchange-rate`, `margin-ratio`, `max-qty`
   - financial-event layer: `financial-report`, `finance-calendar report`,
     `dividend`, `dividend detail`, `operating`, `news detail`,
     `filing detail`
   - ownership-risk layer: `insider-trades`, `short-positions`, `investors`
   - quant layer: `quant run`
4. score trend, short-term momentum, volume participation, breakout status,
   catalyst support, and valuation/expectation support
5. output a ranked list with:
   - `technical_score`
   - `catalyst_score`
   - `valuation_score`
   - `screen_score`
   - `workbench_score` when intraday/theme-chain layers are enabled
   - `signal`
   - `trigger_price`
   - `stop_loss`
   - `abandon_below`
   - `longbridge_analysis.data_coverage`
   - `ownership_risk_analysis` when requested
   - `quant_analysis` when requested
   - per-candidate `qualitative_evaluation`:
     `catalyst_summary`, `financial_report_summary`, `cashflow_quality`,
     `valuation_assessment`, `rating_target_price_assessment`,
     `filing_event_summary`, `research_or_topic_quality`, `key_risks`, and
     `qualitative_verdict`
   - top-level `missed_attention_priorities` / `key_omissions` for follow-up
     issues such as profit/cash-flow divergence, valuation/target-price
     conflict, filing clarification risk, non-trading-day P1 refresh needs,
     and unparsed news/filing details
   - top-level read-only `dry_run_action_plan` with suggested watchlist and
     alert operations, always `should_apply: false` and `side_effects: "none"`
   - watchlist bucket and alert suggestions
   - read-only `account_state`, `portfolio_inspection`, `account_health`,
   `intraday_confirmation`, `theme_chain_analysis`, and per-candidate
   `financial_event_analysis` evidence when requested
6. keep the existing Eastmoney or Tushare path only as fallback for deeper
   history if Longbridge bars are constrained

Local helper:

- `financial-analysis\skills\longbridge\scripts\run_longbridge_screen.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Canonical template:

- `financial-analysis\skills\longbridge\examples\longbridge-screen-request.template.json`

Request options:

- `analysis_layers`: defaults to `["catalyst", "valuation"]`; use
  `["technical"]` or `"none"` for technical-only screening. Use `["all"]`
  to include catalyst, valuation, watchlist/alert, portfolio, intraday,
  theme-chain, account-health, financial-event, ownership-risk, and quant
  evidence.
- `analysis_layers=["financial_event"]`: fetches read-only financial reports,
  finance-calendar events, dividends, operating metrics, news detail, and
  filing detail. Aliases include `financial`, `report`, `event`, `earnings`,
  `calendar`, `dividend`, and `operating`; legacy `event_depth` remains
  accepted for older callers.
- `include_analysis`: set to `false` to skip optional Longbridge analysis
  calls.
- `content_count`: max articles/topics/filings per symbol, capped at `10`.
- `trade_count`: max recent trades sampled by the intraday layer, capped at
  `1000`.
- `statement_type`: account-health statement type, defaults to `daily`.
- `statement_limit`: max account-health statement records, capped at `30`.
- `account_health_symbol_limit`: max ranked symbols checked through
  `margin-ratio` and `max-qty`, capped at `10`.
- `theme_indexes`: optional index symbols used by the theme-chain layer to
  verify constituent membership.
- `analysis_layers=["ownership_risk"]`: fetches read-only US-only
  `insider-trades` and `short-positions` per US symbol, plus optional
  `investors` ranking and CIK holdings when `investor_ciks` is supplied.
- `investor_ciks`: optional SEC CIK list for institutional holdings lookups.
- `investor_top`: max investor ranking/holding rows, capped by the runtime.
- `analysis_layers=["quant"]`: runs Longbridge `quant run` scripts over the
  screen symbols. Use `quant_start`, `quant_end`, and `quant_period` to
  override the default screen date window, and `quant_scripts` or `indicators`
  to supply custom PineScript-compatible scripts.

Side-effect boundary:

- This command does not create Longbridge watchlists or alerts.
- It only emits `tracking_plan.suggested_watchlist_bucket` and
  `tracking_plan.alert_suggestions`, so the user can decide when to write
  account-side watchlist/alert objects.
- Account-aware layers emit `should_apply: false` and `side_effects: "none"`.
  They may suggest adding/enabling/disabling watchlist or alert objects, but
  never mutate the account.
- `qualitative_evaluation`, `missed_attention_priorities`, and
  `dry_run_action_plan` are report artifacts only. They do not create
  watchlists, alerts, orders, or DCA plans.
- Account-health and financial-event layers also emit `should_apply: false` and
  `side_effects: "none"`. They call read-only Longbridge commands only; the
  statement layer uses `statement list` and does not run `statement export`
  with an output path.
- Ownership-risk and quant layers emit `should_apply: false` and
  `side_effects: "none"`. Ownership-risk skips US-only endpoints for non-US
  symbols and records the gap under `unavailable`.
- For plan monitoring after a candidate has concrete trigger, stop, or abandon
  levels, use `financial-analysis/commands/longbridge-intraday-monitor.md`.
  `longbridge-screen` keeps only its lightweight intraday confirmation layer.
- For account-side watchlist or alert changes, pass the screen JSON result to
  `financial-analysis/commands/longbridge-action-gateway.md` as
  `screen_result` or `longbridge_screen_result`. The gateway uses the shared
  `longbridge_action_plan_bridge.py` converter to produce audited dry-run
  action plans.
- If optional Longbridge analysis endpoints are unavailable under the current
  account, the candidate remains in the technical screen and the blocked
  commands are recorded under `longbridge_analysis.unavailable`.

Use this command when the real question is:

- `把这组票按强弱排序`
- `从我的观察池里筛出最适合做突破的标的`
- `结合最新行情给我二次筛选，而不是只看原始报价`
