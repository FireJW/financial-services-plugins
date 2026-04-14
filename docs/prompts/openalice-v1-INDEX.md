# Codex Prompt — OpenAlice Integration INDEX

Execution order is strict:

1. `openalice-v1-unit0-risk-gate.md`
2. `openalice-v1-unit1-contract-setup.md`
3. `openalice-v1-unit2-http-bridge.md`
4. `openalice-v1-unit3-stock-watch-pilot.md`
5. `openalice-v1-unit4-post-pilot-docs.md`

## Hard Rules

- Treat `TraderAlice/OpenAlice` as an **external optional dependency** only.
- Do **not** vendor OpenAlice into this repo.
- Do **not** add `@traderalice/opentypebb` or any OpenAlice package as a dependency in this repo.
- Do **not** implement or enable `MCP Ask`, trading, broker, UTA, Telegram, Web UI, or brain/session features.
- Do **not** merge sidecar output into `claim_ledger`, `source_observation`, or other evidence contracts.
- Default behavior of existing workflows must remain unchanged when OpenAlice is absent.
- Prefer fixture-driven tests; live sidecar access must remain optional.

## Primary objective

Use only the OpenTypeBB-compatible HTTP surface as a bounded source of `market_context` for stock analysis, starting with `scripts/stock_watch_workflow.py` only.
