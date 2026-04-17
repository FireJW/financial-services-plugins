# Codex Prompt - Unit 2: Ticker Normalization Layer

## Goal

Implement or verify the bridge-owned ticker normalization layer for U.S.,
A-share, and HK symbols without relying on upstream `TradingAgents`
`strip().upper()` behavior.

If you are resuming from the current branch state, prefer verifying and
tightening the existing implementation instead of creating duplicate files.

## Pre-condition

- Unit 1 standalone bridge scaffold is complete
- fixture tests already pass without a live upstream install

## Files to Create or Modify

- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_ticker_normalization.py`
- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_decision_bridge_runtime.py`
- `tests/test_tradingagents_decision_bridge_runtime.py`
- `tests/fixtures/tradingagents-decision-bridge/local-market-cases.json`

## Required Behavior

- `601600` -> `601600.SS`
- `002837` -> `002837.SZ`
- `300750` -> `300750.SZ`
- `601600.SS` stays unchanged
- `700.HK` -> `00700.HK`
- `00700.HK` stays unchanged
- `nvda` -> `NVDA`
- `BRK.B` stays unchanged
- blank input raises a bounded validation error
- malformed or unsupported symbols do not crash the bridge runtime

## Integration Rules

- the bridge must preserve all three identifiers:
  - `requested_ticker`
  - `normalized_ticker`
  - `upstream_ticker`
- local-market handling must be owned by our bridge layer
- upstream normalization behavior must not be trusted for A-share or HK rows
- fixture tests must still run without `TradingAgents` installed

## Acceptance Criteria

- U.S., A-share, and HK normalization coverage is present in tests or fixture cases
- the runtime records requested vs normalized vs upstream ticker values
- normalization works the same in disabled, fixture, and live-ready code paths
- no new dependency on a live `TradingAgents` install is introduced

## Constraints

- do not vendor or patch upstream `TradingAgents`
- do not start `stock_watch_workflow.py` integration in this unit
- keep the change set inside the bridge runtime, tests, and fixtures
