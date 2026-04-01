# Runtime Orchestration Docs

This directory defines the wrapper-layer contracts for the P0/P1 runtime
hardening work.

Scope:

- `sub-agent-contract.md`: required worker output shape
- `verification-checklist.md`: verifier checklist and failure criteria
- `structured-verifier-schema.md`: structured verifier JSON contract
- `NOW-template.md`: fixed session-state template
- `compaction-template.md`: intent-preserving compact summary template

These docs are the durable contract for `scripts/runtime/` and
`tests/runtime-host/`. The goal is to harden orchestration without modifying
the recovered runtime until the wrapper layer proves out.

## Runtime Scripts

- `scripts/runtime/run-task-profile.mjs`
  - low-level profile router
  - supports `--list`, `--profile`, `--dry-run`, and actual runtime execution
- `scripts/runtime/run-worker-task.mjs`
  - builds a concrete worker prompt from task text plus optional `NOW` and
    `INTENT` state
  - defaults to `--print --output-format text`
  - supports `--task-id <id>` to stamp a stable task key into runtime artifacts
  - supports `--attempt-ledger-file <path>` to append one machine-readable
    entry per wrapper attempt
  - emits a prompt budget report in `--dry-run --json`
  - auto-raises the initial `--max-turns` budget when the prompt is large and
    no explicit `--max-turns` override was passed
  - persists live stdout to `--output <path>` as UTF-8 when requested
  - retries once by default on empty stdout, max-turn exhaustion, or invalid
    worker-contract output
  - validates the worker markdown contract after execution unless
    `--skip-validation` is set
- `scripts/runtime/run-verifier-task.mjs`
  - builds a verifier prompt from the original task, worker output, changed
    files, and approach notes
  - normalizes worker output before verification by trimming preamble before
    the first required heading when possible
  - runs deterministic worker-contract preflight before any model call
  - supports `--task-id <id>` to stamp a stable task key into runtime artifacts
  - supports `--attempt-ledger-file <path>` to append one machine-readable
    entry per wrapper attempt
  - emits a prompt budget report in `--dry-run --json`
  - auto-raises the initial `--max-turns` budget when the prompt is large and
    no explicit `--max-turns` override was passed
  - supports `--structured-verifier` to make JSON the authoritative verifier
    artifact while rendering markdown as a sidecar
  - supports `--structured-output-file <path>` to persist the authoritative
    structured verifier JSON report
  - persists live stdout to `--output <path>` as UTF-8 when requested
  - retries by default on empty stdout, max-turn exhaustion, or verifier
    contract drift
  - supports `--local-only` for pure local validation
- `scripts/runtime/build-session-state.mjs`
  - renders fixed-shape `NOW` markdown or JSON payload
- `scripts/runtime/preserve-user-intent.mjs`
  - derives `INTENT` and compact-summary payloads from raw user requests or a
    structured intent file
  - preserves multilingual hard constraints vs non-goals when the raw request
    mixes English with Chinese instructions
- `scripts/runtime/run-verification-pass.mjs`
  - deterministic validator for worker, compaction, or structured verifier
    output
- `scripts/runtime/summarize-runtime-attempt-ledger.mjs`
  - turns an NDJSON attempt ledger into a compact text or JSON scorecard
- `scripts/runtime/run-runtime-host-reliability-suite.mjs`
  - runs the curated runtime host regression subset that covers worker/verifier
    entrypoints, structured verifier mode, prompt budget guardrails, attempt
    ledger, multilingual intent/session-state handling, and real-task fixtures
    for both feedback-workflow and macro-shock chain-map tasks

## Recommended Workflow

1. Refresh `INTENT`

```powershell
node scripts/runtime/preserve-user-intent.mjs `
  --input runtime-state/raw-user-request.txt `
  --output-kind intent `
  --output runtime-state/INTENT.md `
  --format text
```

The raw request can be English, Chinese, or mixed-language. The wrapper keeps
hard constraints such as `不要破坏当前 headless 回归测试` separate from non-goals
such as `不要在这一步实现完整 Dream Memory pipeline`.

If you also want a compact-summary version for compaction/resume glue:

```powershell
node scripts/runtime/preserve-user-intent.mjs `
  --input runtime-state/raw-user-request.txt `
  --output-kind compaction `
  --output runtime-state/INTENT-COMPACT.md `
  --format text
```

2. Refresh `NOW`

```powershell
node scripts/runtime/build-session-state.mjs `
  --input runtime-state/current-session.json `
  --output runtime-state/NOW.md `
  --format text
```

3. Dry-run the worker invocation

```powershell
node scripts/runtime/run-worker-task.mjs `
  --task-file docs/plans/2026-03-31-002-feat-agent-runtime-p0-p1-hardening-plan.md `
  --dry-run `
  --json
```

