---
description: Adaptively run Longbridge analysis, trading-plan, review, and portfolio workflows
argument-hint: "[longbridge-adaptive-request-json]"
---

# Longbridge Adaptive

Use this command when the user asks for stock analysis, trading-plan generation,
plan review, or portfolio/account inspection and the exact Longbridge data
layers should be selected automatically.

Runtime helper:

- `financial-analysis/skills/longbridge/scripts/longbridge_adaptive_runner_runtime.py`
- callable: `run_longbridge_adaptive_task(request, *, runner, env=None)`

Default routing:

1. Infer `task_type` from `task_type` or the prompt:
   - `stock_analysis`: quote/kline screen plus requested catalyst, valuation,
     financial-event, ownership-risk, intraday, theme, governance, account,
     derivative, HK microstructure, preflight, or quant layers.
   - `trading_plan`: screen first, then build the standardized
     `longbridge-trading-plan` artifact. If `session_type` is `intraday`, run
     `longbridge-intraday-monitor` against the generated trigger/stop levels.
   - `review`: use a supplied `plan_report` or `screen_result`; if no actuals
     are supplied, fetch read-only `quote` actuals and build a post-close
     review.
   - `portfolio_review`: run only `portfolio`, `assets`, and `positions`.
2. Wrap all Longbridge CLI calls in the local safety runner.
3. Return a single JSON envelope with `workflow_steps`, `outputs`,
   `should_apply: false`, and `side_effects: "none"`.
   - Screen-native evidence such as `account_state`, `account_health`, and
     `quant_analysis` is also promoted from `outputs.screen_result` to stable
     top-level `outputs` keys when those layers are selected.
   - Read-only `subscriptions` and `sharelist` evidence is exposed as
     `outputs.subscription_sharelist_state` when the prompt asks for active
     real-time subscriptions, community lists, or popular sharelists.

Prompt-to-layer hints:

- `news`, `catalyst`, `topic`: catalyst layer.
- `valuation`, `rating`, `EPS`, `consensus`: valuation layer.
- `filing`, `earnings`, `financial report`, `dividend`: financial-event layer.
- `insider`, `investors`, `institutional`, `short interest`: ownership-risk
  layer.
- `capital flow`, `market-temp`, `intraday`, `资金面`, `盘中`: intraday layer.
- `portfolio`, `assets`, `positions`, `组合`, `资产`, `持仓`: portfolio layer or
  portfolio-review task.
- `account review`, `order history`, `executions`, `cash-flow`,
  `profit-analysis`, `statement list`, `订单历史`, `成交`, `现金流`,
  `收益分析`, `日结单`: account-review-plus layer for review or
  portfolio-review tasks.
- `theme`, `sector`, `constituent`, `shareholder`, `fund-holder`: theme-chain
  layer.
- `executive`, `invest-relation`, `governance`, `board`, `control`, `fund exposure`,
  `治理结构`, `高管`, `投资者关系`, `控股结构`, `基金暴露`:
  governance-structure layer.
- `execution preflight`, `preflight`, `static`, `calc-index`, `market-status`,
  `trading session`, `trading days`, `overnight eligibility`, `可执行性`,
  `隔夜资格`, `市场状态`, `交易日`: execution-preflight layer for trading plans.
- `option`, `options`, `iv`, `oi`, `call`, `put`, `warrant`, `期权`, `窝轮`:
  derivative-event-risk layer.
- `brokers`, `broker-holding`, `ah-premium`, `participants`, `港股`, `AH`:
  HK-microstructure layer.
- `quant`, `RSI`, `MACD`, `technical indicator`: quant layer.
- `subscriptions`, `WebSocket subscriptions`, `sharelist`, `popular sharelist`,
  `community stock list`, `实时订阅`, `共享列表`, `社区股票列表`: subscription-sharelist
  layer.

Example local runs:

```powershell
py financial-analysis\skills\longbridge\scripts\longbridge_adaptive_runner_runtime.py `
  financial-analysis\skills\longbridge\examples\longbridge-adaptive-request.template.json `
  --output .tmp\longbridge-adaptive\result.json `
  --markdown-output .tmp\longbridge-adaptive\report.md
```

Minimal request:

```json
{
  "prompt": "[$longbridge] 查 NVDA.US 最新价、新闻催化、filing、insider、investors 和资金面，给交易计划，不要下单",
  "tickers": ["NVDA.US"],
  "analysis_date": "2026-05-06"
}
```

Explicit request:

```json
{
  "task_type": "trading_plan",
  "tickers": ["NVDA.US", "AAPL.US"],
  "analysis_date": "2026-05-06",
  "analysis_layers": ["catalyst", "valuation", "financial_event", "ownership_risk", "execution_preflight"],
  "session_type": "premarket",
  "content_count": 3
}
```

Side-effect boundary:

- The adaptive runner never submits orders, runs DCA, exports statements to
  files, mutates watchlists, mutates alerts, or mutates sharelists.
- `order buy/sell/cancel/replace`, `dca`, and `statement export` are blocked by
  `build_safe_longbridge_runner()` before the CLI call is made.
- Watchlist/sharelist mutation commands such as `watchlist pin` and
  `sharelist sort` are also blocked by the safety runner.
- `portfolio`, `assets`, `positions`, `statement list`, and other read-only
  diagnostics may be used only when the inferred task asks for them.
- `account_review_plus`, `execution_preflight`, `derivative_event_risk`,
  `hk_microstructure`, `governance_structure`, and `subscription_sharelist`
  remain read-only evidence layers only.
- Any future real account write must still go through `longbridge-action-gateway`
  and the explicit confirmation gate documented there.
