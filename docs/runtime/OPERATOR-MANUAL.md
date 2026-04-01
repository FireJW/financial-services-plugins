# Runtime Operator Manual

As of 2026-04-01.

This manual describes how to run the wrapper-layer `explore -> worker ->
verifier` flow on a real task without relying on chat memory.

## 1. What This Layer Does

The wrapper adds four controls around the recovered runtime:

1. fixed worker output contract
2. verifier checklist and independent pass
3. fixed `NOW` session-state shape
4. intent-preserving compaction / request carry-forward

This layer is meant to be cheap to change and easy to test. It is not a full
vendor-runtime rewrite.

## 2. Core Files

Contracts:

- `docs/runtime/sub-agent-contract.md`
- `docs/runtime/verification-checklist.md`
- `docs/runtime/structured-verifier-schema.md`
- `docs/runtime/NOW-template.md`
- `docs/runtime/compaction-template.md`

Entry scripts:

- `scripts/runtime/run-real-task.mjs`
- `scripts/runtime/route-request.mjs`
- `scripts/runtime/run-task-profile.mjs`
- `scripts/runtime/run-worker-task.mjs`
- `scripts/runtime/run-verifier-task.mjs`
- `scripts/runtime/build-session-state.mjs`
- `scripts/runtime/preserve-user-intent.mjs`
- `scripts/runtime/run-verification-pass.mjs`
- `scripts/runtime/summarize-runtime-attempt-ledger.mjs`

Runtime state:

- `runtime-state/INTENT.md`
- `runtime-state/INTENT-COMPACT.md`
- `runtime-state/NOW.md`

`runtime-state/` stays gitignored.

## 3. Profiles

### `explore`

- use for cheap discovery, inventory, and low-risk reconnaissance
- default `max-turns=1`
- not for final synthesis or verification verdicts

### Request Router

Use `route-request.mjs` when you want the wrapper to choose the closest native
workflow and profile before you run the main task:

```powershell
node scripts/runtime/route-request.mjs `
  --json `
  --request "Collect what this design leader said in interviews and support tickets, then turn it into a workflow cadence."
```

The router currently recognizes:

- `feedback_workflow`
- `classic_case`
- `a_share_event_research`
- `fallback_search`

### `worker`

- use for the main execution pass
- default `max-turns=4`
- default wrapper retries: `2`
- must satisfy the worker contract

### `verifier`

- use for the independent review pass
- current default `max-turns=4`
- default wrapper retries: `3`
- must emit `### Check:` blocks plus a final `VERDICT:`
- optional structured mode makes JSON authoritative and markdown derived

## 4. Standard Runbook

### Fast Path: One-Command Real Task Runner

If the task is already defined and you want the wrapper to materialize a clean
run pack, execute worker, and then gate the result through verifier, start
here:

```powershell
node scripts/runtime/run-real-task.mjs `
  --input-file runtime-state/<task>-task.md `
  --session-file runtime-state/<task>-session.json `
  --context-file runtime-state/<task>-evidence.md `
  --output-dir runtime-state/real-task-runs/<task> `
  --json
```

This high-level runner:

- routes the request first and writes route guidance into the run pack
- derives `INTENT.md`, `INTENT-COMPACT.md`, and `NOW.md`
- runs worker, verifier preflight, and final verifier in sequence
- writes a per-run `runtime-attempts.ndjson` plus scorecard files
- defaults to structured verifier mode
- fails closed unless the final verifier verdict is `PASS`

Use the step-by-step flow below when you want to inspect or override each stage
manually.

If the worker already finished and you only want to rerun verifier from the
same run pack:

```powershell
node scripts/runtime/run-verifier-task.mjs `
  --original-task-file runtime-state/real-task-runs/<task>/task.md `
  --task-id <task> `
  --worker-output-file runtime-state/real-task-runs/<task>/worker-output.md `
  --files-changed-file runtime-state/real-task-runs/<task>/files-changed.txt `
  --approach-file runtime-state/real-task-runs/<task>/approach.md `
  --intent-file runtime-state/real-task-runs/<task>/INTENT.md `
  --now-file runtime-state/real-task-runs/<task>/NOW.md `
  --attempt-ledger-file runtime-state/real-task-runs/<task>/runtime-attempts.ndjson `
  --structured-verifier `
  --output runtime-state/real-task-runs/<task>/verifier-output.md `
  --structured-output-file runtime-state/real-task-runs/<task>/verifier-output.json
```

