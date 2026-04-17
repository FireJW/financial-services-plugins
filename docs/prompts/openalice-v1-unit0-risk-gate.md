# Codex Prompt — Unit 0: Risk Gate and Pilot Boundary

## Goal

Before writing any bridge code, create the documentation that freezes the safe integration boundary for OpenAlice.

## Files to create

- `docs/runtime/openalice-risk-register.md`
- `docs/runtime/openalice-adoption-boundary.md`
- `docs/runtime/openalice-pilot-matrix.md`

## Inputs

- `docs/plans/2026-04-04-003-feat-openalice-integration-plan.md`
- local findings already reflected in that plan

## Required content

### 1. `openalice-risk-register.md`
Document at least these risks:
- AGPL-3.0 license risk
- Node 22+/pnpm monorepo runtime drag
- A-share coverage uncertainty
- sidecar output being mistaken for evidence
- session exposure risk from `mcp-ask`
- connector/auth/CORS risk if wrong surfaces are enabled
- silent workflow breakage if sidecar becomes required

For each risk include:
- severity
- why it matters here
- mitigation
- go/no-go implication

### 2. `openalice-adoption-boundary.md`
Must clearly separate:

**Allowed in v1**
- external HTTP sidecar only
- OpenTypeBB-compatible market-data endpoints
- bounded capabilities: quote, history, fundamentals, benchmark, indicators
- loopback/local operator-managed config
- `stock_watch_workflow.py` as first consumer

**Forbidden in v1**
- vendoring OpenAlice
- direct package imports from OpenAlice
- `MCP Ask`
- trading / broker / UTA / Telegram / Web UI / brain / heartbeat / evolution mode
- merging sidecar data into evidence contracts
- adding router-default behavior before pilot success

### 3. `openalice-pilot-matrix.md`
Define the pilot matrix and pass/fail criteria.
Include at minimum:
- `601600.SS`
- `002837.SZ`
- one U.S. or ADR peer placeholder
- one China benchmark such as `000300.SS`

For each row include:
- expected capabilities to test
- acceptable fallback behavior
- what counts as full/partial/missing coverage

## Constraints

- Docs only in this unit.
- Do not modify runtime code.
- Keep wording operational and reviewable.

## Acceptance criteria

- Boundary is explicit and narrow.
- `MCP Ask` is clearly deferred.
- The pilot matrix has concrete pass/fail rules.
