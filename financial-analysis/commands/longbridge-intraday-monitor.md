---
description: Monitor intraday Longbridge data against plan trigger and invalidation levels
argument-hint: "[longbridge-intraday-monitor-request-json]"
---

# Longbridge Intraday Monitor

Use this command when a trading plan already exists and the user wants a
read-only intraday check of whether a symbol has triggered, invalidated, or
remains active.

Runtime:

- `financial-analysis/skills/longbridge/scripts/longbridge_intraday_monitor_runtime.py`
- callable: `run_longbridge_intraday_monitor(request, *, runner, env=None)`

Request shape:

- `tickers`: symbols in Longbridge format, such as `700.HK` or `TSLA.US`
- `analysis_date`: `YYYY-MM-DD`; passed to intraday as `--date YYYYMMDD`
- `market`: `HK`, `US`, `CN`, or `SG`
- `session`: `intraday` or `all`
- `anomaly_count`: max anomaly rows per symbol
- `plan_levels`: per-symbol levels:
  `trigger_price`, `stop_loss`, `abandon_below`

Read-only Longbridge commands used:

- `market-status --format json`
- `trading session --format json`
- `trading days MARKET --start YYYY-MM-DD --end YYYY-MM-DD --format json`
- `intraday SYMBOL --session intraday|all --date YYYYMMDD --format json`
- `capital SYMBOL --flow --format json`
- `anomaly --market MARKET --symbol SYMBOL --count N --format json`
- `trade-stats SYMBOL --format json`

Output:

- top-level `intraday_monitor`, `market_status`, `trading_session`,
  `trading_days`, `monitored_symbols`, `risk_flags`, `data_coverage`, and
  `unavailable`
- per-symbol normalized `intraday`, `capital_flow`, `abnormal_volume`,
  `trade_stats`, and `plan_status`
- `plan_status.state`: `triggered`, `invalidated`, `active`, or `blocked`
- `should_apply: false` and `side_effects: "none"`

Side-effect boundary:

- This command never calls order, submit, replace, cancel, watchlist mutation,
  or alert mutation endpoints.
- Endpoint failures are recorded under `unavailable` and do not block other
  read-only data from being collected.
