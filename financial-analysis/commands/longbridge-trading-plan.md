---
description: Build standardized Longbridge trading-plan and post-close review artifacts
argument-hint: "[longbridge trading plan input json]"
---

# Longbridge Trading Plan

Use this command when a Longbridge watchlist screen needs to become a reusable
premarket, intraday, or post-close handoff artifact.

Runtime helper:

- `financial-analysis/skills/longbridge/scripts/longbridge_trading_plan_runtime.py`

Default flow:

1. Run or read `longbridge-screen`.
2. Use `trading_plan_report` embedded in the screen result, or build it from a
   screen result JSON with this helper.
3. During the session, run `longbridge-intraday-monitor` and rebuild the plan
   with `--session-type intraday --intraday-result <result.json>`.
4. After close, pass actual price data to `--session-type postclose --actuals
   <actuals.json>` to classify each candidate against trigger, stop, and
   abandon levels.

Standard plan schema fields:

- `plan_date`
- `session_type`: `premarket`, `intraday`, or `postclose`
- `market_context`
- `candidates`
- `trigger_plan`
- `invalidation_plan`
- `position_sizing_guidance`
- `qualitative_evidence`
- `risk_flags`
- `missed_attention_priorities`
- `dry_run_action_plan`
- `review_checklist`

Post-close review marks each candidate with:

- `hit_trigger`
- `failed_trigger`
- `stopped`
- `still_valid`
- `invalidated`
- `next_session_adjustment`

Example local runs:

```powershell
py financial-analysis\skills\longbridge\scripts\longbridge_trading_plan_runtime.py `
  --screen-result .tmp\longbridge-watchlist-2026-05-02\result.longbridge-screen.qualitative.json `
  --session-type premarket `
  --output .tmp\longbridge-watchlist-2026-05-02\result.trading-plan.json `
  --markdown-output .tmp\longbridge-watchlist-2026-05-02\report.trading-plan.md
```

```powershell
py financial-analysis\skills\longbridge\scripts\longbridge_trading_plan_runtime.py `
  --plan-json .tmp\longbridge-watchlist-2026-05-02\result.trading-plan.json `
  --session-type postclose `
  --actuals .tmp\longbridge-watchlist-2026-05-02\actuals.postclose.json `
  --output .tmp\longbridge-watchlist-2026-05-02\result.trading-plan.postclose-review.json `
  --markdown-output .tmp\longbridge-watchlist-2026-05-02\report.trading-plan.postclose-review.md
```

Side-effect boundary:

- This helper is a pure artifact builder.
- It never calls watchlist mutation, alert mutation, order, or DCA commands.
- All emitted action plans force `should_apply: false` and
  `side_effects: "none"`.
- Any real account write must go through `longbridge-action-gateway`, exact
  confirmation text, and the explicit environment gate documented there.
