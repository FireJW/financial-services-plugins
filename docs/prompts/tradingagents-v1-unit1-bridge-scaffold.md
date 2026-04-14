# Codex Prompt - Unit 1: Standalone Bridge Scaffold

## Goal

Build a fixture-driven standalone TradingAgents decision bridge that works even
when the upstream package is not installed.

## Pre-condition

- Unit 0 docs are complete

## Files to Create

- `financial-analysis/commands/tradingagents-decision-bridge.md`
- `financial-analysis/skills/tradingagents-decision-bridge/SKILL.md`
- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_decision_bridge_runtime.py`
- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_decision_contract.py`
- `financial-analysis/skills/tradingagents-decision-bridge/scripts/tradingagents_decision_bridge.py`
- `financial-analysis/skills/tradingagents-decision-bridge/scripts/run_tradingagents_decision_bridge.cmd`
- `financial-analysis/skills/tradingagents-decision-bridge/examples/tradingagents-decision-bridge-request.template.json`
- `tests/test_tradingagents_decision_bridge_runtime.py`
- `tests/fixtures/tradingagents-decision-bridge/basic-success.json`
- `tests/fixtures/tradingagents-decision-bridge/partial-output.json`
- `tests/fixtures/tradingagents-decision-bridge/invalid-output.json`

## Required Behavior

- bounded `decision_memo` contract
- `layer: decision_advisory`
- lazy upstream import
- disabled mode returns `skipped`
- missing package returns bounded warning, not crash
- fixture mode produces testable outputs without live installs

## Constraints

- do not vendor upstream `TradingAgents`
- do not change `scripts/stock_watch_workflow.py` yet
- do not merge bridge output into evidence contracts

## Acceptance Criteria

- fixture tests pass without upstream install
- CLI entrypoint works
- the runtime produces advisory-only markdown and JSON outputs
