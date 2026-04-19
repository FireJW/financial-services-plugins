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
- `scripts/runtime/run-real-task.mjs`
  - one-command real-task wrapper that materializes a run pack, routes the
    request, generates `INTENT` and `NOW`, runs worker, runs verifier
    preflight, runs the final verifier, and writes a per-run ledger/scorecard
  - writes a deterministic shaping plan before execution so oversized evidence
    packs can be trimmed or split before the first worker pass
  - when shaping risk is `warning` or `danger`, also materializes
    `shaping/execution-plan.{json,md}`, per-pass task/context overlays, and a
    synthesis worker command so chunk-first runs become executable instead of
    purely advisory
  - defaults to structured verifier mode, treats the JSON artifact as
    authoritative, and only reports success when the final verifier verdict is
    `PASS`
- `scripts/runtime/real-task-runs.mjs`
  - lists durable real-task run bundles under `runtime-state/real-task-runs/`
  - inspects one saved run pack and surfaces the main artifacts plus replay
    commands
  - can replay `worker`, `verifier-preflight`, `verifier`, or the full flow
    into an isolated `replays/<timestamp>/` directory instead of mutating the
    original bundle in place
- `scripts/runtime/route-request.mjs`
  - lightweight request router that turns a raw task request into a route plan
    with route id, profile, plugin dirs, native workflow references, and the
    recommended next `run-task-profile` command
  - currently recognizes `feedback_workflow`, `classic_case`,
    `a_share_event_research`, and `fallback_search`
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
- `scripts/runtime/run-runtime-compatibility-suite.mjs`
  - runs the canonical runtime compatibility gate over runtime init, plugin
    discovery, and runtime surface diff probes
  - exits non-zero on semantic probe drift or runtime probe failure
  - treats an unbuilt recovered runtime as a skipped local state by default
  - add `--require-built-runtime` when you want skipped runs to fail closed
  - legacy alias: `scripts/runtime/run-runtime-compat-suite.mjs` now delegates
    to this canonical entrypoint and returns the same report schema
- `scripts/runtime/run-runtime-host-reliability-suite.mjs`
  - runs the curated runtime host regression subset that covers worker/verifier
    entrypoints, structured verifier mode, prompt budget guardrails, attempt
    ledger, multilingual intent/session-state handling, and real-task fixtures
    for feedback-workflow, macro-shock chain-map, latest-event verification,
    X-post evidence, evidence-to-article, and workflow-improvement-loop tasks
- `scripts/runtime/report-runtime-fixture-coverage.mjs`
  - reports which real-task fixture packs currently exist and whether the core
    classic-case routes are all covered

## Task-Specific Research Routes

### Reddit Community Signal Route

As of 2026-04-04, the repo exposes one bounded Reddit route under
`financial-analysis/skills/autoresearch-info-index/`.

Use the route in this order:

- `agent-reach:reddit` when Reddit should join live cross-channel discovery and
  compete inside `hot_topic_discovery`
- `financial-analysis/commands/reddit-bridge.md` plus
  `scripts/run_reddit_bridge.cmd` when you already have a saved Reddit payload,
  `posts.csv`, or an export root such as `data/r_<subreddit>/posts.csv`

Guardrails:

- Reddit imports stay `channel=shadow` and `origin=reddit_bridge`
- Reddit comment context is operator context only; it does not confirm claims
  by itself
- `x-index` remains the native X/Twitter route; do not replace it with Reddit
  imports or public-page scraping
- subreddit profiles, low-signal buckets, and score multipliers must stay
  bounded and config-driven under
  `financial-analysis/skills/autoresearch-info-index/references/`

Comment metadata to preserve when present:

- `top_comment_summary`, `top_comment_excerpt`, `top_comment_count`,
  `top_comment_authors`, `top_comment_max_score`
- `comment_duplicate_count` for exact duplicate snapshots that were collapsed
- `comment_near_duplicate_count` for suspiciously similar comments that stay in
  the sample and only add caution metadata
- `comment_near_duplicate_same_author_count`,
  `comment_near_duplicate_cross_author_count`, and
  `comment_near_duplicate_level` when you need to tell author self-rephrasing
  from community-wide repetition
- `comment_near_duplicate_examples` when operator review needs one or two
  retained example pairs instead of only counters
- `comment_declared_count`, `comment_sample_coverage_ratio`,
  `comment_count_mismatch`, and `comment_sample_status` for partial samples
- `comment_operator_review` when downstream code wants one structured caution
  block with `has_partial_sample`, duplicate / near-duplicate flags, bounded
  review notes, and top-comment context
- `operator_review_priority` and result-level `operator_review_queue` when
  operators want pre-ranked manual-review work instead of reconstructing
  severity from raw caution fields

### Native X / Twitter Route

Repository-wide default policy:

- `x-index` is the native X / Twitter indexing route
- on Windows, prefer `browser_session.strategy=remote_debugging` when a signed
  browser session is available
