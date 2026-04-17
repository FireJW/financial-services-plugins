# Codex Prompt — Unit 1: Contract and Setup

## Goal

Define the canonical operator setup and the canonical `market_context` contract before implementing any bridge code.

## Files to create

- `docs/runtime/openalice-sidecar-setup.md`
- `docs/runtime/openalice-market-context-contract.md`
- `docs/runtime/openalice-capability-map.md`

## Inputs

- `docs/plans/2026-04-04-003-feat-openalice-integration-plan.md`
- `docs/runtime/openalice-risk-register.md`
- `docs/runtime/openalice-adoption-boundary.md`
- `docs/runtime/openalice-pilot-matrix.md`

## Requirements

### 1. `openalice-sidecar-setup.md`
Document only the supported setup:
- external OpenAlice/OpenTypeBB HTTP sidecar
- loopback base URL like `http://127.0.0.1:6901`
- health endpoint `/api/v1/health`
- explicit operator-managed start instructions placeholder
- no requirement that this repo install OpenAlice dependencies
- no secrets committed into this repo

Document config expectations for this repo:
- environment variable or request-level override for base URL
- optional mode vs required mode
- timeouts
- loopback-only recommendation

### 2. `openalice-market-context-contract.md`
Define a canonical JSON contract with required fields for:
- capability
- requested_symbol
- resolved_symbol
- provider
- source
- retrieved_at
- observed_at
- coverage_status
- warnings
- quote_snapshot
- history
- fundamentals
- benchmark_context
- indicators
- raw_meta

Also define:
- error object shape
- warning object shape
- meaning of `full`, `partial`, `missing`, `error`
- rule that this contract is parallel to, not inside, evidence contracts

### 3. `openalice-capability-map.md`
Provide a table that maps:
- quote
- history
- fundamentals
- benchmark
- indicator bundle

to:
- intended OpenTypeBB/OpenBB-style HTTP endpoint family
- whether it is allowed in v1
- whether it is required for pilot success
- notes about likely provider limitations

Also include a short list of explicitly unsupported surfaces:
- `MCP Ask`
- trading
- broker execution
- web/telegram connectors
- news ingestion

## Constraints

- Docs only in this unit.
- Do not modify code.
- Do not over-specify endpoints if the exact path is uncertain; clearly label assumptions.

## Acceptance criteria

- There is one canonical setup doc.
- There is one canonical `market_context` contract.
- The capability map makes allowed vs forbidden surfaces obvious.