### Step 1: Write the raw request

Create a task-specific raw request file rather than reusing the shared default
files when the task is materially different.

Example naming pattern:

- `runtime-state/<task>-raw-request.txt`
- `runtime-state/<task>-task.md`
- `runtime-state/<task>-session.json`
- `runtime-state/<task>-approach.md`
- `runtime-state/<task>-files-changed.txt`

### Step 2: Build `INTENT`

```powershell
node scripts/runtime/preserve-user-intent.mjs `
  --input runtime-state/<task>-raw-request.txt `
  --output-kind intent `
  --output runtime-state/<task>-INTENT.md `
  --format text
```

The raw request may be English, Chinese, or mixed-language. The wrapper now
keeps multilingual hard constraints and non-goals separate during extraction.
For example:

- `不要破坏当前 headless 回归测试` stays under `Hard Constraints`
- `不要在这一步实现完整 Dream Memory pipeline` stays under `Non-goals`

Optional compaction payload:

```powershell
node scripts/runtime/preserve-user-intent.mjs `
  --input runtime-state/<task>-raw-request.txt `
  --output-kind compaction `
  --output runtime-state/<task>-INTENT-COMPACT.md `
  --format text
```

### Step 3: Build `NOW`

```powershell
node scripts/runtime/build-session-state.mjs `
  --input runtime-state/<task>-session.json `
  --output runtime-state/<task>-NOW.md `
  --format text
```

### Step 4: Dry-run the worker

```powershell
node scripts/runtime/run-worker-task.mjs `
  --task-file runtime-state/<task>-task.md `
  --intent-file runtime-state/<task>-INTENT.md `
  --now-file runtime-state/<task>-NOW.md `
  --context-file runtime-state/<task>-evidence.md `
  --dry-run `
  --json
```

Use this to verify:

- prompt shape
- plugin directories
- model/profile routing
- appended contract file
- prompt budget risk and dominant segments from `promptBudgetReport`

### Step 5: Run the worker for real

```powershell
node scripts/runtime/run-worker-task.mjs `
  --task-file runtime-state/<task>-task.md `
  --task-id <task> `
  --intent-file runtime-state/<task>-INTENT.md `
  --now-file runtime-state/<task>-NOW.md `
  --context-file runtime-state/<task>-evidence.md `
  --attempt-ledger-file runtime-state/runtime-attempts.ndjson `
  --output runtime-state/<task>-worker-output.md
```

Notes:

- `--output` now writes UTF-8 directly from the wrapper. Do not use
  `Tee-Object` unless you intentionally want PowerShell-specific behavior.
- the worker wrapper retries automatically on empty stdout, max-turn
  exhaustion, or contract-invalid output.
- if the prompt is large and you did not explicitly pass `--max-turns`, the
  wrapper may auto-raise the initial turn budget before the first call.
- if the worker is likely to be long, you can still override:

```powershell
node scripts/runtime/run-worker-task.mjs `
  ... `
  --output runtime-state/<task>-worker-output.md `
  -- --max-turns 4
```

To increase wrapper retries:

```powershell
node scripts/runtime/run-worker-task.mjs `
  ... `
  --output runtime-state/<task>-worker-output.md `
  --max-attempts 3
```

### Step 6: Run verifier preflight

```powershell
node scripts/runtime/run-verifier-task.mjs `
  --original-task-file runtime-state/<task>-task.md `
  --worker-output-file runtime-state/<task>-worker-output.md `
  --files-changed-file runtime-state/<task>-files-changed.txt `
  --approach-file runtime-state/<task>-approach.md `
  --intent-file runtime-state/<task>-INTENT.md `
  --now-file runtime-state/<task>-NOW.md `
  --local-only `
  --json
```

This is deterministic. It checks only structure, not truth.

The verifier wrapper also normalizes worker output before review by trimming
any stray preamble before the first required worker heading when such a heading
exists.

### Step 7: Run the verifier for real

```powershell
node scripts/runtime/run-verifier-task.mjs `
  --original-task-file runtime-state/<task>-task.md `
  --task-id <task> `
  --worker-output-file runtime-state/<task>-worker-output.md `
  --files-changed-file runtime-state/<task>-files-changed.txt `
  --approach-file runtime-state/<task>-approach.md `
  --intent-file runtime-state/<task>-INTENT.md `
  --now-file runtime-state/<task>-NOW.md `
  --attempt-ledger-file runtime-state/runtime-attempts.ndjson `
  --output runtime-state/<task>-verifier-output.md
