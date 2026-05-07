---
description: Use Longbridge CLI/Skill for live market data, portfolio data, and stock analysis
argument-hint: "[stock or market question]"
---

# Longbridge

Use this command when the task needs live stock, market, portfolio, watchlist,
or trading-account data.

Native route:

1. Read `financial-analysis/skills/longbridge/SKILL.md`.
2. Prefer the Longbridge CLI for live data:
   - `longbridge quote <SYMBOL> --format json`
   - `longbridge intraday <SYMBOL> --format json`
   - `longbridge news <SYMBOL> --format json`
   - `longbridge portfolio --format json`
   - `longbridge positions --format json`
   - `longbridge assets --format json`
   - `longbridge statement list --type daily --limit N --format json`
   - `longbridge fund-positions --format json`
   - `longbridge exchange-rate --format json`
   - `longbridge margin-ratio <SYMBOL> --format json`
   - `longbridge max-qty <SYMBOL> --side buy --price PRICE --format json`
   - `longbridge kline <SYMBOL> --period day --count N --format json`
   - `longbridge financial-report <SYMBOL> --kind ALL --format json`
   - `longbridge finance-calendar report --symbol <SYMBOL> --count N --format json`
   - `longbridge dividend <SYMBOL> --format json`
   - `longbridge dividend detail <SYMBOL> --format json`
   - `longbridge operating <SYMBOL> --format json`
   - `longbridge news detail <ID> --format json`
   - `longbridge filing detail <SYMBOL> <ID> --format json`
   - `longbridge insider-trades <SYMBOL.US> --count N --format json`
   - `longbridge short-positions <SYMBOL.US> --count N --format json`
   - `longbridge investors --top N --format json`
   - `longbridge investors <CIK> --top N --format json`
   - `longbridge quant run <SYMBOL> --period day --start YYYY-MM-DD --end YYYY-MM-DD --script SCRIPT --format json`
   - `longbridge market-status --format json`
   - `longbridge trading session --format json`
   - `longbridge trading days MARKET --start YYYY-MM-DD --end YYYY-MM-DD --format json`
3. Use `tradingagents-decision-bridge` with `analysis_profile =
   longbridge_market` when the task should feed Longbridge market data into the
   local TradingAgents path.
4. Use `month-end-shortlist` normally; its local market snapshot layer can now
   accept `longbridge_market` when Longbridge is authenticated.
5. Use `financial-analysis/commands/longbridge-screen.md` when Longbridge
   should rank a supplied watchlist as a screening-analysis tool. That screen
   combines market action with optional Longbridge catalyst evidence
   (`news`, `topic`, `filing`) and valuation/expectation evidence
   (`valuation`, `institution-rating`, `forecast-eps`, `consensus`), plus
   optional ownership-risk and quant-indicator layers.
6. Use `financial-analysis/commands/longbridge-intraday-monitor.md` when the
   user already has plan trigger/stop levels and needs a read-only intraday
   status check against market status, trading day, capital flow, anomaly, and
   trade-stat evidence.
7. Use `financial-analysis/commands/longbridge-trading-plan.md` when a
   Longbridge screen result should become a standardized Markdown/JSON
   premarket, intraday, or post-close handoff artifact.

Compatibility notes:

- Symbol format is Longbridge-native `<CODE>.<MARKET>`:
  `AAPL.US`, `NVDA.US`, `00700.HK`, `600519.SH`, `002837.SZ`.
- Bare US tickers may be normalized to `.US` by local helper code.
- If `longbridge kline history` is blocked in this account/CLI combination,
  preserve Longbridge `quote` / `intraday` evidence and use the existing
  Eastmoney or Tushare historical-bars path for longer technical history.
- `longbridge-screen` does not mutate account-side watchlists or alerts. It
  emits suggested watchlist buckets and price-alert levels only.
- `longbridge-screen` `analysis_layers=["all"]` may also include read-only
  account, portfolio, intraday, theme-chain, account-health, and financial-event
  evidence; those layers still emit suggestions or diagnostics only and keep
  `side_effects: "none"`.
- `longbridge-screen` `analysis_layers=["financial_event"]` emits structured
  per-candidate `financial_event_analysis` JSON for article generation,
  earnings scans, and second-pass stock screening.
- `longbridge-screen` `analysis_layers=["ownership_risk"]` emits read-only US
  insider-trade, institutional-investor, and short-position risk diagnostics.
- `longbridge-screen` `analysis_layers=["quant"]` emits read-only Longbridge
  `quant run` indicator alignment diagnostics.
- `longbridge-intraday-monitor` remains an independent plan-monitoring command
  rather than a broad screen layer; use it after a plan already has trigger,
  stop, or abandon levels.
- `longbridge-trading-plan` is a pure artifact builder around screen,
  intraday-monitor, and post-close actuals. It forces `should_apply: false`
  and `side_effects: "none"`.
- `longbridge-action-gateway` remains the account-side action gate. Feed it a
  `longbridge-screen` result when watchlist or alert suggestions should become
  audited dry-run action plans.
- Do not use Longbridge trading commands unless the user explicitly asks for a
  trade operation and confirms the order details.

Verification:

- Check CLI auth with `longbridge auth status --format json`.
- Check connectivity with `longbridge check --format json`.
- For a quick smoke test, run `longbridge quote AAPL.US --format json`.
- In Codex on Windows, do not conclude Longbridge is unauthenticated from a
  sandboxed `Not authenticated` result alone. Unapproved commands may resolve
  the token path under `C:\Users\CodexSandboxOffline\.longbridge` instead of
  the user's real `C:\Users\rickylu\.longbridge` directory. If `auth status` or
  `check` is inconsistent with `quote`, rerun the required Longbridge command
  with approved/escalated execution in the real user environment before falling
  back to non-Longbridge sources or reporting an auth blocker.