- reuse recent relevant `x-index` results before recollecting the same evidence
- public-page scraping is fallback, not default
- `agent-reach` does not replace the native X route
- higher-level workflows must clearly distinguish:
  - live native X results
  - reused `x-index` results
  - static/manual X-shaped social inputs

Guardrails:

- do not describe static/manual social inputs as if they were native live X
  evidence
- do not make public X scraping the implied first step when the native session
  path is available
- when a higher-level workflow uses curated handles, URLs, or summaries instead
  of a live `x-index` run, disclose that source mode explicitly

Downstream publication flow as of 2026-04-04:

- `article_brief_runtime.py` surfaces the Reddit gate into `source_summary`
  plus brief markdown
- `article_workflow_runtime.py` and `macro_note_workflow_runtime.py` now carry
  `manual_review`, `publication_readiness`, and a shared
  `workflow_publication_gate`
- `article_publish_runtime.py` passes the workflow gate into the publish
  package, `article-publish-result.json`, automatic acceptance artifacts, and
  publish report
- `article_batch_workflow_runtime.py`, `article_auto_queue_runtime.py`, and
  `article_publish_reuse_runtime.py` now surface a direct
  `workflow_publication_gate` object on their item / candidate / result outputs
  instead of dropping the gate during queueing or reuse
- `wechat_push_readiness_runtime.py` now reports the workflow publication gate
  explicitly so WeChat push audits can still see the Reddit operator context
  even though Reddit remains shadow evidence
- `wechat_draftbox_runtime.py` and the `article_publish` push-stage summary now
  keep the same workflow gate in direct push results, so the context is still
  visible even when an operator skips the standalone readiness audit
- `article_publish_regression_check_runtime.py`,
  `article_publish_reuse_runtime.py`, and `wechat_push_draft.py` now surface the
  same workflow gate in regression reports, reuse reports, and CLI markdown
  summaries so the Reddit review state survives the whole publish toolchain

This route is useful for heat checks, clustering context, and operator review.
It is not a replacement for primary-source verification.

## Recommended Workflow

### Fast Path: One Command For A Real Task

When you already have the request, session snapshot, and main evidence pack,
use the high-level runner first:

```powershell
node scripts/runtime/run-real-task.mjs `
  --input-file tests/fixtures/runtime-real-tasks/jenny-feedback-workflow/task.md `
  --session-file tests/fixtures/runtime-state/sample-session-input.json `
  --context-file tests/fixtures/runtime-real-tasks/jenny-feedback-workflow/evidence.md `
  --output-dir runtime-state/real-task-runs/jenny-demo `
  --json
```

This runner:

- writes a self-contained run directory
- records `INTENT.md`, `INTENT-COMPACT.md`, `NOW.md`, and route guidance
- records `shaping-plan.json` and `shaping-plan.md` before model execution
- for oversized evidence packs, also writes `shaping/execution-plan.md`,
  `shaping/passes/*-task.md`, `shaping/passes/*-context.md`, and
  `shaping/*worker-command.txt`
- persists worker and verifier artifacts plus an attempt ledger scorecard
- fails closed unless the final verifier verdict is `PASS`

If you want the runner to refuse dangerously oversized worker prompts, add:

```powershell
node scripts/runtime/run-real-task.mjs `
  ... `
  --fail-on-danger-budget
```

### Durable Run Bundles: List, Inspect, Replay

Once `run-real-task.mjs` has created one or more run packs, use the bundle
helper instead of reconstructing file paths by hand:

```powershell
node scripts/runtime/real-task-runs.mjs `
  --json
```

Inspect one run:

```powershell
node scripts/runtime/real-task-runs.mjs `
  --run-dir runtime-state/real-task-runs/jenny-demo `
  --json
```

Replay verifier preflight into an isolated replay directory:

```powershell
node scripts/runtime/real-task-runs.mjs `
  --run-dir runtime-state/real-task-runs/jenny-demo `
  --replay-stage verifier-preflight `
  --json
```

Replay the final verifier without overwriting the original bundle:

```powershell
node scripts/runtime/real-task-runs.mjs `
  --run-dir runtime-state/real-task-runs/jenny-demo `
  --replay-stage verifier `
  --json
```

If the run bundle includes `shaping/execution-plan.md`, use the generated pass
commands first and only run the synthesis command after the chunk worker
outputs exist.

### Manual Path: Step By Step

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

To run the canonical runtime compatibility gate:

```powershell
node scripts/runtime/run-runtime-compatibility-suite.mjs --json --check
```

To require a built runtime and fail closed when the compatibility gate has to
skip:

```powershell
node scripts/runtime/run-runtime-compatibility-suite.mjs `
  --json `
  --check `
  --require-built-runtime
```

To inspect fixture coverage before preparing a merge to `main`:

```powershell
node scripts/runtime/report-runtime-fixture-coverage.mjs --json --check
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