```

If the task is evidence-heavy, keep or restate the current verifier default:

```powershell
node scripts/runtime/run-verifier-task.mjs `
  ... `
  --output runtime-state/<task>-verifier-output.md `
  -- --max-turns 4
```

To increase verifier retries:

```powershell
node scripts/runtime/run-verifier-task.mjs `
  ... `
  --output runtime-state/<task>-verifier-output.md `
  --max-attempts 4
```

If the verifier prompt is large and you did not explicitly pass `--max-turns`,
the wrapper may auto-raise the initial turn budget before the first call.

### Step 7b: Run the structured verifier path

```powershell
node scripts/runtime/run-verifier-task.mjs `
  --original-task-file runtime-state/<task>-task.md `
  --task-id <task> `
  --worker-output-file runtime-state/<task>-worker-output.md `
  --files-changed-file runtime-state/<task>-files-changed.txt `
  --approach-file runtime-state/<task>-approach.md `
  --intent-file runtime-state/<task>-INTENT.md `
  --now-file runtime-state/<task>-NOW.md `
  --attempt-ledger-file runtime-state/runtime-attempts.ndjson `
  --structured-verifier `
  --output runtime-state/<task>-verifier-output.md `
  --structured-output-file runtime-state/<task>-verifier-output.json
```

Notes:

- the JSON file is the authoritative verifier artifact
- the markdown file is rendered by the wrapper from the JSON artifact
- if the JSON artifact is missing, malformed, or schema-invalid, the wrapper
  fails closed
- the shared ledger file now records every worker and verifier attempt,
  including retry reason and max-turn bump information when applicable

### Step 8: Build the runtime scorecard

```powershell
node scripts/runtime/summarize-runtime-attempt-ledger.mjs `
  --input runtime-state/runtime-attempts.ndjson `
  --format text
```

Use `--json` when you want a machine-readable summary for automation.

The per-attempt ledger entries now also preserve prompt budget snapshots, so
you can correlate retries with oversized worker or verifier prompts.

If you want to sanity-check multilingual extraction before a long run:

```powershell
node scripts/runtime/preserve-user-intent.mjs `
  --input tests/fixtures/runtime-state/sample-user-request-multilingual.txt `
  --output-kind intent `
  --json
```

## 5. Reading Results

### Real-Task Runner Summary

The high-level runner writes:

- `run-plan.json`
- `run-summary.json`
- `runtime-attempt-scorecard.json`
- `runtime-attempt-scorecard.txt`

Treat `run-summary.json` as the machine-readable run envelope. A run is only
successful when:

1. worker exits cleanly
2. verifier preflight passes
3. verifier exits cleanly
4. final verifier verdict is `PASS`

### Worker

Valid worker output must contain, in order:

1. `## Conclusion`
2. `## Confirmed`
3. `## Unconfirmed`
4. `## Risks`
5. `## Next Step`

### Verifier

Valid verifier output must contain:

- one or more `### Check:` blocks
- each check block includes:
  - `**Command run:**`
  - `**Output observed:**`
  - `**Result:**`
- at least one adversarial probe
- final line: `VERDICT: PASS|FAIL|PARTIAL`

### Structured Verifier

Valid structured verifier output must contain:

- `schemaVersion = structured-verifier-v1`
- `verdict = PASS|FAIL|PARTIAL`
- `hasAdversarialProbe = true`
- one or more `checks`
- every check includes:
  - `title`
  - `commandRun`
  - `outputObserved`
  - `result`
  - `isAdversarialProbe`

## 6. Common Failure Modes

### `spawnSync node EPERM`

Meaning:

- the sandbox blocked the recovered runtime process spawn

Action:

- rerun with escalation approval

### Verifier hits max turns

Meaning:

- the verifier profile budget is too small for the prompt size

Action:

- rerun with `-- --max-turns 4` or higher if justified

If you did not pass an explicit `--max-turns`, check whether the wrapper
already auto-raised the initial budget and whether the prompt still needs to be
trimmed or split.

### Runtime returns empty stdout

Meaning:

- the runtime exited successfully but produced no usable worker or verifier
  body

Action:

