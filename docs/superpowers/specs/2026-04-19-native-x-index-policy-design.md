# Native X Index Policy Design

**Date:** 2026-04-19  
**Status:** Proposed  
**Scope:** Repository-wide documentation and workflow policy only

## 1. Goal

Promote a single repository-wide default rule for indexing X / Twitter content:

- the native X ingestion path is `x_index_runtime`
- on Windows, the preferred session strategy is
  `browser_session.strategy=remote_debugging`
- signed-session reuse is the default priority, not public scraping
- higher-level workflows must clearly distinguish between:
  - live signed-session X results
  - reused prior `x-index` results
  - static/manual X-like input blocks

This policy exists so the repo does not drift into multiple incompatible X
collection habits depending on which wrapper or report layer is being used.

## 2. Why This Exists

Recent weekend-market work exposed a mismatch:

- the repo already has a native X runtime with signed-session support
- that native runtime still supports `remote_debugging`
- but the newer weekend candidate layer currently consumes static
  `weekend_market_candidate_input` instead of automatically using the native X
  runtime

The result is confusing operator behavior:

- one workflow is assumed to reflect live X intelligence
- but the actual output may only reflect hand-assembled social inputs

This design does not fix that implementation gap yet. It establishes the
repository-wide policy that should govern future workflow behavior and
documentation.

## 3. Policy Statement

The repository-wide default X platform policy should be:

1. **Native X route**
   - `x_index_runtime` is the primary X indexing layer
2. **Preferred session strategy**
   - on Windows, prefer `browser_session.strategy=remote_debugging` when an
     already signed-in browser session is available
3. **Reuse before recollection**
   - reuse recent relevant `x-index` outputs before recollecting the same X
     evidence
4. **Public fallback is not the default**
   - public-page fallback is allowed only after native session-backed paths are
     unavailable or clearly out of scope
5. **Higher-level workflow transparency**
   - any workflow that does not use live native X ingestion must say so
     explicitly in output or request semantics

## 4. Scope Boundary

Included in phase 1:

- repository-level documentation updates
- command-level wording alignment
- explicit policy language for X ingestion order
- explicit distinction between native X results and static/manual social inputs

Excluded in phase 1:

- automatic rewiring of all higher-level workflows to call `x_index_runtime`
- changes to `weekend_market_candidate` runtime behavior
- changes to `agent-reach` X channel behavior
- changes to remote session bootstrap code
- new browser/session transport logic

## 5. Canonical Priority Order

Repository documentation should declare a fixed X-ingestion priority order:

1. **Live native X indexing**
   - `x_index_runtime`
   - signed session
   - `remote_debugging` preferred on Windows
2. **Recent native X result reuse**
   - reuse an existing still-relevant `x-index` result
3. **Static/manual X-shaped inputs**
   - curated handles, URLs, summaries, or candidate blocks
4. **Public fallback**
   - only when the native signed-session route is unavailable

This order must be described as a policy, not as a suggestion.

## 6. Semantics for Higher-Level Workflows

Higher-level workflows such as:

- weekend market candidates
- X style boards
- cross-market social scans
- article and topic workflows that consume X evidence indirectly

must be described using one of the following source semantics:

### 6.1 Native live X

The workflow consumed current or recent output from `x_index_runtime`,
preferably via signed-session browser reuse.

### 6.2 Native reused X result

The workflow reused a previously captured `x-index` result that is still
considered relevant.

### 6.3 Static/manual X-shaped input

The workflow consumed operator-curated handles, URLs, summaries, or theme
inputs that resemble X evidence but do **not** constitute a live native X run.

This distinction is mandatory because users should not confuse:

- “the system used the native X session-backed route”

with:

- “the system used manually prepared X-like source inputs”

## 7. Documentation Targets

Phase 1 should update these surfaces:

### 7.1 Repository-wide runtime guidance

- `docs/runtime/README.md`

This is the preferred repository-level home for the rule because it already
holds cross-route source policy guidance, including Reddit route notes.

Add a new X policy section that states:

- `x-index` is the native X route
- Windows defaults to `remote_debugging`
- `agent-reach` does not replace the native X route
- higher-level workflows must disclose when they are using static/manual social
  inputs rather than live native X results

### 7.2 Command-level X guidance

- `financial-analysis/commands/x-index.md`

This command doc should align with the repository-wide rule and make the
priority order explicit, not just implicit.

### 7.3 Bridge command clarification

- `financial-analysis/commands/agent-reach-bridge.md`

This doc already says repository-native `x-index + remote_debugging` remains
the primary X workflow. Phase 1 should preserve and slightly strengthen that
wording so it matches the runtime README.

## 8. Required Wording Themes

The documentation should consistently communicate:

- “native X route”
- “signed-session reuse”
- “remote_debugging preferred on Windows”
- “public scraping is fallback, not default”
- “static/manual social input is not the same as live native X evidence”

The wording should avoid ambiguous phrases such as:

- “X source”
- “social input”
- “X evidence”

when the actual source mode is static/manual and not native runtime output.

## 9. Non-Goals

This design does not claim that:

- every workflow already follows the policy
- weekend candidate already uses live X by default
- remote session bootstrap is always healthy
- `agent-reach` should be removed

Instead, it declares the documentation-level default that future workflow work
must follow.

## 10. Success Criteria

This repository-level policy change is successful when:

1. there is one obvious place in repo docs that states the default X ingestion
   rule
2. command docs no longer leave room to interpret public scraping or static
   inputs as the default X path
3. users can distinguish between live native X evidence and manually assembled
   social inputs
4. future workflow work can reference this policy instead of re-deciding the
   X-source hierarchy each time

## 11. Implementation Direction

Phase 1 implementation should stay lightweight:

- update repository/runtime documentation
- align command docs
- do not change runtime code

If later work upgrades higher-level workflows such as
`weekend_market_candidate`, that implementation should explicitly reference
this policy and move those workflows closer to:

- native `x_index_runtime` first
- signed session first
- static/manual social input only as a clearly labeled fallback
