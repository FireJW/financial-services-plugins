# Claude Development Handoff

Date: `2026-04-21`
Repo: `D:\Users\rickylu\dev\financial-services-plugins`

## 1. Current Repo Read

- Current branch: `main`
- Observed upstream relation: `main...origin/main [ahead 27]`
- Do not assume this repo is a clean mirror of `origin/main`
- Do not `pull`, `reset`, or rewrite history without checking intent first

Observed local worktree state during this handoff:

- modified:
  - `CLAUDE.md`
- untracked:
  - `docs/superpowers/notes/2026-04-21-claude-status-and-direct-usage.md`

Treat those two files as active local work, not disposable noise.

## 2. What Was Restored In This Session

The `career-ops-local` and China portal shortlist surface had missing and
corrupted runtime assets. The following are now restored in the current working
tree:

- `career-ops-local/skills/career-ops-bridge/scripts/career_ops_local.py`
- `career-ops-local/skills/career-ops-bridge/scripts/career_ops_local_runtime.py`
- `career-ops-local/skills/career-ops-bridge/examples/job-track-request.template.json`
- `career-ops-local/skills/career-ops-bridge/templates/private-local/...`
- `tests/fixtures/career-ops-local/...`
- `china-portal-adapter/skills/china-portal-match-bridge/scripts/china_portal_match_bridge_runtime.py`
- repaired China adapter fixtures under `tests/fixtures/china-portal-adapter/`

This means the local job-search stack is no longer in a half-missing state.

## 3. Fresh Verification Baseline

The following focused verification suite passed after the restore work:

```powershell
& 'C:\Users\rickylu\AppData\Local\Programs\Python\Launcher\py.exe' -m pytest `
  'D:\Users\rickylu\dev\financial-services-plugins\tests\test_career_ops_bootstrap.py' `
  'D:\Users\rickylu\dev\financial-services-plugins\tests\test_career_ops_local_cli_assets.py' `
  'D:\Users\rickylu\dev\financial-services-plugins\tests\test_career_ops_local_runtime.py' `
  'D:\Users\rickylu\dev\financial-services-plugins\tests\test_career_ops_upstream_export.py' `
  'D:\Users\rickylu\dev\financial-services-plugins\tests\test_china_portal_adapter_runtime.py' `
  'D:\Users\rickylu\dev\financial-services-plugins\tests\test_china_portal_match_bridge.py' -q
```

Observed result:

- `31 passed in 0.31s`

If Claude touches the career/job stack, rerun this suite before claiming the
work is done.

## 4. Startup Pack For Claude

Before changing code in this repo, read in this order:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `routing-index.md`
4. `docs/superpowers/notes/2026-04-21-claude-status-and-direct-usage.md`
5. this handoff note

If the task is about hot-topic discovery, news/X indexing, article workflow, or
publishing, also open the latest live-snapshot and setup-launch plans under
`docs/superpowers/plans/`.

## 5. Recommended Claude Workflow

Use this flow for direct Claude development in the current repo:

1. `git status --short --branch`
   - confirm whether you are still on `main`
   - confirm whether the worktree is still dirty
2. read the task-specific command doc under `commands/`
3. read the matching `skills/*/SKILL.md`
4. inspect the runtime helper under `scripts/`
5. only then implement changes
6. rerun the narrowest relevant pytest targets first
7. rerun the broader focused suite if the work touches shared runtime surfaces

## 6. Branching And Safety Guidance

- Prefer using the existing canonical repo at:
  - `D:\Users\rickylu\dev\financial-services-plugins`
- If Claude needs isolation, prefer a normal branch in this repo over a new
  worktree unless the user explicitly wants worktrees
- Do not create broad commits from a dirty tree without first checking whether
  `CLAUDE.md` and the untracked notes are intended to be included
- Prefer targeted staging only
- Do not stage `.tmp/` or browser/session artifacts

## 7. Native Entry Points Claude Should Prefer

For repo-native usage, prefer the command docs and wrappers already described
in `CLAUDE.md` and the status note.

Important active surfaces:

- hot topic discovery
- news index / refresh
- X index
- article workflow / draft / publish
- `career-ops-local`
- China portal scan + shortlist bridge

For the job-search stack, useful direct files are:

- `career-ops-local/commands/job-intake.md`
- `career-ops-local/commands/job-match.md`
- `career-ops-local/commands/job-tailor.md`
- `career-ops-local/commands/job-track.md`
- `career-ops-local/commands/job-apply-assist.md`
- `china-portal-adapter/commands/scan-cn-jobs.md`
- `china-portal-adapter/commands/scan-cn-shortlist.md`

## 8. What Claude Should Not Re-Debug First

Do not spend the first hour re-investigating these issues unless tests show a
new regression:

- missing `career_ops_local.py`
- missing `career_ops_local_runtime.py`
- broken `job-track-request.template.json`
- missing bootstrap templates
- corrupted `china_portal_match_bridge_runtime.py`
- corrupted `basic-scan.json`
- corrupted `platform-probe.json`

Those were the specific restore items already addressed in this working tree.

## 9. Good Next Tasks For Claude

Reasonable follow-on work:

- improve the restored `career_ops_local_runtime.py` beyond the current
  test-minimal implementation
- add more realistic private-local template content
- add direct CLI smoke tests for bootstrap and shortlist wrappers
- expand bridge/runtime tests around edge cases and malformed input
- wire the restored job-search stack into any higher-level repo docs that
  should mention it

## 10. Suggested Prompt To Start Claude

Use something close to this:

```text
Work in D:\Users\rickylu\dev\financial-services-plugins.

Before changing anything, read:
1. CLAUDE.md
2. AGENTS.md
3. routing-index.md
4. docs/superpowers/notes/2026-04-21-claude-status-and-direct-usage.md
5. docs/superpowers/notes/2026-04-21-claude-development-handoff.md

Assume the repo is on main and ahead of origin.
Do not pull or reset.
Respect local dirty state.
Prefer native command docs and skill workflows before improvising.

If the task touches career-ops-local or China shortlist flows, preserve the
currently passing verification baseline and rerun the focused pytest suite
before you finish.
```
