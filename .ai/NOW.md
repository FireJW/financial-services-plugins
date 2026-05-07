# Current Longbridge Handoff

Scope: `feat/longbridge-trading-plan-artifacts`

PR: https://github.com/FireJW/financial-services-plugins/pull/30

Fixed priority order:

1. Keep the feature branch synced with `origin/main`.
2. Run the full Longbridge regression suite after every sync or conflict fix.
3. Push the branch and create or update the PR.
4. After PR integration is stable, run P1 live validation with read-only Longbridge data.
5. During the next open CN session, validate `longbridge-intraday-monitor`.
6. After close, validate `longbridge-trading-plan --session-type postclose` with real actuals.
7. Run `longbridge-action-gateway` only as dry-run action-plan generation.

Current guardrails:

- Do not execute real orders, DCA, statement export writes, watchlist writes, alert writes, or sharelist writes.
- Keep all account-side outputs at `should_apply=false` and `side_effects=none`.
- Use exact watchlist symbols for the live drill: `002565.SZ`, `000969.SZ`, `000988.SZ`.
- If another session takes over, start by checking `git status --short --branch`, PR status, and the latest Longbridge regression result.

Last known next step:

- Check PR #30 status and resolve any review/check failures first.
- If PR #30 is clean, start the read-only P1 live validation run.
