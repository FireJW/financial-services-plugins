# Native X Index Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document a repository-wide default rule that X platform indexing must use the native `x_index_runtime` path first, with `remote_debugging` preferred on Windows, and make higher-level workflow docs distinguish live native X from static/manual social inputs.

**Architecture:** This is a documentation-only rollout. The implementation updates one repository-wide runtime guide and two command docs so the X source hierarchy is stated consistently in one place and reinforced in local command surfaces. No runtime code or workflow behavior changes in this phase.

**Tech Stack:** Markdown docs, existing repo command docs, git

---

## File Structure

- `docs/runtime/README.md`
  - repository-wide runtime/source-policy home
  - will gain the canonical X policy section
- `financial-analysis/commands/x-index.md`
  - native X command guidance
  - will be aligned to the canonical policy wording
- `financial-analysis/commands/agent-reach-bridge.md`
  - bridge-layer guidance
  - will explicitly reinforce that Agent Reach does not replace the native X route

No code files should change in this plan.

### Task 1: Add Repository-Wide X Source Policy

**Files:**
- Modify: `docs/runtime/README.md`
- Test: manual content verification in the edited file

- [ ] **Step 1: Insert a new X platform route section in `docs/runtime/README.md`**

Add a new section immediately after the existing Reddit route guidance block with content shaped like:

```md
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
```

- [ ] **Step 2: Review the new section for wording consistency**

Check that the inserted wording uses these exact themes:

- `native X route`
- `remote_debugging`
- `signed-session`
- `public scraping is fallback`
- `static/manual X-shaped inputs`

There should be no wording that implies:

- `agent-reach` is the main X route
- public scraping is acceptable as the default first step

- [ ] **Step 3: Commit the runtime README update**

```bash
git add docs/runtime/README.md
git commit -m "docs: add repository-wide native x index policy"
```

### Task 2: Align the Native X Command Doc

**Files:**
- Modify: `financial-analysis/commands/x-index.md`
- Test: manual content verification in the edited file

- [ ] **Step 1: Strengthen the guardrails in `financial-analysis/commands/x-index.md`**

Update the existing guardrail block so it reads like:

```md
Guardrails:

- `x-index` is the repository-native X / Twitter route
- prefer `remote_debugging` on Windows when a signed browser session is available
- reuse recent successful `x-index` results when they are still relevant before
  recollecting the same evidence
- do not start with public X page scraping when the native workflow can reuse a
  signed session
- when a downstream workflow only consumes curated handles, URLs, or summaries,
  do not describe that as a live native X run
```

- [ ] **Step 2: Verify the doc now reflects the canonical priority order**

Manual check:

- native live `x-index` first
- `x-index` result reuse second
- public fallback only later

The file should not leave this order implicit.

- [ ] **Step 3: Commit the `x-index` doc alignment**

```bash
git add financial-analysis/commands/x-index.md
git commit -m "docs: align x-index command with native x policy"
```

### Task 3: Clarify That Agent Reach Is A Bridge, Not The Native X Route

**Files:**
- Modify: `financial-analysis/commands/agent-reach-bridge.md`
- Test: manual content verification in the edited file

- [ ] **Step 1: Strengthen the live-default note in `financial-analysis/commands/agent-reach-bridge.md`**

Adjust the current live-default block so it clearly says:

```md
Current live defaults on this machine:

- if you do not pass `--channels`, live fetch defaults to `github + youtube`
- `rss` joins only when feeds are explicitly supplied
- `x` joins only when Agent Reach already has usable X credentials
- repository-native `x-index + remote_debugging` remains the primary X workflow
- Agent Reach may augment X-adjacent discovery, but it does not replace the
  native `x-index` route
```

- [ ] **Step 2: Add one explicit source-semantics reminder**

Add a short reminder near the workflow description:

```md
When a downstream workflow needs authoritative X evidence, use the repository's
native `x-index` path first. Treat Agent Reach as augmentation or bridging, not
as the default X indexing layer.
```

- [ ] **Step 3: Commit the bridge doc clarification**

```bash
git add financial-analysis/commands/agent-reach-bridge.md
git commit -m "docs: clarify agent reach as x augmentation layer"
```

### Task 4: Cross-Check The Three Surfaces For Consistency

**Files:**
- Modify: none unless mismatch is found
- Test: manual consistency review of all edited docs

- [ ] **Step 1: Open the three edited files side by side and compare terminology**

Verify all three surfaces consistently state:

- `x-index` is the native X route
- Windows prefers `remote_debugging`
- public scraping is fallback
- static/manual X-shaped inputs must be disclosed as such
- Agent Reach is augmentation/bridge, not the primary X path

- [ ] **Step 2: Fix any wording drift inline if found**

If one file uses weaker wording than the others, strengthen it to match the
runtime README. Do not introduce new scope. Keep all edits documentation-only.

- [ ] **Step 3: Run a minimal repository diff check**

Run:

```bash
git diff -- docs/runtime/README.md financial-analysis/commands/x-index.md financial-analysis/commands/agent-reach-bridge.md
```

Expected:

- only documentation wording changes
- no runtime/code changes

- [ ] **Step 4: Commit the consistency pass if edits were needed**

```bash
git add docs/runtime/README.md financial-analysis/commands/x-index.md financial-analysis/commands/agent-reach-bridge.md
git commit -m "docs: normalize native x policy wording"
```

### Task 5: Final Verification

**Files:**
- Test: edited documentation files only

- [ ] **Step 1: Verify the target files exist and contain the policy language**

Run:

```bash
rg -n "native X route|remote_debugging|public scraping|static/manual|Agent Reach" docs/runtime/README.md financial-analysis/commands/x-index.md financial-analysis/commands/agent-reach-bridge.md
```

Expected:

- matches in all three files
- no missing policy surface

- [ ] **Step 2: Verify git status only shows intended doc changes**

Run:

```bash
git status --short
```

Expected:

- only the three targeted doc files are modified or committed in this branch
- unrelated untracked files remain untouched

- [ ] **Step 3: Write the implementation summary**

Summarize:

- where the canonical policy now lives
- how command docs align to it
- the fact that this phase intentionally made no runtime changes

This summary is for the final response, not a new file.

---

## Self-Review

- Spec coverage:
  - repository-wide policy home: covered by Task 1
  - command-level wording alignment: covered by Task 2 and Task 3
  - consistent X source hierarchy: covered by Task 4
  - no runtime code changes: protected by Task 4 and Task 5
- Placeholder scan:
  - no `TBD` / `TODO`
  - every task has exact files and concrete wording/examples
- Type/name consistency:
  - uses consistent terms:
    - `x-index`
    - `x_index_runtime`
    - `remote_debugging`
    - `static/manual X-shaped inputs`
    - `Agent Reach`

