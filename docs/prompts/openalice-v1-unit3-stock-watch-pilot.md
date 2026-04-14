# Codex Prompt — Unit 3: Stock Watch Pilot Only

## Goal

Integrate optional `market_context` enrichment into `scripts/stock_watch_workflow.py` without changing default behavior.

## Files to modify

- `scripts/stock_watch_workflow.py`
- `tests/test_stock_watch_workflow.py`

## Inputs

- `docs/runtime/openalice-market-context-contract.md`
- `financial-analysis/skills/openalice-market-data/scripts/openalice_market_data_runtime.py`
- `tests/test_openalice_market_data_runtime.py`

## Requirements

### Behavior
- Add opt-in sidecar usage only.
- When no sidecar config/request is present, behavior must remain unchanged.
- When enabled, retrieve bounded `market_context` for watchlist symbols and benchmark context.
- Add a clearly labeled auxiliary section in outputs for market context.
- Do not promote sidecar data into verified evidence claims.
- If sidecar retrieval fails, continue the base workflow and surface a bounded warning.

### Good uses of `market_context`
- quote snapshot context
- benchmark-relative context
- short history summary
- lightweight indicators if already supported by the bridge

### Bad uses
- replacing primary evidence analysis
- inventing unsupported precision
- making the base workflow depend on sidecar success

### Tests
Cover at least:
- legacy path unchanged with no config
- opt-in path includes `market_context`
- sidecar failure degrades cleanly
- partial coverage is labeled as partial
- benchmark context is attached only when available

## Constraints

- Only touch `stock_watch_workflow.py` and its tests in this unit.
- Do not modify general router logic.
- Do not modify `screen`, `model-update`, `morning-note`, or `macro-note-workflow` here.

## Acceptance criteria

- Default stock-watch behavior is preserved.
- Sidecar enrichment is clearly optional.
- Output labels sidecar content as auxiliary market context, not core evidence.
