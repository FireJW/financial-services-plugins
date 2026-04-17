# Codex Prompt - Unit 4: Post-Pilot Capability Map and Expansion Guide

## Gate

Do not execute this unit until a real live pilot has been run and recorded.

The docs in this unit must describe actual observed outcomes, not predictions.

## Goal

Document what the live TradingAgents pilot really proved, what remains bounded
or weak, and whether expansion beyond standalone bridge mode is justified.

## Files to Create

- `docs/runtime/tradingagents-capability-map.md`
- `docs/runtime/tradingagents-expansion-guide.md`

## Files to Update

- `docs/runtime/tradingagents-adoption-boundary.md`
- `docs/prompts/tradingagents-v1-INDEX.md`

## Required Content

### Capability map

Record actual pilot outcomes by ticker and market, including:

- requested ticker
- normalized ticker
- upstream ticker
- upstream version
- final status
- observed latency
- observed token or cost metadata if available
- analyst usefulness judgment
- notes on weakness or instability

### Expansion guide

Only after a successful pilot, document:

- whether `stock_watch_workflow.py` is approved as the first consumer
- criteria for adding any further consumers
- how to extend ticker normalization for new markets
- how to review or update the upstream version pin
- how to monitor cost and timeout behavior

### Adoption-boundary update

Update the boundary doc to reflect what changed after the pilot:

- which pilot rows passed
- which rows remained partial but usable
- which rows failed and still block expansion
- whether local-market support is strong enough for wider rollout

## Acceptance Criteria

- all statements are tied to real pilot evidence
- the docs clearly separate proven support from tentative support
- expansion guidance remains bounded and evidence-aware
- no runtime code is changed in this unit

## Constraints

- docs only
- do not fill these docs speculatively before pilot evidence exists
- if the pilot result is mixed, preserve the narrower boundary instead of
  forcing expansion
