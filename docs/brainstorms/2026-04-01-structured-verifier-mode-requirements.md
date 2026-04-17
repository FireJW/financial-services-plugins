---
date: 2026-04-01
topic: structured-verifier-mode
---

# Structured Verifier Mode

## Problem Frame

The current runtime wrapper has already closed the first wave of reliability gaps around worker/verifier prompting, retries, UTF-8 output, and contract validation. The main remaining weakness is that verifier success is still judged by parsing markdown text. That leaves the wrapper exposed to formatting drift even when the underlying verification logic is correct.

The next step is to make verifier output machine-authoritative without losing operator readability. This should improve correctness first, preserve the wrapper-first approach, and avoid widening scope into worker contracts, attempt ledgers, or broader runtime redesign.

## Requirements

**Verifier Output Contract**
- R1. Structured verifier mode shall use an authoritative JSON report as the verifier output contract.
- R2. The authoritative JSON report shall be sufficient for wrapper pass/fail gating without parsing markdown text.
- R3. The authoritative JSON report shall include, at minimum, a schema version, a final verdict, whether an adversarial probe was present, and a list of verification checks.
- R4. Each verification check in the authoritative JSON report shall include the logical equivalent of the current verifier fields: check title, command run, output observed, and result.
- R5. Structured verifier mode shall preserve a human-readable verifier artifact by rendering a markdown sidecar deterministically from the authoritative JSON report.

**Compatibility And Rollout**
- R6. Structured verifier mode shall be opt-in in v1 and shall not change the default behavior of existing verifier flows unless explicitly enabled.
- R7. When structured verifier mode is enabled, existing wrapper retry behavior and fail-closed semantics shall still apply.
- R8. If structured verifier mode is enabled but the verifier output is missing, malformed, or schema-invalid, the wrapper shall treat the run as failed rather than silently falling back to best-effort markdown parsing.
- R9. V1 shall not require changing the worker output contract.
- R10. V1 shall not require modifying the recovered vendor runtime as a prerequisite.

**Validation And Operator Workflow**
- R11. The local validation path for structured verifier mode shall support validating the structured verifier artifact without requiring a live model call where practical.
- R12. The repo shall include durable valid and invalid fixtures for structured verifier artifacts and regression coverage for parsing, rendering, and failure handling.
- R13. Structured verifier mode shall preserve a readable operator experience comparable to the current markdown verifier report.

## Success Criteria

- A verifier run can be executed in structured mode while leaving the existing markdown-only flow unchanged by default.
- When structured mode is enabled, wrapper pass/fail gating depends on the authoritative JSON artifact rather than regex-style markdown parsing.
- The markdown sidecar is deterministic and derived from the JSON artifact rather than being an independently authored second truth source.
- Malformed or incomplete structured verifier output fails closed and is covered by automated tests.
- Existing non-structured runtime tests and operator workflows continue to work during the rollout window.

## Scope Boundaries

- V1 does not add structured worker output.
- V1 does not add attempt-ledger or scorecard persistence.
- V1 does not make structured verifier mode the default path.
- V1 does not expand into vendor-runtime surgery.
- V1 does not redesign the worker/verifier task model beyond verifier output authority.

## Key Decisions

- JSON is the authoritative verifier output; markdown is a derived sidecar.
- The markdown sidecar is rendered by the wrapper, not authored independently by the model.
- The rollout starts as opt-in rather than default-on.
- V1 scope is limited to the final verifier report, not preflight data or retry metadata.
- The current worker contract remains unchanged in this phase.

## Dependencies / Assumptions

- The wrapper layer remains the primary integration surface for this work.
- Existing markdown verifier behavior remains available during rollout as the compatibility baseline.
- A machine-readable verifier artifact can be requested and validated without broadening the runtime surface beyond the current wrapper path.

## Outstanding Questions

### Resolve Before Planning
- None.

### Deferred to Planning
- [Affects R1-R5][Technical] What exact JSON schema shape and versioning strategy should be used for the authoritative verifier artifact?
- [Affects R5][Technical] What markdown rendering format should be considered canonical so current operator expectations remain familiar without reintroducing markdown authority?
- [Affects R6-R8][Technical] What CLI flag, profile option, or wrapper switch should enable structured verifier mode during the opt-in rollout?
- [Affects R11-R12][Technical] Which validations can remain fully local and deterministic, and which behaviors still require a live runtime invocation to verify end-to-end?

## Next Steps

`-> /prompts:ce-plan` for structured implementation planning
