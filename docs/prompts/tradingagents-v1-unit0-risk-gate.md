# Codex Prompt - Unit 0: Risk Gate and Operator Boundary

## Goal

Before writing any bridge code, freeze the v1 adoption boundary in durable
runtime docs.

## Files to Create

- `docs/runtime/tradingagents-risk-register.md`
- `docs/runtime/tradingagents-adoption-boundary.md`
- `docs/runtime/tradingagents-pilot-matrix.md`
- `docs/runtime/tradingagents-operator-setup.md`

## Inputs

- `docs/plans/2026-04-05-002-feat-tradingagents-decision-bridge-plan.md`
- verified repo facts for `TauricResearch/TradingAgents`

## Required Content

- risk table with severity, mitigation, and go/no-go implication
- explicit v1 allowed vs forbidden boundary
- local-market pilot matrix with U.S. controls plus A-share / HK rows
- operator setup that keeps the dependency optional and explicitly pinned

## Constraints

- docs only
- do not install `TradingAgents`
- do not edit workflow code in this unit

## Acceptance Criteria

- the evidence boundary is explicit
- cost and latency are treated as first-class risks
- local-market pilot success is required before stock-watch integration
- operator setup does not imply repo-wide mandatory installation
