---
description: Build audited dry-run action plans for Longbridge account-side operations
argument-hint: "[longbridge-action-request-json]"
---

# Longbridge Action Gateway

Use this command when Longbridge account-side actions need a local audit plan
before any write-capable CLI command is allowed.

Runtime helper:

- `financial-analysis\skills\longbridge\scripts\longbridge_action_gateway_runtime.py`
- Screen-to-action bridge:
  `financial-analysis\skills\longbridge\scripts\longbridge_action_plan_bridge.py`

Default contract:

1. Build `action_plans` only. Default execution is dry-run.
2. Every action plan includes:
   - `operation`
   - `command_preview`
   - `symbol`
   - `account_target`
   - `risk_level`
   - `required_confirmation`
   - `confirmation_text`
   - `should_apply: false`
   - `side_effects: "none"`
3. The apply gate must pass all of:
   - `request.apply == true`
   - `request.confirmation_text` exactly matches the generated
     `action_plan.confirmation_text`
   - environment variable `LONGBRIDGE_ALLOW_WRITE == "1"`
4. Order write operations and DCA operations are hard-blocked even if the apply
   gate is otherwise satisfied. They are planner-only until a separate review.
5. Statement export output paths must stay under
   `.tmp/longbridge-statements/` inside this repo.
6. The apply allowlist is limited to `watchlist.*`, `alert.*`, and
   `statement.export`. Read-only plans use the separate `execute_read_only`
   path instead of the write apply gate.

Supported plan types:

- `watchlist.create`
- `watchlist.delete`
- `watchlist.add_stocks`
- `watchlist.remove_stocks`
- `alert.add`
- `alert.delete`
- `alert.enable`
- `alert.disable`
- `order.list`, `order.detail`, `order.executions` as read-only plans
- `order.buy`, `order.sell`, `order.cancel`, `order.replace` as hard-blocked
  dry-run plans
- `dca.*` as hard-blocked dry-run plans
- `statement.list` as read-only
- `statement.export` as a gated export plan with repo-local output validation

Example request:

```json
{
  "actions": [
    {
      "type": "watchlist",
      "operation": "add_stocks",
      "group": "breakout_with_catalyst",
      "symbols": ["600111.SH"]
    },
    {
      "type": "alert",
      "operation": "add",
      "symbol": "600111.SH",
      "price": 53.46,
      "direction": "rise"
    }
  ]
}
```

Example local run:

```powershell
py financial-analysis\skills\longbridge\scripts\longbridge_action_gateway_runtime.py .tmp\longbridge-action-request.json --output .tmp\longbridge-action-plan.json
```

Relationship to `longbridge-screen`:

- `longbridge-screen` remains read-only.
- `longbridge-screen` is the main analysis entrypoint for ranking candidates
  and emitting watchlist/alert suggestions.
- This gateway may consume a screen result through `screen_result` or
  `longbridge_screen_result` and convert
  `tracking_plan.alert_action_suggestions` and
  `tracking_plan.watchlist_action_suggestions` into audited action plans.
- The conversion is isolated in `longbridge_action_plan_bridge.py`, so screen
  output rules and gateway action-planning rules stay testable without giving
  `longbridge-screen` any write capability.
- The generated action plans still default to dry-run and keep
  `side_effects: "none"`.