- treat this as a runtime/model compliance failure, not a successful pass
- the wrapper now retries this automatically before surfacing failure
- rerun once more manually only after checking prompt size and recent changes
- if it repeats, inspect whether the task should be shortened or split before
  assuming the verifier contract is wrong

### Prompt budget warning appears before the run

Meaning:

- the wrapper estimates the prompt is large enough to increase failure risk

Action:

- inspect the reported top segments
- trim the dominant context or worker-output block if possible
- accept the auto-raised turn budget, or pass an explicit `--max-turns` if you
  intentionally want tighter limits
- for large verifier passes, prefer `--structured-verifier`

### Worker or verifier adds preamble text

Meaning:

- the model did not start directly in the required contract shape

Action:

- current prompts explicitly forbid preambles
- verifier now auto-normalizes worker preamble when the first required worker
  heading is present
- if legacy output already exists and still fails, sanitize by trimming
  everything before the first required heading, then rerun verifier preflight

### PowerShell output encoding breaks verifier preflight

Meaning:

- output was captured with a PowerShell default encoding path such as
  `Tee-Object`, often UTF-16LE, while Node later read it as UTF-8

Action:

- prefer wrapper-native `--output`
- if a file is already wrong, rewrite it with UTF-8 before using it downstream

### Verifier output exists but wrapper rejects it

Meaning:

- the model may have produced a mostly valid review that still violated one
  required field shape

Action:

1. inspect the saved verifier output
2. run a local parse against `parseVerifierOutput`
3. decide whether to tighten prompt, relax parser compatibly, or keep the
   contract strict

### Structured verifier JSON exists but wrapper rejects it

Meaning:

- the runtime returned parseable JSON, but the JSON violated the structured
  verifier schema

Action:

1. run `run-verification-pass.mjs --mode structured-verifier` on the saved JSON
2. inspect missing or invalid fields
3. fix the prompt or renderer expectations before assuming the schema is wrong

## 7. Real-Task Guidance

For real research or planning tasks:

- build task-specific state files instead of reusing generic ones
- keep one evidence pack or context file per task
- record the approach and changed-file list before the verifier run
- if the worker output is contract-valid but presentation-weak, let the verifier
  call that out rather than patching by hand first

## 8. Verification Commands

Recommended regression set after runtime-wrapper changes:

```powershell
node scripts/runtime/run-runtime-host-reliability-suite.mjs
node scripts/runtime/run-runtime-compatibility-suite.mjs --json --check
node --test tests\runtime-host\*.test.mjs
```

The reliability suite is the fastest high-signal check. It currently covers:

- real-task Jenny feedback-workflow fixtures
- real-task A-share macro-shock chain-map fixtures
- real-task latest-event verification fixtures
- real-task X-post evidence fixtures
- real-task evidence-to-article fixtures
- real-task workflow-improvement-loop fixtures
- prompt budget guardrails
- attempt ledger and scorecard
- worker/verifier entrypoints
- structured verifier contract and entrypoints
- verification pass validation

Use the fixture coverage report before landing to `main` when you want a quick
answer to "which core real-task cases are currently represented?":

```powershell
node scripts/runtime/report-runtime-fixture-coverage.mjs --json --check
```
- multilingual intent preservation and session-state rendering

Use narrower tests when touching a single behavior:

```powershell
node --test tests\runtime-host\worker-verifier-entrypoints.test.mjs
node --test tests\runtime-host\task-profile-routing.test.mjs
node --test tests\runtime-host\structured-verifier-contract.test.mjs
node --test tests\runtime-host\structured-verifier-entrypoints.test.mjs
node --test tests\runtime-host\runtime-compatibility-suite-entrypoint.test.mjs
```

Use the compatibility gate when the wrapper, plugin surface, or recovered
runtime wiring might have drifted:

```powershell
node scripts/runtime/run-runtime-compatibility-suite.mjs --json --check
```

Policy:

- semantic probe drift or runtime probe failure returns non-zero
- missing runtime build returns a skipped report by default
- add `--require-built-runtime` when you want skipped runs to fail closed

## 9. Current Practical Guidance

At the current maturity level:

- keep the wrapper strict on structure
- be moderately tolerant on verifier field formatting variants
- prefer wrapper-managed retries over ad hoc reruns in the shell
- prefer fixing wrapper edges before patching the recovered vendor runtime
- treat real-task runs as part of validation, not just the automated test suite