Check the returned `promptBudgetReport` before a long run. When risk is
`warning` or `danger`, the wrapper will recommend a safer turn budget and show
which prompt segment is dominating size.

4. Run the worker for real

```powershell
node scripts/runtime/run-worker-task.mjs `
  --task-file docs/plans/2026-03-31-002-feat-agent-runtime-p0-p1-hardening-plan.md `
  --task-id runtime-hardening `
  --attempt-ledger-file runtime-state/runtime-attempts.ndjson `
  --output runtime-state/worker-output.md `
  -- --max-turns 4
```

Optional:

- add `--max-attempts <n>` to increase wrapper-managed retries

5. Run verifier preflight only

```powershell
node scripts/runtime/run-verifier-task.mjs `
  --original-task-file docs/plans/2026-03-31-002-feat-agent-runtime-p0-p1-hardening-plan.md `
  --worker-output-file runtime-state/worker-output.md `
  --files-changed-file runtime-state/files-changed.txt `
  --approach-file runtime-state/approach.md `
  --local-only `
  --json
```

6. Run the verifier profile

```powershell
node scripts/runtime/run-verifier-task.mjs `
  --original-task-file docs/plans/2026-03-31-002-feat-agent-runtime-p0-p1-hardening-plan.md `
  --task-id runtime-hardening `
  --worker-output-file runtime-state/worker-output.md `
  --files-changed-file runtime-state/files-changed.txt `
  --approach-file runtime-state/approach.md `
  --attempt-ledger-file runtime-state/runtime-attempts.ndjson `
  --output runtime-state/verifier-output.md
```

If the verifier report is long or the task is evidence-heavy, prefer the
current default verifier budget (`max-turns=4`) or override explicitly with:

```powershell
node scripts/runtime/run-verifier-task.mjs `
  ... `
  --output runtime-state/verifier-output.md `
  -- --max-turns 4
```

Optional:

- add `--max-attempts <n>` if the verifier is still flaky on a long task

### Attempt Ledger And Scorecard

Use one shared ledger file across worker and verifier runs when you want
durable retry and failure visibility:

```powershell
node scripts/runtime/summarize-runtime-attempt-ledger.mjs `
  --input runtime-state/runtime-attempts.ndjson `
  --json
```

The scorecard summarizes:

- total runs and attempts
- success vs failed runs
- retry counts by reason
- per-profile averages for attempts and duration
- prompt-budget snapshots for each persisted attempt

### Prompt Budget Guardrails

The wrapper now estimates prompt size before the first worker or verifier call.

Default behavior:

- `--dry-run --json` includes `promptBudgetReport`
- real runs print a readable budget warning to stderr when risk is `warning` or
  `danger`
- if the prompt is large and you did not explicitly pass `--max-turns`, the
  wrapper auto-raises the initial turn budget to the safer recommendation
- verifier danger runs suggest enabling `--structured-verifier`

If you want to keep a lower turn budget anyway, pass an explicit runtime
override such as:

```powershell
node scripts/runtime/run-verifier-task.mjs `
  ... `
  -- --max-turns 4
```

### Structured Verifier Mode

Use structured verifier mode when you want JSON to be the verifier source of
truth while keeping a human-readable markdown report:

```powershell
node scripts/runtime/run-verifier-task.mjs `
  --original-task-file runtime-state/<task>-task.md `
  --worker-output-file runtime-state/<task>-worker-output.md `
  --files-changed-file runtime-state/<task>-files-changed.txt `
  --approach-file runtime-state/<task>-approach.md `
  --structured-verifier `
  --output runtime-state/<task>-verifier-output.md `
  --structured-output-file runtime-state/<task>-verifier-output.json
```

In this mode:

- `--output` receives the wrapper-rendered markdown sidecar
- `--structured-output-file` receives the authoritative JSON artifact
- wrapper pass/fail gating uses the JSON artifact, not markdown parsing

To validate a structured verifier fixture or saved artifact locally:

```powershell
node scripts/runtime/run-verification-pass.mjs `
  --input tests/fixtures/runtime-orchestration/structured-verifier-valid.json `
  --mode structured-verifier `
  --json
```

To locally smoke-test multilingual intent extraction:

```powershell
node scripts/runtime/preserve-user-intent.mjs `
  --input tests/fixtures/runtime-state/sample-user-request-multilingual.txt `
  --output-kind intent `
  --json
```

To rerun the current curated runtime host reliability suite:

```powershell
node scripts/runtime/run-runtime-host-reliability-suite.mjs
```

## State Files

- `runtime-state/INTENT.md`
  - stable user request, hard constraints, and non-goals
- `runtime-state/NOW.md`
  - stable current-state snapshot for long-running work

`runtime-state/` is intentionally gitignored. Use it to compress working
context without polluting the repository history.

For a fuller operator guide, troubleshooting notes, and real-task usage
patterns, read [`OPERATOR-MANUAL.md`](OPERATOR-MANUAL.md).
