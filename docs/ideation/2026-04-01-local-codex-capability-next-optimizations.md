---
date: 2026-04-01
topic: local-codex-capability-next-optimizations
focus: local codex capability after runtime P0/P1 hardening
---

# Ideation: Local Codex Capability Next Optimizations

## Codebase Context

- The wrapper layer is no longer the weak point it was at the start of the week.
  `scripts/runtime/run-worker-task.mjs`,
  `scripts/runtime/run-verifier-task.mjs`, and
  `scripts/runtime/run-verification-pass.mjs` now cover multilingual intent
  carry-forward, structured verifier mode, attempt ledgers, prompt-budget
  guardrails, and a curated host reliability suite.
- `docs/runtime/README.md` and `docs/runtime/OPERATOR-MANUAL.md` show that the
  current runtime is reliable enough to operate, but still too manual to feel
  like a daily-driver local Codex system. The runbook is still a long sequence
  of commands.
- The repo now has stronger routing guidance in `AGENTS.md`, `CLAUDE.md`, and
  the newly restored `financial-analysis/commands/feedback-workflow.md`, but
  that routing mostly lives in docs and operator judgment rather than an
  executable runtime router.
- Runtime compatibility tooling already exists:
  `scripts/runtime/collect-runtime-init-report.mjs`,
  `scripts/runtime/collect-runtime-compat-report.mjs`, and
  `scripts/runtime/collect-runtime-surface-diff.mjs`.
  What is missing is a canonical, landed compatibility gate equivalent to the
  host reliability suite.
- The remaining trimmed stash is a clue. It still contains `vendor/claude-code-recovered`,
  `tests/runtime-compat/`, `scripts/stock_watch_workflow.py`, and several
  repo-routing/workflow expansions. That means the next capability layer is not
  raw reliability anymore. It is turning the hardened wrapper into a more
  automatic, more self-routing, more end-to-end operator system.

## Ranked Ideas

### 1. Canonical Runtime Compatibility Gate
**Description:** Promote the existing compatibility probes into a first-class
runtime compatibility suite with one entrypoint, stable skip/fail policy, and
clear reports for plugin discovery, runtime init, and runtime surface drift.

**Rationale:** The host reliability suite now proves wrapper correctness. The
remaining silent risk is compatibility drift between the wrapper and the
recovered runtime or plugin surface. The repo already has the probe scripts.
What is missing is a landed gate that turns those probes into a daily safety
net.

**Downsides:** This will depend on local vendor build state and can get noisy if
the skip rules are not disciplined.

**Confidence:** 92%
**Complexity:** Medium
**Status:** Unexplored

### 2. Executable Request Router For Native Workflows
**Description:** Build a runtime-side router that takes a raw task request and
chooses the right native workflow, plugin dirs, and safety knobs automatically.
Examples: route feedback-interview tasks into `feedback-workflow`, classic
China-research tasks into the classic-case router, and evidence-heavy verifier
passes into structured mode by default.

**Rationale:** This is the biggest capability jump per unit of effort. The repo
already knows how tasks should be routed, but that intelligence mostly lives in
markdown. Turning it into executable routing is how local Codex starts feeling
context-aware instead of just tool-rich.

**Downsides:** Heuristic routing can misclassify tasks. It needs obvious
overrides and trace output so operators can see why it chose a path.

**Confidence:** 90%
**Complexity:** Medium
**Status:** Unexplored

### 3. One-Command Real-Task Runner
**Description:** Add a single command that turns `raw request -> INTENT -> NOW
-> worker -> verifier -> ledger -> scorecard` into one run with predictable
artifact paths.

**Rationale:** The current operator manual is good, but still too manual. A
one-command runner would make the hardened runtime usable as a real daily
workflow, not just a validated engineering subsystem. This is the difference
between "we can run it" and "we actually will run it."

**Downsides:** If overbuilt too early, this becomes a mini platform with too
many knobs. It should stay wrapper-thin and artifact-first.

**Confidence:** 88%
**Complexity:** Medium
**Status:** Unexplored

### 4. Oversize-Task Splitter And Evidence Shaper
**Description:** When prompt budget risk reaches `warning` or `danger`, add an
automatic shaping layer that suggests or executes a safer decomposition:
evidence summary first, chunked worker passes, then final synthesis and
verification.

**Rationale:** Prompt-budget guardrails now tell us when a task is too large,
but they still rely on the operator to redesign the run. Turning budget signals
into an actual decomposition path is the next big step for handling hard,
evidence-heavy research tasks locally.

**Downsides:** Task splitting can introduce false confidence if the synthesis
step glosses over missing context. It needs explicit traceability between chunks
and final conclusions.

**Confidence:** 84%
**Complexity:** Medium-High
**Status:** Unexplored

### 5. Authenticated Evidence Acquisition Layer
**Description:** Add a first-class pre-worker collection layer for tasks that
depend on signed sessions, authenticated browsing, or platform-native fetch
workflows. The output should be a stable evidence pack, not ad hoc browser
state.

**Rationale:** The wrapper is now much better once evidence already exists. A
big remaining capability gap is reliable evidence collection for tasks like X
post extraction or logged-in product/market research. This is where local Codex
stops being "good at processing files" and becomes "good at collecting the
right files."

**Downsides:** Browser auth and signed-session flows are harder to test and can
be brittle across machines.

**Confidence:** 80%
**Complexity:** High
**Status:** Unexplored

### 6. Durable Run Bundles And Replay Commands
**Description:** Replace the flat `runtime-state/` scratch habit with stable
per-task bundles that can be listed, replayed, compared, and harvested into
fixtures later.

**Rationale:** Attempt ledgers now exist, but the surrounding artifacts are
still ad hoc. Durable run bundles would make postmortems, regression harvesting,
and cross-session handoff dramatically easier.

**Downsides:** This improves long-term leverage more than immediate task success,
so it is slightly less urgent than routing and one-command execution.

**Confidence:** 78%
**Complexity:** Medium
**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Deep vendor-runtime surgery | Wrong order. Wrapper-first is still working and keeps blast radius down. |
| 2 | More profile types right now | New profiles add knobs before the router and runner are good enough to use them well. |
| 3 | UI dashboard first | A dashboard before executable routing and compatibility gating is mostly polish. |
| 4 | Full multi-agent swarm orchestration | Premature. The biggest remaining gains are routing, shaping, and operability. |
| 5 | More real-task fixtures only | Still useful, but the suite is already credible. The next bottleneck is how tasks get routed and executed. |
| 6 | Commit the entire remaining stash | Too much mixed scope, too much vendor bulk, not enough leverage per risk. |

## Session Log

- 2026-04-01: Post-P0/P1 ideation refresh. Re-ranked next improvements after structured verifier mode, attempt ledger, prompt-budget guardrails, and canonical real-task fixtures were all landed. Top priorities now: runtime compatibility gate, executable routing, and a one-command real-task runner.
